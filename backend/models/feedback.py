"""
사용자 평가 · 관리자 검토 DB 모델 — AnswerRating, AnswerReview

면접 결과 화면에서 사용자가 질문별 AI 채점에 남긴 평가("점수가 너무 높음/적절/너무 낮음", 피드백 도움 여부).
재학습 때 사람이 검토할 답변을 고르고(모델이 틀리기 쉬운 답변), 모델 버전별 만족도를 비교하는 데 쓴다.

테이블 관계:
  interview_questions (1) ──< answer_ratings (N)   (질문 1개당 사용자 1명이 1개 — 다시 누르면 덮어씀)
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base

SCORE_RATINGS = ("too_high", "ok", "too_low")


class AnswerRating(Base):
    __tablename__ = "answer_ratings"
    __table_args__ = (UniqueConstraint("question_id", "user_id", name="uq_answer_rating_question_user"),)

    id               = Column(Integer, primary_key=True, index=True)
    question_id      = Column(Integer, ForeignKey("interview_questions.id"), nullable=False, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    score_rating     = Column(String, nullable=True)      # too_high | ok | too_low (SCORE_RATINGS)
    feedback_helpful = Column(Boolean, nullable=True)     # 피드백이 도움이 됐는지 (선택)
    comment          = Column(Text, nullable=True)        # 자유 의견 (선택, 500자 이내)
    model_score      = Column(Float, nullable=True)       # 평가 시점에 화면에 보였던 AI 점수
    model_version    = Column(String, nullable=True)      # 그 점수를 매긴 모델
    created_at       = Column(DateTime, default=datetime.utcnow)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    question = relationship("InterviewQuestion", back_populates="ratings")


REVIEW_STATUSES = ("reviewed", "skipped")


class AnswerReview(Base):
    """관리자 검토 결과 — 사람이 정한 '올바른 점수·피드백·팁'. 재학습 데이터(정답 라벨)가 된다.

    답변 1개당 1개 (다시 저장하면 덮어씀). skipped는 학습에 쓰기 부적절한 답변(장난, 개인정보 포함 등).
    """
    __tablename__ = "answer_reviews"

    id             = Column(Integer, primary_key=True, index=True)
    question_id    = Column(Integer, ForeignKey("interview_questions.id"), nullable=False, unique=True, index=True)
    reviewer_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    status         = Column(String, nullable=False, default="reviewed")   # reviewed | skipped (REVIEW_STATUSES)
    human_score    = Column(Integer, nullable=True)   # 사람이 정한 점수 (0~100)
    human_feedback = Column(Text, nullable=True)      # 고친 피드백 ("1. …\n2. …\n3. …")
    human_tip      = Column(Text, nullable=True)      # 고친 팁 한 문장
    note           = Column(Text, nullable=True)      # 검토 메모 (학습에는 안 씀)
    model_score    = Column(Float, nullable=True)     # 검토 시점의 AI 점수
    model_version  = Column(String, nullable=True)    # 그 점수를 매긴 모델
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    question = relationship("InterviewQuestion", back_populates="review")
