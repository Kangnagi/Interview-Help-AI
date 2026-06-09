import json
import logging
import os
from datetime import datetime
import hashlib
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from core.database import get_db
from core.security import get_current_user_id
from models.interview import Interview, InterviewQuestion, InterviewStatus
from schemas.schemas import InterviewCreate, InterviewResponse
from services.llm.gemini_service import generate_questions_from_resume
from services.llm.kobert_service import kobert_service


def _generate_local_feedback(kobert: dict, answer: str) -> dict:
    """KoBERT 점수 기반 로컬 피드백 생성 (Gemini API 호출 없음)."""
    status = kobert.get("status", "error")

    if status != "success":
        # KoBERT 미로드 시 텍스트 길이 기반 휴리스틱
        length = len((answer or "").strip())
        if length < 10:
            score = 30
        elif length < 50:
            score = 55
        elif length < 200:
            score = 75
        else:
            score = 85
        return {
            "score": score,
            "feedback": "1. 답변이 저장되었습니다.\n2. 면접 종료 후 종합 분석에서 상세 Gemini 피드백을 확인하세요.",
            "tip": "STAR 기법(상황→과제→행동→결과)으로 구조화하면 답변의 설득력이 높아집니다.",
        }

    relevance = kobert.get("relevance_score", 0.0)
    content   = kobert.get("content_score",   0.0)
    clarity   = kobert.get("clarity_score",   0.0)

    # 가중 평균 (관련성 40% · 내용 35% · 명확성 25%)
    score = round(relevance * 0.4 + content * 0.35 + clarity * 0.25)
    score = max(20, min(100, score))

    lines = []
    if relevance >= 70:
        lines.append("1. 질문과의 관련성이 높은 답변입니다.")
    elif relevance >= 40:
        lines.append("1. 질문 핵심을 부분적으로 다뤘습니다. 핵심 포인트를 더 명확히 짚어주세요.")
    else:
        lines.append("1. 질문의 핵심에서 벗어났습니다. 질문을 다시 확인하고 답변 방향을 잡아보세요.")

    if content >= 70:
        lines.append("2. 답변 내용이 충실합니다.")
    elif content >= 40:
        lines.append("2. 답변이 조금 짧습니다. 구체적인 경험이나 수치를 추가해보세요.")
    else:
        lines.append("2. 답변이 너무 짧습니다. STAR 구조(상황→과제→행동→결과)로 구체화해보세요.")

    if clarity >= 70:
        lines.append("3. 표현이 명확하고 어휘가 다양합니다.")
    else:
        lines.append("3. 추임새나 반복 표현을 줄이고 더 명확하게 전달해보세요.")

    keywords = kobert.get("keywords", [])
    tip = (
        f"핵심 키워드 '{', '.join(keywords[:3])}'를 중심으로 답변을 구체화해보세요."
        if keywords else
        "STAR 기법(상황→과제→행동→결과)으로 구조화하면 답변의 설득력이 높아집니다."
    )

    return {"score": score, "feedback": "\n".join(lines), "tip": tip}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interviews", tags=["면접"])

QUESTION_CACHE_FILE = "question_cache.json"

def load_question_cache():
    if os.path.exists(QUESTION_CACHE_FILE):
        try:
            with open(QUESTION_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_question_cache(cache_data):
    try:
        with open(QUESTION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False)
    except Exception:
        pass

_question_cache = load_question_cache()

@router.post("", response_model=InterviewResponse, status_code=201)
async def create_interview(
    body: InterviewCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # 1. 면접 엔티티 생성
    interview = Interview(
        user_id=user_id,
        title=body.title,
        category=body.category,
    )
    db.add(interview)
    await db.flush()  # ID 생성을 위해 flush

    questions_list = []
    try:
        resume_hash = ""
        if body.resume_text:
            resume_hash = hashlib.sha256(body.resume_text.encode('utf-8')).hexdigest()

        if resume_hash and resume_hash in _question_cache:
            cache_entry = _question_cache[resume_hash]
            # 구버전 캐시(리스트 형태) 호환성 처리
            if isinstance(cache_entry, list):
                cache_entry = {
                    "ai_questions": cache_entry[2:] if len(cache_entry) > 2 else cache_entry,
                    "index": 0
                }
            logger.info(f"Interview {interview.id}: 캐시된 질문 풀에서 3개를 가져옵니다. (API 절약)")
        elif os.getenv("GEMINI_API_KEY") and body.resume_text and len(body.resume_text.strip()) > 10:
            logger.info(f"Interview {interview.id}: Gemini API로 질문 풀 생성을 시도합니다.")
            category_val = body.category.value if hasattr(body.category, "value") else str(body.category)
            raw_questions = await generate_questions_from_resume(
                resume_text=body.resume_text,
                category=category_val,
                num_questions=8  # 타임아웃 방지: 고정 2개 + AI 질문 6개로 축소
            )
            if raw_questions and len(raw_questions) > 2:
                cache_entry = {
                    "ai_questions": raw_questions[2:],
                    "index": 0
                }
            else:
                cache_entry = None
                logger.warning(f"Interview {interview.id}: Gemini가 질문을 반환하지 않았습니다. 폴백 로직을 사용합니다.")
        else:
            cache_entry = None
            logger.info(f"Interview {interview.id}: Gemini API 키가 없거나 자기소개서 내용이 부족하여 폴백 로직을 사용합니다.")

        if cache_entry and "ai_questions" in cache_entry:
            ai_pool = cache_entry["ai_questions"]
            idx = cache_entry.get("index", 0)

            selected_ai = []
            count_to_pick = min(3, len(ai_pool))
            for _ in range(count_to_pick):
                selected_ai.append(ai_pool[idx])
                idx = (idx + 1) % len(ai_pool)

            # 다음 면접을 위해 회전된 인덱스 저장
            cache_entry["index"] = idx
            _question_cache[resume_hash] = cache_entry
            save_question_cache(_question_cache)

            questions_list = [
                "간단한 자기소개 부탁드립니다.",
                "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?"
            ] + selected_ai

    except Exception as e:
        logger.error(f"Interview {interview.id}: Gemini 질문 생성 중 예외 발생, 폴백 로직 실행: {e}")

    # 3. AI 질문 생성에 실패한 경우, 기본 폴백 질문 사용
    if not questions_list or len(questions_list) <= 2:
        DEFAULT_QUESTIONS = [
            "간단한 자기소개 부탁드립니다.",
            "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?",
            "자기소개서에 작성하신 경험에 대해 더 자세히 설명해 주세요.",
            "지원하신 직무와 관련하여 본인만의 강점은 무엇인가요?",
            "가장 힘들었던 경험과 이를 어떻게 극복했는지 말씀해 주세요.",
        ]
        questions_list = DEFAULT_QUESTIONS[:5]

    # 4. 생성된 질문을 DB에 저장
    for i, q_text in enumerate(questions_list):
        new_q = InterviewQuestion(
            interview_id=interview.id,
            order=i + 1,
            question_text=q_text,
        )
        db.add(new_q)

    interview.total_questions = len(questions_list)

    # 5. 최종 커밋 및 데이터 반환
    await db.commit() 
    await db.refresh(interview)
    return interview


@router.get("")
async def list_interviews(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자의 모든 면접 이력과 종합 점수를 조회합니다."""
    from models.analysis import Analysis
    result = await db.execute(
        select(Interview, Analysis.total_score)
        .outerjoin(Analysis, Interview.id == Analysis.interview_id)
        .where(Interview.user_id == user_id)
        .order_by(Interview.created_at.desc())
    )
    
    data = []
    for iv, score in result.all():
        data.append({
            "id": iv.id,
            "title": iv.title,
            "category": iv.category.value if hasattr(iv.category, 'value') else iv.category,
            "status": iv.status.value if hasattr(iv.status, 'value') else iv.status,
            "total_questions": iv.total_questions,
            "created_at": iv.created_at.isoformat() if iv.created_at else None,
            "total_score": round(score, 1) if score else None
        })
    return data


# ----------------------------------------------------
# 프론트엔드 연동을 위한 추가 API 라우터
# ----------------------------------------------------

class AnswerCreate(BaseModel):
    answer_text: str

@router.get("/{interview_id}/questions")
async def get_interview_questions(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """특정 면접의 질문 목록을 가져옵니다."""
    result = await db.execute(
        select(InterviewQuestion)
        .where(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.order)
    )
    return result.scalars().all()

@router.post("/{interview_id}/questions/{question_id}/answer")
async def submit_answer(
    interview_id: int,
    question_id: int,
    body: AnswerCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """면접 질문에 대한 사용자의 답변(JSON)을 서버에 저장합니다."""
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.id == question_id,
            InterviewQuestion.interview_id == interview_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")

    question.answer_text = body.answer_text
    await db.commit()
    return {"message": "답변이 저장되었습니다"}


@router.post("/{interview_id}/questions/{question_id}/feedback")
async def get_question_feedback(
    interview_id: int,
    question_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """저장된 답변에 대해 즉시 AI 피드백을 생성합니다."""
    result = await db.execute(
        select(InterviewQuestion).where(
            InterviewQuestion.id == question_id,
            InterviewQuestion.interview_id == interview_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")
    if not question.answer_text:
        raise HTTPException(status_code=400, detail="저장된 답변이 없습니다")

    # KoBERT 로컬 분석 → Gemini API 호출 없이 즉시 반환
    kobert_result = await kobert_service.analyze_answer(question.question_text, question.answer_text)
    logger.info(f"KoBERT 분석 결과: {kobert_result}")

    result_data = _generate_local_feedback(kobert_result, question.answer_text)
    score        = result_data["score"]
    feedback_text = result_data["feedback"]
    tip_text      = result_data["tip"]

    question.ai_score    = score
    question.ai_feedback = feedback_text
    await db.commit()

    return {"score": score, "feedback": feedback_text, "tip": tip_text}

@router.patch("/{interview_id}/finish")
async def finish_interview(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """면접 상태를 완료(COMPLETED)로 변경합니다."""
    result = await db.execute(select(Interview).where(Interview.id == interview_id))
    interview = result.scalar_one_or_none()
    if interview:
        try:
            interview.status = InterviewStatus.COMPLETED
        except AttributeError:
            interview.status = "completed"
        await db.commit()
        
    return {"message": "면접이 완료되었습니다"}


@router.delete("/{interview_id}", status_code=204)
async def delete_interview(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """면접 기록과 관련된 분석 결과를 함께 삭제합니다."""
    from models.analysis import Analysis
    result = await db.execute(
        select(Interview).where(
            Interview.id == interview_id,
            Interview.user_id == user_id,
        )
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    # Analysis has no ORM cascade, so delete it explicitly first
    analysis_result = await db.execute(
        select(Analysis).where(Analysis.interview_id == interview_id)
    )
    analysis = analysis_result.scalar_one_or_none()
    if analysis:
        await db.delete(analysis)

    await db.delete(interview)
    await db.commit()


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id)
):
    """음성 파일을 업로드받아 텍스트로 변환(STT)합니다."""
    audio_bytes = await file.read()
    try:
        from services.voice.whisper_service import whisper_service
        # whisper_service에 transcribe_bytes 메서드가 구현되어 있다고 가정
        if hasattr(whisper_service, "transcribe_bytes"):
            result = await whisper_service.transcribe_bytes(audio_bytes)
            logger.info(f"🎤 [STT 분석 결과] {result}")
            text = result.get("text", "") if isinstance(result, dict) else str(result)
        else:
            text = "음성 인식을 완료했습니다. (현재 Whisper 모델 연동 대기 중)"
        return {"text": text}
    except Exception as e:
        logger.error(f"STT 변환 중 오류: {e}")
        return {"text": f"음성 변환 실패: {str(e)}"}
