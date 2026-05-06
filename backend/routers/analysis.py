"""
면접 분석 라우터
- POST /analysis/feedback          : 질문별 즉시 AI 피드백
- POST /analysis/{interview_id}/start  : 분석 작업 시작 (백그라운드)
- GET  /analysis/{interview_id}        : 분석 결과 조회
"""
import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db, AsyncSessionLocal
from core.security import get_current_user_id
from models.interview import Interview, InterviewStatus
from models.analysis import Analysis
from schemas.schemas import AnalysisResponse
from services.llm.gemini_service import gemini_service
from services.llm.kobert_service import kobert_service
from services.voice.whisper_service import whisper_service
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

<<<<<<< Updated upstream
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

        # ── 2) Whisper: 음성 분석 (영상이 있을 경우) ───
        if interview.video_path:
            speech = await whisper_service.analyze_speech(interview.video_path)
            analysis.speech_score      = speech["speech_score"]
            analysis.speech_pace       = speech["speech_pace"]
            analysis.filler_word_count = speech["filler_word_count"]

            # ── 3) MediaPipe: 영상 분석 ─────────────────
            vision = await mediapipe_service.analyze_video(interview.video_path)
            analysis.eye_contact_score = vision["eye_contact_score"]
            analysis.posture_score     = vision["posture_score"]
            analysis.expression_data   = vision["expression_data"]

        # ── 4) 종합 점수 + 피드백 ───────────────────────
        sub_scores = [
            analysis.speech_score,
            analysis.eye_contact_score,
            analysis.posture_score,
        ]
        analysis.total_score = _avg([s for s in sub_scores if s is not None])

        # 임시 피드백 (다음 단계: KoBERT/LLM이 생성)
        analysis.feedback_summary = "AI 종합 피드백 (Stub) — 모델 통합 후 자동 생성됩니다."
        analysis.strengths = ["답변을 끝까지 시도함"]
        analysis.improvements = ["구체적인 사례를 추가하면 좋습니다"]
=======
    try:
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

            # 2) 기존 분석 레코드 확인 (재실행 시 갱신)
            existing = await db.execute(
                select(Analysis).where(Analysis.interview_id == interview_id)
            )
            analysis = existing.scalar_one_or_none() or Analysis(interview_id=interview_id)

            # 3) Q&A 데이터 준비 및 답변 현황 로깅
            qa_data = [
                {"question": q.question_text, "answer": q.answer_text or ""}
                for q in interview.questions
            ]
            answered = [qa for qa in qa_data if qa["answer"].strip()]
            logger.info(f"[Analysis] {len(answered)}/{len(qa_data)} 질문에 답변 있음")

            # 4) KoBERT: 답변 내용 분석 (답변이 있는 질문만)
            content_scores, relevance_scores, clarity_scores = [], [], []
            for qa in answered:
                try:
                    r = await kobert_service.analyze_answer(qa["question"], qa["answer"])
                    if r.get("status") == "success":
                        content_scores.append(r["content_score"])
                        relevance_scores.append(r["relevance_score"])
                        clarity_scores.append(r["clarity_score"])
                except Exception as e:
                    logger.warning(f"[Analysis] KoBERT 분석 실패: {e}")

            analysis.content_score   = _avg(content_scores)
            analysis.relevance_score = _avg(relevance_scores)
            analysis.clarity_score   = _avg(clarity_scores)
            logger.info(
                f"[Analysis] content={analysis.content_score} "
                f"relevance={analysis.relevance_score} clarity={analysis.clarity_score}"
            )

            # 5) Whisper + MediaPipe: 영상 분석 (영상이 있을 경우만 실제 분석)
            if interview.video_path:
                try:
                    speech = await whisper_service.analyze_speech(interview.video_path)
                    analysis.speech_score      = speech["speech_score"]
                    analysis.speech_pace       = speech["speech_pace"]
                    analysis.filler_word_count = speech["filler_word_count"]
                except Exception as e:
                    logger.warning(f"[Analysis] Whisper 분석 실패: {e}")
                    analysis.speech_score = 70.0
>>>>>>> Stashed changes

                try:
                    vision = await mediapipe_service.analyze_video(interview.video_path)
                    analysis.eye_contact_score = vision["eye_contact_score"]
                    analysis.posture_score     = vision["posture_score"]
                    analysis.expression_data   = vision["expression_data"]
                except Exception as e:
                    logger.warning(f"[Analysis] MediaPipe 분석 실패: {e}")
                    analysis.eye_contact_score = 75.0
                    analysis.posture_score     = 80.0
            else:
                # 영상 없음: 현 구현 단계에서 기본값 사용
                analysis.speech_score      = 70.0
                analysis.eye_contact_score = 75.0
                analysis.posture_score     = 80.0

            # 6) 종합 점수 계산 (가용한 모든 점수의 가중 평균)
            sub_scores = [
                analysis.content_score,
                analysis.relevance_score,
                analysis.clarity_score,
                analysis.speech_score,
                analysis.eye_contact_score,
                analysis.posture_score,
            ]
            analysis.total_score = _avg([s for s in sub_scores if s is not None])
            logger.info(f"[Analysis] total_score={analysis.total_score}")

            # 7) Gemini: Q&A 기반 종합 피드백 생성
            gemini_qa = [
                {
                    "question": qa["question"],
                    "answer": qa["answer"] if qa["answer"].strip() else "답변 없음",
                }
                for qa in qa_data
            ]
            try:
                ai_feedback = await gemini_service.generate_interview_feedback(gemini_qa)
                analysis.feedback_summary = ai_feedback["feedback_summary"]
                analysis.strengths        = ai_feedback["strengths"]
                analysis.improvements     = ai_feedback["improvements"]
                logger.info("[Analysis] Gemini 피드백 생성 완료")
            except Exception as e:
                logger.error(f"[Analysis] Gemini 피드백 생성 실패: {e}")
                analysis.feedback_summary = "피드백 생성 중 오류가 발생했습니다."
                analysis.strengths        = []
                analysis.improvements     = []

            db.add(analysis)
            await db.commit()
            logger.info(f"[Analysis] interview_id={interview_id} 분석 완료 저장")

    except Exception as e:
        logger.exception(f"[Analysis] interview_id={interview_id} 파이프라인 전체 오류: {e}")


def _avg(values: list) -> Optional[float]:
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
            detail="분석 결과가 아직 없습니다. 잠시 후 다시 시도하세요.",
        )
    return analysis
