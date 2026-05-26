"""
면접 분석 라우터
- POST /analysis/feedback                  : 질문-답변 즉시 피드백
- POST /analysis/{interview_id}/start      : 분석 작업 시작 (백그라운드)
- GET  /analysis/{interview_id}            : 분석 결과 조회
"""
import logging
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional

from core.database import get_db, AsyncSessionLocal
from core.config import settings
from core.security import get_current_user_id
from models.interview import Interview, InterviewQuestion, InterviewStatus
from models.analysis import Analysis
from schemas.schemas import AnalysisResponse
from services.llm.kobert_service import kobert_service
from services.llm.gemini_service import analyze_answers_batch_with_gemini
from services.voice.whisper_service import whisper_service
from services.vision.mediapipe_service import mediapipe_service
from services.llm.gemini_service import gemini_service, analyze_answers_batch_with_gemini

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["분석"])


def _avg(values):
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _safe_int(d: dict, key: str, default: int = 80) -> int:
    try:
        return int(d.get(key, default))
    except (TypeError, ValueError):
        return default


class FeedbackRequest(BaseModel):
    question: str
    answer: str
    company: Optional[str] = ""
    job: Optional[str] = ""


@router.post("/feedback")
async def get_question_feedback(
    body: FeedbackRequest,
    user_id: int = Depends(get_current_user_id),
):
    """답변 완료 직후 Gemini에게 해당 질문-답변에 대한 즉시 피드백을 요청합니다."""
    feedback = await gemini_service.generate_question_feedback(
        body.question, body.answer, body.company or "", body.job or ""
    )
    return {"feedback": feedback}


# ───────────────────────────────────────────────────────────
# 백그라운드 작업: 면접 종료 후 종합 분석 수행
# ───────────────────────────────────────────────────────────

async def _run_analysis_pipeline(interview_id: int):
    """
    면접 1건에 대한 전체 분석 파이프라인.
    BackgroundTasks 안에서 실행되며 자체 DB 세션을 연다.
    """
    logger.info(f"[Analysis] interview_id={interview_id} 분석 시작")

    async with AsyncSessionLocal() as db:
        # 1) 면접 + 질문 로드
        result = await db.execute(
            select(Interview)
            .options(selectinload(Interview.questions))
            .where(Interview.id == interview_id)
        )
        interview = result.scalar_one_or_none()

        if not interview:
            logger.error(f"[Analysis] interview {interview_id} 없음")
            return

        # 2) 기존 분석 로드 or 새로 생성
        existing = await db.execute(
            select(Analysis).where(Analysis.interview_id == interview_id)
        )
        analysis = existing.scalar_one_or_none() or Analysis(interview_id=interview_id)

        # 3) 각 질문별 오디오 처리
        qna_list = []
        valid_questions = []

        for q in interview.questions:
            if not q.answer_text:
                continue

            audio_path = f"{settings.UPLOAD_DIR}/iv_{interview_id}_q_{q.id}.webm"
            image_bytes = None
            try:
                from services.voice.librosa_service import generate_audio_spectrogram
                image_bytes = await generate_audio_spectrogram(audio_path)
            except Exception as e:
                logger.warning(f"오디오 이미지 변환 실패 (건너뜀): {e}")

            qna_list.append({
                "question": q.question_text,
                "answer": q.answer_text,
                "audio_image_bytes": image_bytes
            })
            valid_questions.append(q)

        # 4) Gemini 배치 분석 → 실패 시 KoBERT 점수로 폴백
        from services.llm.kobert_service import kobert_service

        content_scores, relevance_scores, clarity_scores = [], [], []
        speech_scores, posture_scores, eye_contact_scores = [], [], []
        all_feedbacks = []

        batch_results = await analyze_answers_batch_with_gemini(qna_list) if qna_list else []

        for q, gemini_result in zip(valid_questions, batch_results):
            # Gemini 스텁(70점 고정)인지 확인: content_score가 정확히 70이면 API 실패로 판단
            is_gemini_stub = (
                not isinstance(gemini_result, dict)
                or gemini_result.get("content_score") == 70
                and gemini_result.get("relevance_score") == 70
            )

            if isinstance(gemini_result, dict) and not is_gemini_stub:
                # Gemini 실제 결과 사용
                c_score  = _safe_int(gemini_result, "content_score")
                r_score  = _safe_int(gemini_result, "relevance_score")
                cl_score = _safe_int(gemini_result, "clarity_score")
                sp_score = _safe_int(gemini_result, "speech_score")
                p_score  = _safe_int(gemini_result, "posture_score")
                e_score  = _safe_int(gemini_result, "eye_contact_score")
                fb_text  = gemini_result.get("feedback", "")
            else:
                # Gemini 실패 → KoBERT 임베딩 기반 실제 점수 사용
                logger.info(f"[Analysis] Q{q.id}: Gemini 스텁 감지 → KoBERT 폴백")
                try:
                    kobert_result = await kobert_service.analyze_answer(
                        q.question_text, q.answer_text or ""
                    )
                    if kobert_result.get("status") == "success":
                        c_score  = int(kobert_result["content_score"])
                        r_score  = int(kobert_result["relevance_score"])
                        cl_score = int(kobert_result["clarity_score"])
                    else:
                        c_score = r_score = cl_score = 60
                except Exception as ke:
                    logger.warning(f"KoBERT 폴백 실패: {ke}")
                    c_score = r_score = cl_score = 60

                sp_score = p_score = e_score = 70
                fb_text = (
                    gemini_result.get("feedback", "") if isinstance(gemini_result, dict)
                    else f"내용 {c_score}점 / 관련성 {r_score}점 / 명확성 {cl_score}점"
                )

            content_scores.append(c_score)
            relevance_scores.append(r_score)
            clarity_scores.append(cl_score)
            speech_scores.append(sp_score)
            posture_scores.append(p_score)
            eye_contact_scores.append(e_score)

            # 질문별 점수·피드백 저장 (분석 결과 페이지 상세 표시용)
            q.ai_score = round((c_score + r_score + cl_score) / 3, 1)
            q.ai_feedback = fb_text

            if fb_text:
                all_feedbacks.append(f"Q: {q.question_text}\n{fb_text}")

        analysis.content_score     = _avg(content_scores)
        analysis.relevance_score   = _avg(relevance_scores)
        analysis.clarity_score     = _avg(clarity_scores)
        analysis.speech_score      = _avg(speech_scores)
        analysis.posture_score     = _avg(posture_scores)
        analysis.eye_contact_score = _avg(eye_contact_scores)

        if getattr(interview, 'video_path', None):
            logger.warning("[Analysis] 저장된 비디오 분석은 건너뜁니다.")

        # 5) 종합 점수
        sub_scores = [
            analysis.content_score, analysis.relevance_score, analysis.clarity_score,
            analysis.speech_score, analysis.posture_score, analysis.eye_contact_score,
        ]
        analysis.total_score = _avg([s for s in sub_scores if s is not None])

        # 6) Gemini 종합 피드백
        qa_data = [
            {"question": q.question_text, "answer": q.answer_text or "답변 없음"}
            for q in interview.questions
        ]
        ai_feedback = await gemini_service.generate_interview_feedback(qa_data)
        analysis.feedback_summary = ai_feedback["feedback_summary"]
        analysis.strengths        = ai_feedback["strengths"]
        analysis.improvements     = ai_feedback["improvements"]
    try:
        async with AsyncSessionLocal() as db:
            # 1) 면접 + 질문 + 기존 분석 로드
            result = await db.execute(
                select(Interview)
                .options(selectinload(Interview.questions))
                .where(Interview.id == interview_id)
            )
            interview = result.scalar_one_or_none()
            if not interview:
                logger.error(f"[Analysis] interview {interview_id} 없음")
                return

            # 기존 분석 레코드 확인 (재실행 시 갱신)
            existing = await db.execute(
                select(Analysis).where(Analysis.interview_id == interview_id)
            )
            analysis = existing.scalar_one_or_none() or Analysis(interview_id=interview_id)

            # ── 2) KoBERT(점수 평가) 및 Gemini(피드백 생성) 분석 ─────────
            content_scores, relevance_scores, clarity_scores = [], [], []
            speech_scores, posture_scores, eye_contact_scores = [], [], []
            all_feedbacks = []

            qna_list = []
            valid_questions = []

            for q in interview.questions:
                if not q.answer_text:
                    continue
               
                # 🎵 오디오 파일을 이미지로 변환 (Librosa)
                audio_path = f"{settings.UPLOAD_DIR}/iv_{interview_id}_q_{q.id}.webm"
                image_bytes = None
                try:
                    from services.voice.librosa_service import generate_audio_spectrogram
                    image_bytes = await generate_audio_spectrogram(audio_path)
                except Exception as e:
                    logger.warning(f"오디오 이미지 변환 실패 (건너뜀): {e}")

                qna_list.append({
                    "question": q.question_text,
                    "answer": q.answer_text,
                    "audio_image_bytes": image_bytes
                })
                valid_questions.append(q)

            # 한 번의 호출로 모든 분석 결과 받아오기
            batch_results = await analyze_answers_batch_with_gemini(qna_list) if qna_list else []

            # ── Gemini 피드백 결과 매핑 ──
            for q, gemini_result in zip(valid_questions, batch_results):
                if isinstance(gemini_result, dict):
                    try: c_score = int(gemini_result.get("content_score", 80))
                    except: c_score = 80
                    try: r_score = int(gemini_result.get("relevance_score", 80))
                    except: r_score = 80
                    try: cl_score = int(gemini_result.get("clarity_score", 80))
                    except: cl_score = 80
                    try: sp_score = int(gemini_result.get("speech_score", 80))
                    except: sp_score = 80
                    try: p_score = int(gemini_result.get("posture_score", 80))
                    except: p_score = 80
                    try: e_score = int(gemini_result.get("eye_contact_score", 80))
                    except: e_score = 80
                    fb_text = gemini_result.get("feedback", "")
                else:
                    c_score = r_score = cl_score = sp_score = p_score = e_score = 80
                    fb_text = str(gemini_result)
                    content_scores.append(c_score)
                    relevance_scores.append(r_score)
                    clarity_scores.append(cl_score)
                    speech_scores.append(sp_score)
                    posture_scores.append(p_score)
                    eye_contact_scores.append(e_score)
              
                if fb_text:
                    all_feedbacks.append(f"Q: {q.question_text}\n{fb_text}")

            analysis.content_score   = _avg(content_scores)
            analysis.relevance_score = _avg(relevance_scores)
            analysis.clarity_score   = _avg(clarity_scores)
            
            analysis.speech_score    = _avg(speech_scores)
            analysis.posture_score   = _avg(posture_scores)
            analysis.eye_contact_score = _avg(eye_contact_scores)


            # ── 3) 파일 분석(음성/영상) 건너뛰기 (에러 방지) ───
            # 현재 웹소켓으로 실시간 전송 중이므로 저장된 video_path 호출 시 에러가 날 수 있음. 
            # 안전을 위해 try-except로 감쌉니다.
            if getattr(interview, 'video_path', None):
                logger.warning(f"[Analysis] 저장된 비디오 분석은 건너뜁니다.")

            # ── 4) 종합 점수 + 피드백 ───────────────────────
            sub_scores = [
                analysis.content_score,
                analysis.relevance_score,
                analysis.clarity_score,
                analysis.speech_score,
                analysis.posture_score,
                analysis.eye_contact_score
            ]
            analysis.total_score = _avg([s for s in sub_scores if s is not None])

            analysis.feedback_summary = "전체적인 답변 내용을 분석한 결과입니다." 
            analysis.improvements = all_feedbacks if all_feedbacks else ["구체적인 답변 사례를 보강해 보세요."]
            
            db.add(analysis)
            await db.commit()

        logger.info(f"[Analysis] interview_id={interview_id} 분석 완료 및 DB 저장 성공")
    except Exception as e:
        logger.error(f"[Analysis] 파이프라인 실행 중 치명적 오류 발생: {e}", exc_info=True)


# ───────────────────────────────────────────────────────────
# REST 엔드포인트
# ───────────────────────────────────────────────────────────

@router.post("/{interview_id}/start", status_code=202)
async def start_analysis(
    interview_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """면접 분석을 백그라운드에서 시작."""
    result = await db.execute(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.user_id == user_id,
        )
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    if interview.status != InterviewStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="완료된 면접만 분석할 수 있습니다",
        )

    background_tasks.add_task(_run_analysis_pipeline, interview_id)
    return {
        "message": "분석을 시작했습니다",
        "interview_id": interview_id,
        "status": "processing",
    }


@router.get("/{interview_id}")
async def get_analysis(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """면접 분석 결과 조회 (질문별 상세 피드백 포함)."""
    iv = await db.execute(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.user_id == user_id,
        )
    )
    if not iv.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    result = await db.execute(
        select(Analysis).where(Analysis.interview_id == interview_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="분석 결과가 아직 없습니다. 먼저 분석을 시작하세요.",
        )

    q_result = await db.execute(
        select(InterviewQuestion)
        .where(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.order)
    )
    questions = q_result.scalars().all()

    return {
        "id": analysis.id,
        "interview_id": analysis.interview_id,
        "total_score": analysis.total_score,
        "content_score": analysis.content_score,
        "relevance_score": analysis.relevance_score,
        "clarity_score": analysis.clarity_score,
        "speech_score": analysis.speech_score,
        "posture_score": analysis.posture_score,
        "eye_contact_score": analysis.eye_contact_score,
        "feedback_summary": analysis.feedback_summary,
        "strengths": analysis.strengths,
        "improvements": analysis.improvements,
        "created_at": analysis.created_at,
        "question_feedbacks": [
            {
                "id": q.id,
                "order": q.order,
                "question_text": q.question_text,
                "answer_text": q.answer_text,
                "ai_score": q.ai_score,
                "ai_feedback": q.ai_feedback,
            }
            for q in questions
        ],
    }
