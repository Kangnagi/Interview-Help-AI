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
from services.llm.llama_service import generate_questions_from_resume, analyze_answer_with_llama, is_valid_question
from services.llm.question_bank import fallback_questions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interviews", tags=["면접"])

QUESTION_CACHE_FILE = "question_cache.json"
FIXED_QUESTIONS = [
    "간단한 자기소개 부탁드립니다.",
    "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?",
]
AI_QUESTIONS_PER_INTERVIEW = 3   # 고정 질문 뒤에 붙는 AI(또는 직무 기본) 질문 수

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
    # 1. 질문 먼저 준비 — Llama 생성(수 초~십수 초) 동안 DB 쓰기 잠금을 잡고 있지 않도록 면접 레코드보다 먼저 만든다
    #    (SQLite는 쓰기 잠금이 DB 전체 하나라, 예전처럼 flush 후 생성하면 그동안 다른 사용자의 저장이 막혔다)
    resume_text = body.resume_text or ""
    selected_ai = []
    try:
        resume_hash = hashlib.sha256(resume_text.encode('utf-8')).hexdigest() if resume_text else ""
        cache_entry = _question_cache.get(resume_hash) if resume_hash else None
        # 구버전 캐시(리스트 형태) 호환성 처리
        if isinstance(cache_entry, list):
            cache_entry = {"ai_questions": cache_entry[2:] if len(cache_entry) > 2 else cache_entry, "index": 0}
        if cache_entry:
            # 예전에 캐시된 깨진 질문(일본어·영어 섞임 등)은 버리고, 쓸 만한 질문이 모자라면 새로 생성
            pool = [q for q in cache_entry.get("ai_questions", []) if is_valid_question(q)]
            cache_entry = {"ai_questions": pool, "index": cache_entry.get("index", 0) % max(1, len(pool))} \
                if len(pool) >= AI_QUESTIONS_PER_INTERVIEW else None

        if cache_entry:
            logger.info("면접 생성: 캐시된 질문 풀 사용")
        elif len(resume_text.strip()) > 10:
            logger.info("면접 생성: 로컬 Llama로 질문 풀 생성")
            category_val = body.category.value if hasattr(body.category, "value") else str(body.category)
            pool = await generate_questions_from_resume(
                resume_text=resume_text,
                category=category_val,
                num_questions=8,  # 고정 2개 + AI 질문 6개 (다음 면접들에서 3개씩 돌려 씀)
            )
            if len(pool) >= AI_QUESTIONS_PER_INTERVIEW:
                cache_entry = {"ai_questions": pool, "index": 0}
            else:
                # 모자란 결과는 캐시하지 않는다 (다음 면접에서 다시 생성 시도)
                selected_ai = pool
                logger.warning(f"면접 생성: 사용할 수 있는 AI 질문 {len(pool)}개 — 직무 기본 질문으로 채움")
        else:
            logger.info("면접 생성: 지원 정보가 부족해 직무 기본 질문 사용")

        if cache_entry:
            ai_pool = cache_entry["ai_questions"]
            idx = cache_entry["index"]
            for _ in range(AI_QUESTIONS_PER_INTERVIEW):
                selected_ai.append(ai_pool[idx])
                idx = (idx + 1) % len(ai_pool)
            # 다음 면접을 위해 회전된 인덱스 저장
            cache_entry["index"] = idx
            _question_cache[resume_hash] = cache_entry
            save_question_cache(_question_cache)
    except Exception as e:
        logger.error(f"면접 생성: 질문 생성 중 예외 발생, 직무 기본 질문 사용: {e}")

    # AI 질문이 모자라면 직무 기본 질문으로 채운다 (항상 고정 2개 + 3개 = 5개)
    if len(selected_ai) < AI_QUESTIONS_PER_INTERVIEW:
        selected_ai += fallback_questions(resume_text, AI_QUESTIONS_PER_INTERVIEW - len(selected_ai), exclude=selected_ai)
    questions_list = FIXED_QUESTIONS + selected_ai

    # 2. 면접 엔티티 생성
    interview = Interview(
        user_id=user_id,
        title=body.title,
        category=body.category,
    )
    db.add(interview)
    await db.flush()  # ID 생성을 위해 flush

    # 3. 질문을 DB에 저장
    for i, q_text in enumerate(questions_list):
        new_q = InterviewQuestion(
            interview_id=interview.id,
            order=i + 1,
            question_text=q_text,
        )
        db.add(new_q)

    interview.total_questions = len(questions_list)

    # 4. 최종 커밋 및 데이터 반환
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
    """저장된 답변에 대해 AI 피드백을 즉시 생성합니다 (점수·피드백·팁 모두 로컬 Llama, Gemini 미사용)."""
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

    llama_result = await analyze_answer_with_llama(question.question_text, question.answer_text)
    logger.info(f"[Feedback] q={question_id} score={llama_result.get('score')}")

    score         = llama_result.get("score", 70)
    feedback_text = llama_result.get("feedback", "")
    tip_text      = llama_result.get("tip", "")

    question.ai_score    = score
    question.ai_feedback = feedback_text
    question.ai_model_version = llama_result.get("model_version")
    question.ai_tip = tip_text or None
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
