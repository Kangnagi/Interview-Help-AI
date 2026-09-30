"""
AI 학습 활용 동의 + 질문별 AI 채점 평가 API.

- GET/PUT /users/me/training-consent : 답변(텍스트·음성)과 평가를 AI 재학습에 써도 되는지 (선택, 언제든 철회)
- GET     /interviews/{id}/ratings    : 이 면접에서 내가 남긴 질문별 평가
- PUT     /interviews/{id}/questions/{qid}/rating : 평가 저장 (다시 누르면 덮어씀)

평가는 동의 여부와 관계없이 서비스 개선 지표로 저장하고, 재학습 데이터에는 동의한 사용자의 것만 쓴다.
"""
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user_id
from models.feedback import AnswerRating
from models.interview import Interview, InterviewQuestion
from models.user import User

router = APIRouter(tags=["평가·동의"])


# ── 스키마 ───────────────────────────────────────────────────────────────────
class ConsentResponse(BaseModel):
    training_consent: Optional[bool]          # None = 아직 선택 안 함
    training_consent_at: Optional[datetime]


class ConsentUpdate(BaseModel):
    consent: bool


class RatingUpdate(BaseModel):
    score_rating: Optional[Literal["too_high", "ok", "too_low"]] = None
    feedback_helpful: Optional[bool] = None
    comment: Optional[str] = Field(default=None, max_length=500)


class RatingResponse(BaseModel):
    question_id: int
    score_rating: Optional[str]
    feedback_helpful: Optional[bool]
    comment: Optional[str]


# ── 동의 ─────────────────────────────────────────────────────────────────────
@router.get("/users/me/training-consent", response_model=ConsentResponse)
async def get_training_consent(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    return ConsentResponse(training_consent=user.training_consent, training_consent_at=user.training_consent_at)


@router.put("/users/me/training-consent", response_model=ConsentResponse)
async def update_training_consent(
    body: ConsentUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    user.training_consent = body.consent
    user.training_consent_at = datetime.utcnow()
    await db.commit()
    return ConsentResponse(training_consent=user.training_consent, training_consent_at=user.training_consent_at)


# ── 질문별 평가 ──────────────────────────────────────────────────────────────
async def _own_interview(interview_id: int, user_id: int, db: AsyncSession) -> Interview:
    interview = (await db.execute(
        select(Interview).where(Interview.id == interview_id, Interview.user_id == user_id)
    )).scalar_one_or_none()
    if not interview:
        raise HTTPException(status_code=404, detail="면접을 찾을 수 없습니다")
    return interview


@router.get("/interviews/{interview_id}/ratings", response_model=List[RatingResponse])
async def list_ratings(interview_id: int, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    await _own_interview(interview_id, user_id, db)
    rows = (await db.execute(
        select(AnswerRating)
        .join(InterviewQuestion, AnswerRating.question_id == InterviewQuestion.id)
        .where(InterviewQuestion.interview_id == interview_id, AnswerRating.user_id == user_id)
    )).scalars().all()
    return [RatingResponse(question_id=r.question_id, score_rating=r.score_rating,
                           feedback_helpful=r.feedback_helpful, comment=r.comment) for r in rows]


@router.put("/interviews/{interview_id}/questions/{question_id}/rating", response_model=RatingResponse)
async def upsert_rating(
    interview_id: int,
    question_id: int,
    body: RatingUpdate,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await _own_interview(interview_id, user_id, db)
    question = (await db.execute(
        select(InterviewQuestion).where(InterviewQuestion.id == question_id, InterviewQuestion.interview_id == interview_id)
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="질문을 찾을 수 없습니다")

    rating = (await db.execute(
        select(AnswerRating).where(AnswerRating.question_id == question_id, AnswerRating.user_id == user_id)
    )).scalar_one_or_none()
    if rating is None:
        rating = AnswerRating(question_id=question_id, user_id=user_id)
        db.add(rating)

    # 보낸 항목만 갱신 (점수 평가만 누르거나, 피드백 도움 여부만 누를 수 있게)
    for field in body.model_fields_set:
        setattr(rating, field, getattr(body, field))
    # 평가 시점에 사용자가 본 점수와 채점 모델을 함께 남긴다 (나중에 모델이 바뀌어도 비교 가능)
    rating.model_score = question.ai_score
    rating.model_version = question.ai_model_version
    await db.commit()
    return RatingResponse(question_id=question_id, score_rating=rating.score_rating,
                          feedback_helpful=rating.feedback_helpful, comment=rating.comment)
