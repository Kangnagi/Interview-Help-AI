"""
면접 분석 라우터
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
from models.interview import Interview, InterviewQuestion, InterviewStatus
from models.analysis import Analysis
from schemas.schemas import AnalysisResponse
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

        db.add(analysis)
        await db.commit()

    logger.info(f"[Analysis] interview_id={interview_id} 분석 완료")


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
        select(Analysis).where(Analysis.interview_id == interview_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="분석 결과가 아직 없습니다. 먼저 분석을 시작하세요.",
        )
    return analysis
