from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List
from core.database import get_db
from core.security import get_current_user_id
from models.interview import Interview, InterviewQuestion, InterviewStatus
from schemas.schemas import InterviewCreate, InterviewResponse, QuestionResponse, AnswerSubmit

router = APIRouter(prefix="/interviews", tags=["면접"])

# 기본 질문 세트 (다음 단계에서 DB 또는 KoBERT 기반 생성으로 교체)
DEFAULT_QUESTIONS = {
    "general": [
        "1분 자기소개를 해주세요.",
        "본인의 강점과 약점은 무엇인가요?",
        "지원 동기를 말씀해주세요.",
        "5년 후 목표는 무엇인가요?",
        "마지막으로 하고 싶은 말이 있으신가요?",
    ],
    "technical": [
        "주요 기술 스택을 소개해주세요.",
        "가장 자신 있는 프로젝트를 설명해주세요.",
        "코드 리뷰 경험이 있으신가요?",
        "어려운 기술 문제를 해결한 경험을 공유해주세요.",
        "최근 관심 있는 기술 트렌드는 무엇인가요?",
    ],
    "behavioral": [
        "팀 프로젝트에서 갈등이 생겼을 때 어떻게 해결했나요?",
        "실패한 경험과 그로부터 배운 점을 말씀해주세요.",
        "업무 우선순위를 어떻게 정하시나요?",
        "스트레스를 관리하는 방법이 있으신가요?",
        "리더십을 발휘한 경험이 있으신가요?",
    ],
}


@router.post("", response_model=InterviewResponse, status_code=201)
async def create_interview(
    body: InterviewCreate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    interview = Interview(
        user_id=user_id,
        title=body.title,
        category=body.category,
    )
    db.add(interview)
    await db.flush()

    # 카테고리에 맞는 질문 생성
    questions_list = DEFAULT_QUESTIONS.get(body.category.value, DEFAULT_QUESTIONS["general"])
    for i, q_text in enumerate(questions_list):
        db.add(InterviewQuestion(
            interview_id=interview.id,
            order=i + 1,
            question_text=q_text,
        ))

    interview.total_questions = len(questions_list)
    await db.flush()
    await db.refresh(interview)
    return interview


@router.get("", response_model=List[InterviewResponse])
async def list_interviews(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Interview)
        .where(Interview.user_id == user_id)
        .order_by(Interview.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")
    return interview


@router.get("/{interview_id}/questions", response_model=List[QuestionResponse])
async def get_questions(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # 접근 권한 확인
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    q_result = await db.execute(
        select(InterviewQuestion)
        .where(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.order)
    )
    return q_result.scalars().all()


@router.post("/{interview_id}/questions/{question_id}/answer")
async def submit_answer(
    interview_id: int,
    question_id: int,
    body: AnswerSubmit,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
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
    return {"message": "답변이 저장되었습니다"}


@router.patch("/{interview_id}/finish")
async def finish_interview(
    interview_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )
    interview = result.scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")

    interview.status = InterviewStatus.COMPLETED
    interview.ended_at = datetime.utcnow()
    return {"message": "면접이 종료되었습니다", "interview_id": interview_id}
