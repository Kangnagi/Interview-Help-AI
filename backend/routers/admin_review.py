"""
관리자 검토 API — 사람이 AI 채점을 바로잡아 재학습용 정답 라벨을 만든다 (B2).

- 관리자: .env의 ADMIN_EMAILS에 있는 계정만 (그 외 403)
- 대상: 학습 활용에 동의한(training_consent=True) 사용자의 채점된 답변만 — 동의하지 않은 사용자의 답변 내용은 보여주지 않는다
- 우선순위: ① 사용자가 '점수 너무 높음/낮음' 또는 👎를 누른 답변 ② AI 점수가 중간대(45~74, 모델이 약한 구간) ③ 나머지
- 내보내기: 검토 완료(reviewed) 답변을 학습 데이터와 같은 형식(JSONL)으로. 내보낼 때도 동의 여부를 다시 확인한다.
"""
import json
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import get_db
from core.security import get_current_user_id
from models.feedback import AnswerRating, AnswerReview
from models.interview import Interview, InterviewQuestion
from models.user import User
from services.llm.llama_service import MAX_ANSWER_CHARS, SCORING_SYSTEM_PROMPT

router = APIRouter(prefix="/admin", tags=["관리자 검토"])

MID_RANGE = (45, 74)        # 모델이 잘 못 맞히는 중간 점수대 — 검토 우선순위를 높인다
CANDIDATE_LIMIT = 5000      # 한 번에 훑는 최대 답변 수


async def require_admin(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if not user or (user.email or "").lower() not in settings.admin_emails:
        raise HTTPException(status_code=403, detail="관리자만 사용할 수 있습니다")
    return user


# ── 스키마 ───────────────────────────────────────────────────────────────────
class QueueItem(BaseModel):
    question_id: int
    interview_id: int
    question_text: str
    answer_preview: str
    ai_score: Optional[float]
    model_version: Optional[str]
    user_rating: Optional[str]          # too_high | ok | too_low
    user_helpful: Optional[bool]
    priority: int                       # 2=사용자 부정 평가, 1=중간 점수대, 0=그 외
    review_status: Optional[str]        # None=검토 전 | reviewed | skipped
    human_score: Optional[int]
    created_at: Optional[datetime]


class QueueResponse(BaseModel):
    total: int
    items: List[QueueItem]


class ItemDetail(BaseModel):
    question_id: int
    interview_id: int
    question_text: str
    answer_text: str
    ai_score: Optional[float]
    ai_feedback: Optional[str]
    ai_tip: Optional[str]
    model_version: Optional[str]
    user_rating: Optional[str]
    user_helpful: Optional[bool]
    user_comment: Optional[str]
    review_status: Optional[str]
    human_score: Optional[int]
    human_feedback: Optional[str]
    human_tip: Optional[str]
    note: Optional[str]


class ReviewUpdate(BaseModel):
    status: Literal["reviewed", "skipped"] = "reviewed"
    human_score: Optional[int] = Field(default=None, ge=0, le=100)
    human_feedback: Optional[str] = Field(default=None, max_length=3000)
    human_tip: Optional[str] = Field(default=None, max_length=500)
    note: Optional[str] = Field(default=None, max_length=1000)


# ── 공통 ─────────────────────────────────────────────────────────────────────
async def _consented_questions(db: AsyncSession) -> list:
    """동의한 사용자의 채점된 답변 (평가·검토 함께 로드)."""
    rows = (await db.execute(
        select(InterviewQuestion)
        .join(Interview, InterviewQuestion.interview_id == Interview.id)
        .join(User, Interview.user_id == User.id)
        .where(User.training_consent.is_(True), InterviewQuestion.answer_text.isnot(None),
               InterviewQuestion.ai_score.isnot(None))
        .options(selectinload(InterviewQuestion.ratings), selectinload(InterviewQuestion.review))
        .order_by(InterviewQuestion.created_at.desc())
        .limit(CANDIDATE_LIMIT)
    )).scalars().all()
    return [q for q in rows if (q.answer_text or "").strip()]


def _owner_rating(q: InterviewQuestion) -> Optional[AnswerRating]:
    return q.ratings[0] if q.ratings else None


def _priority(q: InterviewQuestion) -> int:
    r = _owner_rating(q)
    if r and (r.score_rating in ("too_high", "too_low") or r.feedback_helpful is False):
        return 2
    if q.ai_score is not None and MID_RANGE[0] <= q.ai_score <= MID_RANGE[1]:
        return 1
    return 0


async def _get_consented_question(question_id: int, db: AsyncSession) -> InterviewQuestion:
    q = (await db.execute(
        select(InterviewQuestion)
        .join(Interview, InterviewQuestion.interview_id == Interview.id)
        .join(User, Interview.user_id == User.id)
        .where(InterviewQuestion.id == question_id, User.training_consent.is_(True))
        .options(selectinload(InterviewQuestion.ratings), selectinload(InterviewQuestion.review))
    )).scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="검토할 수 없는 답변입니다 (없거나 학습 활용 미동의)")
    return q


def _detail(q: InterviewQuestion) -> ItemDetail:
    r, rv = _owner_rating(q), q.review
    return ItemDetail(
        question_id=q.id, interview_id=q.interview_id, question_text=q.question_text, answer_text=q.answer_text or "",
        ai_score=q.ai_score, ai_feedback=q.ai_feedback, ai_tip=q.ai_tip, model_version=q.ai_model_version,
        user_rating=r.score_rating if r else None, user_helpful=r.feedback_helpful if r else None,
        user_comment=r.comment if r else None,
        review_status=rv.status if rv else None, human_score=rv.human_score if rv else None,
        human_feedback=rv.human_feedback if rv else None, human_tip=rv.human_tip if rv else None,
        note=rv.note if rv else None,
    )


# ── 엔드포인트 ───────────────────────────────────────────────────────────────
@router.get("/me")
async def admin_me(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """화면에서 '관리자 검토' 메뉴를 보여줄지 판단용."""
    user = await db.get(User, user_id)
    return {"is_admin": bool(user and (user.email or "").lower() in settings.admin_emails)}


@router.get("/review/stats")
async def review_stats(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    questions = await _consented_questions(db)
    reviews = [q.review for q in questions if q.review]
    diffs = [abs(r.human_score - r.model_score) for r in reviews
             if r.status == "reviewed" and r.human_score is not None and r.model_score is not None]
    consenting_users = len((await db.execute(select(User.id).where(User.training_consent.is_(True)))).all())

    # 모델 버전별 사용자 평가 — 전체 사용자 대상이지만 개수만 집계 (답변 내용 없음)
    by_model = {}
    for rating in (await db.execute(select(AnswerRating))).scalars().all():
        m = by_model.setdefault(rating.model_version or "알 수 없음",
                                {"model_version": rating.model_version or "알 수 없음", "total": 0, "too_high": 0, "ok": 0,
                                 "too_low": 0, "helpful": 0, "not_helpful": 0})
        m["total"] += 1
        if rating.score_rating in ("too_high", "ok", "too_low"):
            m[rating.score_rating] += 1
        if rating.feedback_helpful is True:
            m["helpful"] += 1
        elif rating.feedback_helpful is False:
            m["not_helpful"] += 1

    return {
        "consenting_users": consenting_users,
        "eligible_answers": len(questions),
        "reviewed": sum(r.status == "reviewed" for r in reviews),
        "skipped": sum(r.status == "skipped" for r in reviews),
        "pending": sum(1 for q in questions if not q.review),
        "pending_priority": sum(1 for q in questions if not q.review and _priority(q) > 0),
        "mean_abs_diff": round(sum(diffs) / len(diffs), 1) if diffs else None,
        "ratings_by_model": sorted(by_model.values(), key=lambda m: -m["total"]),
    }


@router.get("/review/queue", response_model=QueueResponse)
async def review_queue(
    status: Literal["pending", "reviewed", "skipped", "all"] = "pending",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    questions = await _consented_questions(db)
    if status == "pending":
        questions = [q for q in questions if not q.review]
        questions.sort(key=_priority, reverse=True)      # 안정 정렬 → 같은 우선순위 안에서는 최신순 유지
    elif status != "all":
        questions = [q for q in questions if q.review and q.review.status == status]

    items = []
    for q in questions[offset:offset + limit]:
        r, rv = _owner_rating(q), q.review
        items.append(QueueItem(
            question_id=q.id, interview_id=q.interview_id, question_text=q.question_text,
            answer_preview=(q.answer_text or "")[:80], ai_score=q.ai_score, model_version=q.ai_model_version,
            user_rating=r.score_rating if r else None, user_helpful=r.feedback_helpful if r else None,
            priority=_priority(q), review_status=rv.status if rv else None,
            human_score=rv.human_score if rv else None, created_at=q.created_at,
        ))
    return QueueResponse(total=len(questions), items=items)


@router.get("/review/items/{question_id}", response_model=ItemDetail)
async def review_item(question_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return _detail(await _get_consented_question(question_id, db))


@router.put("/review/items/{question_id}", response_model=ItemDetail)
async def save_review(
    question_id: int,
    body: ReviewUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    q = await _get_consented_question(question_id, db)
    if body.status == "reviewed" and body.human_score is None:
        raise HTTPException(status_code=422, detail="검토 완료로 저장하려면 점수를 입력하세요")

    review = q.review or AnswerReview(question_id=q.id, reviewer_id=admin.id)
    review.reviewer_id = admin.id
    review.status = body.status
    review.human_score = body.human_score
    review.human_feedback = (body.human_feedback or "").strip() or None
    review.human_tip = (body.human_tip or "").strip() or None
    review.note = (body.note or "").strip() or None
    review.model_score = q.ai_score
    review.model_version = q.ai_model_version
    if q.review is None:
        db.add(review)
        q.review = review
    await db.commit()
    return _detail(q)


@router.get("/review/export")
async def export_reviews(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """검토 완료 답변을 학습 데이터 형식(JSONL)으로 내려준다 — 지금 시점에도 동의 중인 사용자 것만."""
    lines = []
    for q in await _consented_questions(db):
        rv = q.review
        if not rv or rv.status != "reviewed" or rv.human_score is None:
            continue
        feedback = rv.human_feedback or q.ai_feedback
        tip = rv.human_tip or q.ai_tip
        if not feedback or not tip:
            continue   # 팁이 저장되기 전(예전) 답변은 팁을 직접 입력해야 내보낼 수 있다
        label = {"score": rv.human_score, "feedback": feedback, "tip": tip}
        lines.append(json.dumps({
            "messages": [
                {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                {"role": "user", "content": f"면접 질문: {q.question_text}\n지원자 답변: {q.answer_text.strip()[:MAX_ANSWER_CHARS]}"},
                {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
            ],
            "meta": {"source": "human_review", "question_id": q.id, "model_score": rv.model_score,
                     "model_version": rv.model_version, "reviewed_at": (rv.updated_at or rv.created_at).isoformat()},
        }, ensure_ascii=False))
    filename = f"human_reviews_{datetime.utcnow():%Y%m%d}.jsonl"
    return Response("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
