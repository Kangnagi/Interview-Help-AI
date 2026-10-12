"""
자기소개서(이력서) DB 모델 — Resume

예전엔 브라우저(localStorage)에만 저장해서 다른 PC · 브라우저에서 로그인하면 자기소개서가 없었다.
이제 계정에 저장해 어디서 로그인해도 같은 자기소개서가 보인다.

ref_id: 화면 주소(/resume/{ref_id})와 면접의 interviews.resume_ref_id에 쓰는 문자열 ID.
        브라우저에 있던 자기소개서를 옮겨 올 때 예전 ID를 그대로 써서, 이미 한 면접 기록과 계속 이어지게 한다.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from core.database import Base


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("user_id", "ref_id", name="uq_resume_user_ref"),)

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 소유자
    ref_id            = Column(String(40), nullable=False)       # 화면 · 면접 기록에서 쓰는 ID
    title             = Column(String(200), nullable=False)      # 자기소개서 제목
    company_name      = Column(String(200), nullable=True)       # 지원 회사
    job_title         = Column(String(200), nullable=True)       # 지원 직무
    job_description   = Column(Text, nullable=True)              # 직무 수행 업무
    ideal_candidate   = Column(Text, nullable=True)              # 인재상 (선택)
    self_introduction = Column(Text, nullable=True)              # 자기소개서 본문 (선택) — 키워드 질문에 쓴다
    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="resumes")
