from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base


class Analysis(Base):
    """면접 전체 분석 결과"""
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), unique=True, nullable=False)

    # 종합 점수 (0~100)
    total_score = Column(Float, nullable=True)

    # KoBERT: 답변 내용 분석
    content_score = Column(Float, nullable=True)       # 내용 적절성
    relevance_score = Column(Float, nullable=True)     # 질문 관련성
    clarity_score = Column(Float, nullable=True)       # 명확성

    # Whisper: 음성 분석 (나중에 Librosa 추가)
    speech_score = Column(Float, nullable=True)        # 발화 종합
    speech_pace = Column(Float, nullable=True)         # 발화 속도 (단어/분)
    filler_word_count = Column(Integer, nullable=True) # 습관어 횟수

    # MediaPipe: 표정/자세 분석 (나중에 py-feat 추가)
    posture_score = Column(Float, nullable=True)       # 자세 점수
    eye_contact_score = Column(Float, nullable=True)   # 눈맞춤 점수
    expression_data = Column(JSON, nullable=True)      # 프레임별 표정 데이터

    # 피드백
    feedback_summary = Column(Text, nullable=True)     # AI 종합 피드백
    strengths = Column(JSON, nullable=True)            # 강점 리스트
    improvements = Column(JSON, nullable=True)         # 개선점 리스트

    created_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship("Interview", back_populates="analysis")
