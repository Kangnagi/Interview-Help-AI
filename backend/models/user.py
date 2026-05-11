from sqlalchemy import Column, Integer, String, DateTime, Boolean   # DB 컬럼 타입들
from sqlalchemy.orm import relationship   # 테이블 간 관계 정의
from datetime import datetime             # 기본값으로 현재 시각 사용
from core.database import Base           # ORM 모델 베이스 클래스


class User(Base):
    __tablename__ = "users"   # DB에 생성될 테이블 이름

    id = Column(Integer, primary_key=True, index=True)                             # 자동 증가 기본키
    email = Column(String, unique=True, index=True, nullable=False)                # 이메일 (중복 불가, 빠른 조회를 위해 인덱스)
    username = Column(String, nullable=False)                                       # 사용자 표시 이름
    hashed_password = Column(String, nullable=False)                               # argon2 해시된 비밀번호 (평문 저장 금지)
    is_active = Column(Boolean, default=True)                                      # 계정 활성화 여부 (탈퇴/정지 시 False)
    created_at = Column(DateTime, default=datetime.utcnow)                        # 계정 생성 시각 (UTC)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 마지막 수정 시각 (자동 갱신)

    # 이 사용자의 면접 목록 — cascade: 사용자 삭제 시 면접 기록도 함께 삭제
    interviews = relationship("Interview", back_populates="user", cascade="all, delete-orphan")
