"""
감점 장면 DB 모델 — InterviewScene

면접 중 1초에 2장씩 분석하던 작은 사진(320×240) 가운데, 감점 기준(시선 · 얼굴 벗어남 · 자세 · 눈 감김)에
1초 이상 걸린 장면의 앞뒤 사진 몇 장을 남겨 분석 결과 화면에서 움직이는 이미지로 보여 준다.

- 사진 파일은 UPLOAD_DIR/scenes/{interview_id}/ (웹으로 바로 열리지 않음 — 본인 확인 API로만)
- 30일이 지나면 사진 파일을 지우고 purged_at을 기록 (services/vision/scenes.py purge_expired)
- AI 학습에는 쓰지 않는다 (학습 동의와 무관)
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from core.database import Base


class InterviewScene(Base):
    __tablename__ = "interview_scenes"

    id             = Column(Integer, primary_key=True, index=True)
    interview_id   = Column(Integer, ForeignKey("interviews.id"), nullable=False, index=True)
    rank           = Column(Integer, nullable=False)          # 1 = 가장 크게 감점된 장면
    reason         = Column(String(20), nullable=False)       # away | no_face | posture | eyes_closed
    question_order = Column(Integer, nullable=True)           # 몇 번째 질문 답변 중이었는지 (모르면 None)
    at_sec         = Column(Float, nullable=True)             # 면접 화면을 연 뒤 몇 초째
    duration_sec   = Column(Float, nullable=True)             # 감점 상태가 이어진 시간
    eye_score      = Column(Float, nullable=True)             # 그 장면의 눈맞춤 평균 (0~100)
    expression_score = Column(Float, nullable=True)           # 그 장면의 표정 평균 (0~100)
    frame_count    = Column(Integer, nullable=False, default=0)
    created_at     = Column(DateTime, default=datetime.utcnow)
    purged_at      = Column(DateTime, nullable=True)          # 보관 기간이 지나 사진을 지운 시각
