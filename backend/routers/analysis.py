import logging
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import get_db, AsyncSessionLocal
from core.config import settings
from core.security import get_current_user_id
from core.vision_buffer import get_and_clear_vision_scores
from models.interview import Interview, InterviewQuestion, InterviewStatus
from models.analysis import Analysis
from schemas.schemas import AnalysisResponse
from services.llm.kobert_service import kobert_service
from services.llm.gemini_service import analyze_answers_batch_with_gemini, generate_overall_summary_with_gemini

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["분석"])


def _avg(values):
    """None/빈 리스트 안전한 평균."""
    valid = [v for v in values if v is not None]
    return round(sum(valid) / len(valid), 2) if valid else None


def _safe_int(val, default: int = 80) -> int:
    try:
        return int(val)
    except Exception:
        return default


# ───────────────────────────────────────────────────────────
# 백그라운드 작업: 면접 종료 후 종합 분석 수행
# ───────────────────────────────────────────────────────────
async def _run_analysis_pipeline(interview_id: int):
    logger.info(f"[Analysis] interview_id={interview_id} 분석 시작")

    try:
        async with AsyncSessionLocal() as db:
            # ── 1) 면접 + 질문 로드 ──────────────────────────────
            result = await db.execute(
                select(Interview)
                .options(selectinload(Interview.questions))
                .where(Interview.id == interview_id)
            )
            interview = result.scalar_one_or_none()
            if not interview:
                logger.error(f"[Analysis] interview {interview_id} 없음")
                return

            existing = await db.execute(
                select(Analysis).where(Analysis.interview_id == interview_id)
            )
            analysis = existing.scalar_one_or_none() or Analysis(interview_id=interview_id)

            valid_questions = [q for q in interview.questions if q.answer_text]
            if not valid_questions:
                logger.warning(f"[Analysis] 답변이 있는 질문 없음 — 분석 중단")
                return

            # ── 2) KoBERT: 텍스트 기반 점수 (content / relevance / clarity) ──
            kobert_results = []
            for q in valid_questions:
                kobert = await kobert_service.analyze_answer(q.question_text, q.answer_text)
                kobert_results.append(kobert)
                logger.debug(f"[Analysis] KoBERT q{q.id}: {kobert.get('status')}")

            content_scores   = [k["content_score"]   for k in kobert_results if k.get("status") == "success"]
            relevance_scores = [k["relevance_score"]  for k in kobert_results if k.get("status") == "success"]
            clarity_scores   = [k["clarity_score"]    for k in kobert_results if k.get("status") == "success"]

            # ── 3) Gemini 배치: 피드백 텍스트 + speech_score ────────────────
            qna_list = [{"question": q.question_text, "answer": q.answer_text} for q in valid_questions]
            batch_results = await analyze_answers_batch_with_gemini(qna_list)

            speech_scores = []
            for q, gemini_r, kobert_r in zip(valid_questions, batch_results, kobert_results):
                if isinstance(gemini_r, dict):
                    sp_score  = _safe_int(gemini_r.get("speech_score"))
                    fb_text   = gemini_r.get("feedback", "")

                    # Gemini content/relevance/clarity를 KoBERT 결과로 덮어씀
                    # (KoBERT가 실제 임베딩 기반이라 더 신뢰성 있음)
                    if kobert_r.get("status") == "success":
                        q_content   = kobert_r["content_score"]
                        q_relevance = kobert_r["relevance_score"]
                        q_clarity   = kobert_r["clarity_score"]
                    else:
                        q_content   = _safe_int(gemini_r.get("content_score"))
                        q_relevance = _safe_int(gemini_r.get("relevance_score"))
                        q_clarity   = _safe_int(gemini_r.get("clarity_score"))
                else:
                    sp_score    = 70
                    fb_text     = ""
                    q_content   = kobert_r["content_score"]   if kobert_r.get("status") == "success" else 70
                    q_relevance = kobert_r["relevance_score"]  if kobert_r.get("status") == "success" else 70
                    q_clarity   = kobert_r["clarity_score"]    if kobert_r.get("status") == "success" else 70

                speech_scores.append(sp_score)

                # 질문별 종합 점수 = (content·40 + relevance·35 + clarity·25) / 100
                q_score = round(q_content * 0.4 + q_relevance * 0.35 + q_clarity * 0.25)

                # Gemini 피드백이 없으면 KoBERT 점수 기반 폴백 피드백 생성
                # (짧은 답변 포함 모든 질문이 동일하게 피드백을 갖도록 보장)
                if not fb_text:
                    if kobert_r.get("status") == "success":
                        r  = kobert_r.get("relevance_score", 0)
                        c  = kobert_r.get("content_score",   0)
                        cl = kobert_r.get("clarity_score",   0)
                        fb_text = (
                            f"1. {'질문 관련성이 높은 답변입니다.' if r >= 70 else '질문의 핵심에 더 집중하여 답변해보세요.'}\n"
                            f"2. {'답변 내용이 충실합니다.' if c >= 70 else 'STAR 기법(상황→과제→행동→결과)으로 답변을 구체화해보세요.'}\n"
                            f"3. {'표현이 명확합니다.' if cl >= 70 else '추임새나 반복 표현을 줄이고 더 명확하게 전달해보세요.'}"
                        )
                    else:
                        answer_len = len((q.answer_text or "").strip())
                        if answer_len < 10:
                            fb_text = "답변이 너무 짧습니다. 면접에서는 구체적인 경험과 이유를 함께 설명해주세요."
                        else:
                            fb_text = "구체적인 경험과 수치를 활용해 답변하면 면접관에게 더 설득력 있게 전달됩니다."

                # 각 질문 레코드에 Gemini 피드백과 종합 점수 저장 (기존 로컬 피드백 덮어씀)
                q.ai_score    = max(20, min(100, q_score))
                q.ai_feedback = fb_text
                db.add(q)

            # ── 4) 영역별 집계 점수 ──────────────────────────────────────────
            analysis.content_score    = _avg(content_scores)   or _avg([_safe_int(r.get("content_score"))   for r in batch_results if isinstance(r, dict)])
            analysis.relevance_score  = _avg(relevance_scores) or _avg([_safe_int(r.get("relevance_score")) for r in batch_results if isinstance(r, dict)])
            analysis.clarity_score    = _avg(clarity_scores)   or _avg([_safe_int(r.get("clarity_score"))   for r in batch_results if isinstance(r, dict)])
            analysis.speech_score     = _avg(speech_scores)

            # posture / eye_contact: 실시간 MediaPipe 버퍼 우선 사용, 없으면 텍스트 기반 추정
            vision_scores = get_and_clear_vision_scores(interview_id)
            if vision_scores:
                analysis.posture_score     = vision_scores["posture_score"]
                analysis.eye_contact_score = vision_scores["eye_contact_score"]
                logger.info(
                    f"[Analysis] MediaPipe 실측값 사용 "
                    f"(프레임 수={vision_scores['frame_count']}, "
                    f"자세={analysis.posture_score}, 눈맞춤={analysis.eye_contact_score})"
                )
            else:
                text_avg = _avg([analysis.content_score, analysis.relevance_score, analysis.clarity_score])
                analysis.posture_score     = round(min(100, (text_avg or 75) * 0.9 + 10), 1)
                analysis.eye_contact_score = round(min(100, (text_avg or 80) * 0.85 + 12), 1)
                logger.info("[Analysis] MediaPipe 데이터 없음 — 텍스트 기반 추정값 사용")

            # ── 5) 종합 점수 ─────────────────────────────────────────────────
            analysis.total_score = _avg([
                analysis.content_score,
                analysis.relevance_score,
                analysis.clarity_score,
                analysis.speech_score,
                analysis.posture_score,
                analysis.eye_contact_score,
            ])

            # ── 6) Gemini 종합 총평 / 강점 / 개선점 ─────────────────────────
            qna_feedbacks = [
                {
                    "question": q.question_text,
                    "answer":   q.answer_text or "",
                    "feedback": (r.get("feedback", "") if isinstance(r, dict) else ""),
                }
                for q, r in zip(valid_questions, batch_results)
            ]
            summary = await generate_overall_summary_with_gemini(qna_feedbacks)
            analysis.feedback_summary = summary.get("feedback_summary", "")
            analysis.strengths        = summary.get("strengths", []) or []
            analysis.improvements     = summary.get("improvements", []) or []

            db.add(analysis)
            await db.commit()

        logger.info(f"[Analysis] interview_id={interview_id} 분석 완료")
    except Exception as e:
        logger.error(f"[Analysis] 파이프라인 치명적 오류: {e}", exc_info=True)


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
        raise HTTPException(status_code=400, detail="완료된 면접만 분석할 수 있습니다")

    background_tasks.add_task(_run_analysis_pipeline, interview_id)
    return {"message": "분석을 시작했습니다", "interview_id": interview_id, "status": "processing"}


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
        select(Analysis)
        .options(selectinload(Analysis.interview).selectinload(Interview.questions))
        .where(Analysis.interview_id == interview_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="분석 결과가 아직 없습니다. 먼저 분석을 시작하세요.")

    analysis.question_feedbacks = sorted(
        [q for q in analysis.interview.questions if q.answer_text],
        key=lambda q: q.order,
    )
    return analysis
