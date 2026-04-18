from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from core.database import Base


class InterviewStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InterviewCategory(str, enum.Enum):
    GENERAL = "general"          # 일반 면접
    TECHNICAL = "technical"      # 기술 면접
    BEHAVIORAL = "behavioral"    # 인성 면접
    SELF_INTRO = "self_intro"    # 자기소개


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    category = Column(Enum(InterviewCategory), default=InterviewCategory.GENERAL)
    status = Column(Enum(InterviewStatus), default=InterviewStatus.PENDING)
    total_questions = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)  # 총 소요 시간
    video_path = Column(String, nullable=True)         # 녹화 파일 경로
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="interviews")
    questions = relationship("InterviewQuestion", back_populates="interview", cascade="all, delete-orphan")
    analysis = relationship("Analysis", back_populates="interview", uselist=False)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    order = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)       # Whisper로 변환된 텍스트
    audio_path = Column(String, nullable=True)      # 답변 오디오 파일
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship("Interview", back_populates="questions")
