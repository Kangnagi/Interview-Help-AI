import logging
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core import audio_sessions
from core.database import get_db, AsyncSessionLocal
from core.config import settings
from core.security import get_current_user_id
from core.vision_buffer import get_and_clear_vision_scores
from models.interview import Interview, InterviewQuestion, InterviewStatus
from models.analysis import Analysis
from schemas.schemas import AnalysisResponse
from services.llm.kobert_service import kobert_service
from services.llm.llama_service import analyze_answers_batch_with_llama, generate_overall_summary_with_llama
from services.voice.librosa_service import analyze_speech, get_audio_duration
from services.vision.mediapipe_service import mediapipe_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["분석"])

# 답변이 하나도 저장되지 않은 면접의 결과 안내
NO_ANSWER_SUMMARY = (
    "저장된 답변이 없어 채점하지 못했습니다. 답변 시간에 음성 입력이 켜져 있었는지(빨간 '인식 중지' 버튼), "
    "또는 답변 칸에 글이 들어갔는지 확인한 뒤 다시 면접을 진행해 주세요."
)
NO_ANSWER_FEEDBACK = "답변이 저장되지 않았습니다. 음성 입력 또는 직접 입력으로 답변을 남겨 주세요."
NO_ANSWER_IMPROVEMENTS = [
    "답변 시간에 음성 입력이 켜져 있는지 확인하세요 (말한 내용이 답변 칸에 글자로 나타나야 저장됩니다)",
    "음성 입력이 안 되면 답변 칸에 직접 입력해도 됩니다",
]
# 분석 도중 오류 — 결과 화면은 '점수 없음 + 이 문구'를 보고 기다리기를 멈춘다
ANALYSIS_FAILED_SUMMARY = "분석 중 오류가 발생해 결과를 만들지 못했습니다. 같은 문제가 반복되면 관리자에게 알려 주세요."


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
    """분석 진입점 — 같은 면접의 중복 실행을 막고, 녹음 저장이 진행 중이면 끝날 때까지 기다린다.

    (화면은 '종료 → 분석 시작 → 결과 화면 이동' 순으로 호출하고 녹음 소켓은 화면을 떠날 때 닫혀서,
     예전엔 녹음 없이 한 번, 녹음 저장 후 한 번 — 분석이 두 번 돌았다)
    """
    if not audio_sessions.try_start_analysis(interview_id):
        logger.info(f"[Analysis] interview_id={interview_id} 이미 분석 중 — 중복 실행 건너뜀")
        return
    try:
        if not await audio_sessions.wait_for_audio(interview_id):
            logger.warning(f"[Analysis] interview_id={interview_id} 녹음 저장 대기 시간 초과 — 녹음 없이 진행")
        await _run_analysis_pipeline_impl(interview_id)
    finally:
        audio_sessions.end_analysis(interview_id)


async def _run_analysis_pipeline_impl(interview_id: int):
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
                # 예전엔 여기서 조용히 끝나서, 결과 화면이 빈 결과를 4분 동안 기다리다 '불러올 수 없음'으로 끝났다
                # → 0점 결과와 이유를 저장해 바로 보여 준다
                logger.warning(f"[Analysis] 답변이 있는 질문 없음 — 0점 결과와 안내 저장")
                for q in interview.questions:
                    q.ai_score, q.ai_feedback, q.ai_tip, q.ai_model_version = 0, NO_ANSWER_FEEDBACK, None, "rule"
                    db.add(q)
                for field in ("total_score", "content_score", "relevance_score", "clarity_score",
                              "speech_score", "posture_score", "eye_contact_score"):
                    setattr(analysis, field, 0.0)
                analysis.feedback_summary = NO_ANSWER_SUMMARY
                analysis.strengths = []
                analysis.improvements = NO_ANSWER_IMPROVEMENTS
                db.add(analysis)
                await db.commit()
                return

            # ── 2) KoBERT(관련성 보정) 및 Llama(점수·피드백)·로컬 발화 분석 ─────────
            content_scores, relevance_scores, clarity_scores = [], [], []
            speech_scores, posture_scores, eye_contact_scores = [], [], []
            speech_paces = []
            all_feedbacks = []

            # ── 2) KoBERT: 텍스트 기반 점수 (content / relevance / clarity) ──
            kobert_results = []
            for q in valid_questions:
                kobert = await kobert_service.analyze_answer(q.question_text, q.answer_text)
                kobert_results.append(kobert)
                logger.debug(f"[Analysis] KoBERT q{q.id}: {kobert.get('status')}")

            content_scores   = [k["content_score"]   for k in kobert_results if k.get("status") == "success"]
            relevance_scores = [k["relevance_score"]  for k in kobert_results if k.get("status") == "success"]
            clarity_scores   = [k["clarity_score"]    for k in kobert_results if k.get("status") == "success"]

            for q in interview.questions:
                if not q.answer_text or not q.audio_path:
                    continue
               
                # 발화 속도 기록 (WPM). 점수는 아래 로컬 발화 분석(analyze_speech)이 매긴다.
                # get_audio_duration은 동기 함수라 별도 스레드로 넘겨 이벤트 루프를 막지 않는다.
                duration = await asyncio.to_thread(get_audio_duration, q.audio_path, q.audio_start_sec, q.audio_end_sec)
                if duration > 0:
                    word_count = len(q.answer_text.split())
                    speech_paces.append(round((word_count / duration) * 60, 1))

            # ── 3) Llama 배치 채점 + 로컬 발화 분석 ─────────────────────────
            # (예전엔 스펙트로그램 이미지를 만들어 Gemini에 보냈지만, 서버에 webm 디코더가 없어 이미지 생성이
            #  실패하면서 음성 평가가 사실상 기본값으로만 채워졌다. 이제 파형을 직접 분석한다.)
            qna_list = [
                {"question": q.question_text, "answer": q.answer_text, "audio_path": q.audio_path,
                 "audio_start_sec": q.audio_start_sec, "audio_end_sec": q.audio_end_sec}
                for q in valid_questions
            ]

            # 텍스트 내용 기반 배치 분석과 오디오 기반 개별 분석을 동시에 실행합니다.
            logger.info(f"[Analysis] Llama 배치 평가(텍스트) 및 개별 음성 평가 시작")

            # 1. 텍스트 배치 분석 Task (점수·feedback 모두 로컬 Llama 채점 어댑터, Gemini 미사용)
            text_analysis_task = asyncio.create_task(analyze_answers_batch_with_llama(qna_list) if qna_list else asyncio.sleep(0, result=[]))

            # 2. 오디오 개별 분석 Tasks (녹음이 없거나 분석 불가면 None)
            speech_tasks = [
                analyze_speech(qna["audio_path"], qna["answer"], qna["audio_start_sec"], qna["audio_end_sec"])
                if qna.get("audio_path")
                else asyncio.sleep(0, result=None)
                for qna in qna_list
            ]

            # 모든 태스크 동시 대기
            batch_results, speech_results = await asyncio.gather(
                text_analysis_task,
                asyncio.gather(*speech_tasks)
            )

            # 3. 결과 병합: 텍스트 분석 결과에 음성 분석 점수와 피드백을 추가합니다.
            if isinstance(batch_results, list) and len(batch_results) == len(speech_results):
                for i in range(len(batch_results)):
                    if isinstance(batch_results[i], dict) and isinstance(speech_results[i], dict):
                        s_score = int(speech_results[i]["speech_score"])
                        batch_results[i]["speech_score"] = s_score
                        speech_scores.append(s_score)
                        logger.info(f"[Analysis] 발화 분석 q{i + 1}: {s_score}점 {speech_results[i].get('metrics')}")

                        speech_fb = speech_results[i].get("feedback", "").strip()
                        if speech_fb:
                            current_fb = batch_results[i].get("feedback", "")
                            batch_results[i]["feedback"] = f"{current_fb}\n\n[음성 코칭]\n{speech_fb}".strip()

            speech_scores_final = []
            per_q_content_scores, per_q_relevance_scores, per_q_clarity_scores = [], [], []
            for q, llama_r, kobert_r in zip(valid_questions, batch_results, kobert_results):
                if isinstance(llama_r, dict):
                    sp_score = _safe_int(llama_r.get("speech_score"))
                    fb_text  = llama_r.get("feedback", "")
                    tip_text = llama_r.get("tip") or None
                    model_version = llama_r.get("model_version")

                    # content / clarity: Llama 채점 어댑터의 종합 점수 (현재 세 항목 모두 같은 값)
                    q_content = _safe_int(llama_r.get("content_score"))
                    q_clarity = _safe_int(llama_r.get("clarity_score"))

                    # relevance: Llama(60%) + KoBERT 임베딩 유사도(40%) 혼합
                    # KoBERT 코사인 유사도는 객관적 수치라 모델의 주관 평가를 보정함
                    llama_relevance = _safe_int(llama_r.get("relevance_score"))
                    if kobert_r.get("status") == "success":
                        kobert_relevance = kobert_r["relevance_score"]
                        q_relevance = round(llama_relevance * 0.6 + kobert_relevance * 0.4)
                    else:
                        q_relevance = llama_relevance
                else:
                    # Llama 배치 결과가 없으면 KoBERT 전체 폴백
                    sp_score    = 70
                    fb_text     = ""
                    tip_text    = None
                    model_version = "kobert"
                    q_content   = kobert_r["content_score"]   if kobert_r.get("status") == "success" else 70
                    q_relevance = kobert_r["relevance_score"]  if kobert_r.get("status") == "success" else 70
                    q_clarity   = kobert_r["clarity_score"]    if kobert_r.get("status") == "success" else 70

                # 원래 speech_scores 가 2번 루프에서 채워지므로 겹치지 않게 speech_scores_final에 담음
                speech_scores_final.append(sp_score)

                # 질문별 종합 점수 = (content·40 + relevance·35 + clarity·25) / 100
                q_score = round(q_content * 0.4 + q_relevance * 0.35 + q_clarity * 0.25)

                # 답변이 없거나 질문과 아예 다른 경우 점수 상한을 30으로 제한
                # (예전엔 30으로 "고정"해서 "잘 모르겠습니다" 같은 답변이 오히려 30점으로 올라갔다)
                answer_stripped = (q.answer_text or "").strip()
                is_empty = len(answer_stripped) < 10 or len(answer_stripped.split()) < 3
                is_unrelated = (
                    kobert_r.get("status") == "success"
                    and kobert_r.get("relevance_score", 100) < 25
                )
                if is_empty or is_unrelated:
                    q_score = min(q_score, 30)
                    q_content, q_relevance, q_clarity = (min(v, 30) for v in (q_content, q_relevance, q_clarity))

                # 질문별 점수와 동일한 값으로 세부 항목 집계
                per_q_content_scores.append(q_content)
                per_q_relevance_scores.append(q_relevance)
                per_q_clarity_scores.append(q_clarity)

                # Llama 배치 분석 피드백이 없으면 단건 호출로 보완
                if not fb_text:
                    logger.warning(f"[Analysis] q{q.id} 배치 피드백 없음 — 단건 호출 시도")
                    try:
                        from services.llm.llama_service import analyze_answer_with_llama
                        single = await analyze_answer_with_llama(q.question_text, q.answer_text)
                        fb_text = single.get("feedback", "")
                        # 단건 호출 점수가 있으면 배치 점수 보정
                        if single.get("score"):
                            q_score = int(single["score"])
                            model_version = single.get("model_version", model_version)
                            tip_text = single.get("tip") or tip_text
                    except Exception as fb_err:
                        logger.error(f"[Analysis] 단건 피드백 생성 실패: {fb_err}")
                    # 단건도 실패하면 점수 기반 자동 생성
                    if not fb_text:
                        fb_text = (
                            f"1. {'질문 관련성이 높은 답변입니다.' if q_relevance >= 70 else '질문의 핵심에 더 집중하여 답변해보세요.'}\n"
                            f"2. {'답변 내용이 충실합니다.' if q_content >= 70 else 'STAR 기법(상황→과제→행동→결과)으로 답변을 구체화해보세요.'}\n"
                            f"3. {'표현이 명확합니다.' if q_clarity >= 70 else '추임새나 반복 표현을 줄이고 더 명확하게 전달해보세요.'}"
                        )

                # 각 질문 레코드에 Llama 피드백과 종합 점수 저장 (기존 즉시 피드백 덮어씀)
                q.ai_score    = max(0, min(100, q_score))
                q.ai_feedback = fb_text
                q.ai_model_version = model_version
                q.ai_tip = tip_text
                db.add(q)

            # 녹음을 분석한 발화 점수(speech_scores)가 있으면 그것을, 없으면 배치 결과의 기본값을 쓴다
            # 아까 첫루프에서 생성된 speech_scores가 더 정확함
            if speech_scores:
                analysis.speech_score = _avg(speech_scores) or 80.0
            else:
                analysis.speech_score = _avg(speech_scores_final) or 80.0
                
            analysis.speech_pace     = _avg(speech_paces)
            analysis.posture_score   = _avg(posture_scores)
            analysis.eye_contact_score = _avg(eye_contact_scores)

            # ── 4) 영역별 집계 점수 (질문별 점수와 동일한 값에서 평균) ─────────
            # per_q_* 는 루프에서 실제 q.ai_score 계산에 쓴 값 그대로를 수집한 것이므로
            # content_score 평균 × 0.4 + relevance 평균 × 0.35 + clarity 평균 × 0.25
            # ≈ 질문별 ai_score 평균이 성립해 세부 항목과 질문별 점수가 연동됨
            analysis.content_score    = _avg(per_q_content_scores)
            analysis.relevance_score  = _avg(per_q_relevance_scores)
            analysis.clarity_score    = _avg(per_q_clarity_scores)

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

            # ── 6) 종합 총평 / 강점 / 개선점 (베이스 Llama, 실패 시 규칙 기반 총평) ──
            qna_feedbacks = [
                {
                    "question":        q.question_text,
                    "answer":          q.answer_text or "",
                    "score":           q.ai_score,
                    "content_score":   per_q_content_scores[i]   if i < len(per_q_content_scores)   else None,
                    "relevance_score": per_q_relevance_scores[i] if i < len(per_q_relevance_scores) else None,
                    "clarity_score":   per_q_clarity_scores[i]   if i < len(per_q_clarity_scores)   else None,
                    "feedback":        q.ai_feedback or "",
                }
                for i, (q, r) in enumerate(zip(valid_questions, batch_results))
            ]
            summary = await generate_overall_summary_with_llama(qna_feedbacks)
            analysis.feedback_summary = summary.get("feedback_summary", "")
            analysis.strengths        = summary.get("strengths", []) or []
            analysis.improvements     = summary.get("improvements", []) or []

            db.add(analysis)
            await db.commit()

        logger.info(f"[Analysis] interview_id={interview_id} 분석 완료")
    except Exception as e:
        logger.error(f"[Analysis] 파이프라인 치명적 오류: {e}", exc_info=True)
        # 점수 없이 안내 문구만 남긴다 — 결과 화면은 '점수 없음 + 안내 문구'를 실패로 보고 기다리기를 멈춘다
        try:
            async with AsyncSessionLocal() as db:
                row = (await db.execute(select(Analysis).where(Analysis.interview_id == interview_id))).scalar_one_or_none()
                if row and row.total_score is None:
                    row.feedback_summary = ANALYSIS_FAILED_SUMMARY
                    await db.commit()
        except Exception as mark_err:
            logger.error(f"[Analysis] 실패 표시 저장 실패: {mark_err}")


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

    # 플레이스홀더 레코드를 즉시 생성해 GET 엔드포인트가 404를 반환하지 않도록 보장
    existing = await db.execute(select(Analysis).where(Analysis.interview_id == interview_id))
    if not existing.scalar_one_or_none():
        db.add(Analysis(interview_id=interview_id))
        await db.commit()

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
