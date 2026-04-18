"""
MediaPipe 표정/자세 분석 서비스
현재는 Stub — 다음 단계에서 실제 MediaPipe 연동

분석 항목:
- 얼굴 랜드마크: FaceMesh (눈맞춤, 고개 기울기)
- 자세: Pose (어깨, 척추 정렬)
- 손: Hands (제스처, 긴장도)

나중에 추가: py-feat (AU, 감정 분류 고도화)
"""
import logging
from typing import Optional, List
from core.config import settings

logger = logging.getLogger(__name__)


class MediaPipeService:
    """MediaPipe 비전 분석 서비스"""

    _instance: Optional["MediaPipeService"] = None
    _face_mesh = None
    _pose = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """
        다음 단계에서 구현:
        import mediapipe as mp
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            min_detection_confidence=settings.MEDIAPIPE_MIN_DETECTION_CONFIDENCE
        )
        self._pose = mp.solutions.pose.Pose()
        """
        logger.info("MediaPipe: 초기화 준비 완료 (현재 Stub)")

    async def analyze_frame(self, frame_bytes: bytes) -> dict:
        """
        단일 프레임 분석
        다음 단계: OpenCV로 디코딩 후 MediaPipe 추론
        """
        # TODO:
        # import cv2, numpy as np
        # nparr = np.frombuffer(frame_bytes, np.uint8)
        # frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # results = self._face_mesh.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        return {
            "eye_contact": True,
            "head_pose": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
            "expression": "neutral",
            "posture_ok": True,
        }

    async def analyze_video(self, video_path: str) -> dict:
        """
        면접 영상 전체 분석 — 프레임 단위 집계
        """
        logger.info(f"MediaPipe 비디오 분석 (Stub): {video_path}")

        # 더미 집계 결과
        return {
            "eye_contact_score": 75.0,
            "posture_score": 80.0,
            "expression_data": [],          # 프레임별 데이터 (나중에 채움)
            "dominant_expression": "neutral",
        }

    def analyze_frame_sync(self, frame_bytes: bytes) -> dict:
        """WebSocket 실시간 분석용 동기 버전"""
        return {
            "eye_contact": True,
            "expression": "neutral",
            "posture_ok": True,
        }


mediapipe_service = MediaPipeService()
