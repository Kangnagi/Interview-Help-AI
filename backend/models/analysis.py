"""
분석 결과 DB 모델 — Analysis

Interview와 1:1 관계.
면접 1건당 분석 결과 1건이 생성됨.

점수 출처:
  content_score / relevance_score / clarity_score  → KoBERT (답변 텍스트 분석)
  speech_score / speech_pace / filler_word_count    → Whisper + Librosa (음성 분석)
  posture_score / eye_contact_score / expression_data → MediaPipe (영상 분석)
"""
from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id           = Column(Integer, primary_key=True, index=True)
    interview_id = Column(
        Integer, ForeignKey("interviews.id"),
        unique=True,   # Interview 1건 = Analysis 1건 (1:1 제약)
        nullable=False,
    )

    # ── 종합 점수 ───────────────────────────────────────────────────────────
    # 하위 점수(speech/eye_contact/posture)의 평균값으로 산출 (0~100)
    total_score = Column(Float, nullable=True)

    # ── KoBERT: 답변 내용 분석 점수 ────────────────────────────────────────
    # 현재 torch.rand() 임시값 사용 — 실제 분류 헤드 구현 필요 (TODO)
    content_score   = Column(Float, nullable=True)   # 내용 적절성 (질문에 맞는 답변인가)
    relevance_score = Column(Float, nullable=True)   # 질문 관련성 (키워드 포함 여부 등)
    clarity_score   = Column(Float, nullable=True)   # 명확성 (두괄식 구조, 불필요한 내용 배제)

    # ── Whisper + Librosa: 음성 분석 점수 ──────────────────────────────────
    speech_score      = Column(Float, nullable=True)    # 발화 종합 점수
    speech_pace       = Column(Float, nullable=True)    # 발화 속도 (단어/분, WPM)
    filler_word_count = Column(Integer, nullable=True)  # 습관어 횟수 (어, 음, 그, 저 등)

    # ── MediaPipe: 표정·자세 분석 점수 ─────────────────────────────────────
    posture_score     = Column(Float, nullable=True)   # 자세 점수 (어깨 수평도 기반)
    eye_contact_score = Column(Float, nullable=True)   # 눈맞춤 점수 (고개 정면 비율 기반)
    # 프레임별 표정 데이터 — JSON 배열 형태로 저장 (추후 py-feat 연동 시 활용)
    expression_data   = Column(JSON, nullable=True)

    # ── AI 피드백 ────────────────────────────────────────────────────────────
    feedback_summary = Column(Text, nullable=True)   # KoBERT/LLM이 생성할 종합 피드백 텍스트
    strengths        = Column(JSON, nullable=True)   # 강점 목록 (예: ["끝까지 답변 완료"])
    improvements     = Column(JSON, nullable=True)   # 개선점 목록 (예: ["구체적 사례 추가"])

    created_at = Column(DateTime, default=datetime.utcnow)

    interview = relationship("Interview", back_populates="analysis")
