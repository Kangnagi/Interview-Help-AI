"""
면접 관련 DB 모델 — Interview, InterviewQuestion

테이블 관계:
  users (1) ──< interviews (N) ──< interview_questions (N)

cascade="all, delete-orphan":
  부모(Interview) 삭제 시 자식(InterviewQuestion)도 자동 삭제됨.
  DB 레벨 ON DELETE CASCADE 없이도 ORM이 처리함.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from core.database import Base


# ─── Enum 정의 ────────────────────────────────────────────────────────────────

class InterviewStatus(str, enum.Enum):
    """면접 진행 상태 — DB에 문자열로 저장, Python에서도 str처럼 사용 가능"""
    PENDING     = "pending"      # 생성됨, 아직 시작 안 함
    IN_PROGRESS = "in_progress"  # 면접 진행 중
    COMPLETED   = "completed"    # 완료 (분석 가능 상태)
    CANCELLED   = "cancelled"    # 취소됨


class InterviewCategory(str, enum.Enum):
<<<<<<< Updated upstream
    """면접 유형 — 카테고리별로 다른 질문 세트 사용"""
    GENERAL    = "general"     # 일반 면접 (자기소개·지원동기 등)
    TECHNICAL  = "technical"   # 기술 면접 (스택·프로젝트·문제해결)
    BEHAVIORAL = "behavioral"  # 인성 면접 (갈등·실패·리더십 경험)
    SELF_INTRO = "self_intro"  # 자기소개서 기반 면접
=======
    GENERAL = "general"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SELF_INTRO = "self_intro"
>>>>>>> Stashed changes


# ─── Interview 테이블 ─────────────────────────────────────────────────────────

class Interview(Base):
    """
    면접 세션 단위 모델.
    한 번의 면접 = 1개의 Interview 레코드 + N개의 InterviewQuestion 레코드.
    """
    __tablename__ = "interviews"

    id              = Column(Integer, primary_key=True, index=True)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=False)
    title           = Column(String, nullable=False)
    category        = Column(Enum(InterviewCategory), default=InterviewCategory.GENERAL)
    status          = Column(Enum(InterviewStatus), default=InterviewStatus.PENDING)
<<<<<<< Updated upstream
    total_questions = Column(Integer, default=0)          # 질문 총 개수 (생성 시 자동 설정)
    duration_seconds = Column(Integer, nullable=True)     # 면접 총 소요 시간 (종료 후 계산)
    video_path      = Column(String, nullable=True)       # 녹화 파일 경로 (없으면 음성만 분석)
    created_at      = Column(DateTime, default=datetime.utcnow)
    ended_at        = Column(DateTime, nullable=True)     # PATCH /finish 호출 시 기록
=======
    total_questions = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)
    video_path       = Column(String, nullable=True)
    interview_type   = Column(String, default="practice", nullable=True)
    resume_ref_id    = Column(String, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    ended_at         = Column(DateTime, nullable=True)
>>>>>>> Stashed changes

    # ORM 관계 — 직접 쿼리 없이 interview.user, interview.questions 접근 가능
    user      = relationship("User", back_populates="interviews")
    questions = relationship(
        "InterviewQuestion",
        back_populates="interview",
        cascade="all, delete-orphan",  # Interview 삭제 시 질문도 함께 삭제
    )
    analysis  = relationship(
        "Analysis",
        back_populates="interview",
        uselist=False,   # 1:1 관계이므로 리스트가 아닌 단일 객체로 접근
    )


# ─── InterviewQuestion 테이블 ─────────────────────────────────────────────────

class InterviewQuestion(Base):
    """
    면접 질문 + 답변 단위 모델.
    question_text: 서버가 생성한 질문
    answer_text:   Whisper STT로 변환된 텍스트 또는 프론트 직접 입력값
    """
    __tablename__ = "interview_questions"

    id           = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    order        = Column(Integer, nullable=False)          # 질문 순서 (1-based)
    question_text = Column(Text, nullable=False)
<<<<<<< Updated upstream
    answer_text   = Column(Text, nullable=True)             # 답변 저장 전까지 None
    audio_path    = Column(String, nullable=True)           # 답변 오디오 파일 (Whisper 변환용)
    duration_seconds = Column(Integer, nullable=True)       # 해당 질문 답변에 걸린 시간
    created_at    = Column(DateTime, default=datetime.utcnow)
=======
    answer_text = Column(Text, nullable=True)
    audio_path = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
>>>>>>> Stashed changes

    interview = relationship("Interview", back_populates="questions")
