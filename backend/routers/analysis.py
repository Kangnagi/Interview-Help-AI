"""
면접 분석 라우터
- POST /analysis/{interview_id}/start  : 분석 작업 시작 (백그라운드)
- GET  /analysis/{interview_id}        : 분석 결과 조회

현재는 Stub 서비스 호출 → 다음 단계에서 실제 KoBERT/Whisper/MediaPipe로 교체.
"""
import logging
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db, AsyncSessionLocal
from core.config import settings
from core.security import get_current_user_id
from models.interview import Interview, InterviewQuestion, InterviewStatus
from models.analysis import Analysis
from schemas.schemas import AnalysisResponse
from services.llm.kobert_service import kobert_service
from services.llm.gemini_service import analyze_answers_batch_with_gemini, generate_overall_summary_with_gemini
from services.voice.librosa_service import generate_audio_spectrogram, save_audio_spectrogram, get_audio_duration
from services.vision.mediapipe_service import mediapipe_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["분석"])


# ───────────────────────────────────────────────────────────
# 백그라운드 작업: 면접 종료 후 종합 분석 수행
# ───────────────────────────────────────────────────────────
async def _run_analysis_pipeline(interview_id: int):
    """
    면접 1건에 대한 전체 분석 파이프라인.
    BackgroundTasks 안에서 실행되며 자체 DB 세션을 연다.
    """
    logger.info(f"[Analysis] interview_id={interview_id} 분석 시작")

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
            speech_paces = []
            all_feedbacks = []

            qna_list = []
            valid_questions = []

            for q in interview.questions:
                if not q.answer_text or not q.audio_path:
                    continue
               
                # 1) 발화 속도 계산 (WPM)
                duration = get_audio_duration(q.audio_path)
                if duration > 0:
                    word_count = len(q.answer_text.split())
                    # WPM = (단어 수 / 초) * 60
                    wpm = round((word_count / duration) * 60, 1)
                    speech_paces.append(wpm)
                    
                    # 발화 속도 점수화 (예: 한국어 기준 분당 80~110단어가 적절하다고 가정)
                    # 너무 빠르거나(150 초과) 너무 느린(40 미만) 경우 감점 로직 추가 가능
                    if 70 <= wpm <= 130:
                        s_score = 95
                    elif wpm < 40 or wpm > 160:
                        s_score = 60
                    else:
                        s_score = 80
                    speech_scores.append(s_score)

                # 2) 🎵 오디오 파일을 이미지로 변환 및 저장 (Librosa)
                image_bytes = None
                try:
                    # 디버깅/확인용: 이미지를 실제 폴더에 저장
                    saved_path = await save_audio_spectrogram(q.audio_path)
                    if saved_path:
                        # 저장된 파일을 읽어서 AI 모델 전송용 bytes 데이터로 변환
                        with open(saved_path, "rb") as f:
                            image_bytes = f.read()
                        logger.info(f"[Analysis] 스펙트로그램 이미지 저장 완료: {saved_path}")
                except Exception as e:
                    logger.warning(f"오디오 이미지 변환/저장 실패 (건너뜀): {e}")

                qna_list.append({
                    "question": q.question_text,
                    "answer": q.answer_text,
                    "audio_image_bytes": image_bytes
                })
                valid_questions.append(q)

            # 저장된 실시간 피드백이 있으면 배치 Gemini 호출 건너뜀
            all_have_feedback = bool(valid_questions) and all(q.ai_feedback for q in valid_questions)
            if all_have_feedback:
                logger.info(f"[Analysis] 저장된 실시간 피드백 사용 (Gemini 배치 생략)")
                batch_results = [
                    {
                        "content_score": int(q.ai_score or 80),
                        "relevance_score": int(q.ai_score or 80),
                        "clarity_score": int(q.ai_score or 80),
                        "speech_score": int(q.ai_score or 80),
                        "posture_score": int(q.ai_score or 80),
                        "eye_contact_score": int(q.ai_score or 80),
                        "feedback": q.ai_feedback or "",
                    }
                    for q in valid_questions
                ]
            else:
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

            analysis.speech_score    = _avg(speech_scores) or 80.0
            analysis.speech_pace     = _avg(speech_paces)
            analysis.posture_score   = _avg(posture_scores)
            analysis.eye_contact_score = _avg(eye_contact_scores)

            if getattr(interview, 'video_path', None):
                logger.warning(f"[Analysis] 저장된 비디오 분석은 건너뜁니다.")

            # ── 4) 종합 점수 계산 ───────────────────────────
            sub_scores = [
                analysis.content_score,
                analysis.relevance_score,
                analysis.clarity_score,
                analysis.speech_score,
                analysis.posture_score,
                analysis.eye_contact_score
            ]
            analysis.total_score = _avg([s for s in sub_scores if s is not None])

            # ── 5) 종합 총평 / 강점 / 개선점 생성 ─────
            # qna_feedbacks는 db.commit() 이전에 구성 (커밋 후 ORM 객체 만료됨)
            qna_feedbacks = [
                {
                    "question": q.question_text,
                    "answer": q.answer_text or "",
                    "feedback": r.get("feedback", "") if isinstance(r, dict) else str(r),
                }
                for q, r in zip(valid_questions, batch_results)
            ]
            summary_result = await generate_overall_summary_with_gemini(qna_feedbacks)
            analysis.feedback_summary = summary_result.get("feedback_summary", "")
            analysis.strengths    = summary_result.get("strengths", []) or []
            analysis.improvements = summary_result.get("improvements", []) or []

            # 점수 + 총평을 한 번에 저장 (중간 커밋 제거 — 부분 저장 시 프론트 polling이 조기 종료됨)
            db.add(analysis)
            await db.commit()

        logger.info(f"[Analysis] interview_id={interview_id} 분석 완료 및 DB 저장 성공")
    except Exception as e:
        logger.error(f"[Analysis] 파이프라인 실행 중 치명적 오류 발생: {e}", exc_info=True)


def _avg(values):
    """None/빈 리스트 안전한 평균"""
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


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
    # 권한 + 상태 확인
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


@router.get("/{interview_id}", response_model=AnalysisResponse)
async def get_analysis(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """면접 분석 결과 조회."""
    # 권한 확인
    iv = await db.execute(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.user_id == user_id,
        )
    )
    if not iv.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    result = await db.execute(
        select(Analysis)
        .options(
            selectinload(Analysis.interview)
            .selectinload(Interview.questions)
        )
        .where(Analysis.interview_id == interview_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="분석 결과가 아직 없습니다. 먼저 분석을 시작하세요.",
        )

    analysis.question_feedbacks = sorted(
        [q for q in analysis.interview.questions if q.answer_text],
        key=lambda q: q.order,
    )
    return analysis
