"""
MediaPipe 얼굴 검출(Face Detection) 서버 서비스
"""
import logging
import numpy as np
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)


class MediaPipeService:
    """MediaPipe 비전 분석 서비스"""

    _instance: Optional["MediaPipeService"] = None
    _face_detection = None
    _mp_drawing = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        try:
            import mediapipe as mp
            import cv2

            self._mp = mp
            self._cv2 = cv2
            self._mp_drawing = mp.solutions.drawing_utils

            # Face Detection 세팅 적용 (0: 가까운 얼굴 웹캠용)
            self._face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5
            )

            self._initialized = True
            logger.info("MediaPipe 얼굴 검출 서비스 초기화 완료 ✅")

        except ImportError:
            logger.warning("MediaPipe 미설치 — Stub 모드로 동작합니다. pip install mediapipe opencv-python")
        except Exception as e:
            logger.error(f"MediaPipe 초기화 실패: {e}")

    def _decode_frame(self, frame_bytes: bytes):
        """프론트엔드가 보낸 bytes ➔ OpenCV BGR 이미지로 변환 및 좌우반전"""
        cv2 = self._cv2
        nparr = np.frombuffer(frame_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return None
        
        # 화면을 좌우 반전 시켜서 거울 보는 것처럼 만듦
        image = cv2.flip(image, 1)
        return image

    async def analyze_frame(self, frame_bytes: bytes) -> Optional[bytes]:
        """비동기 버전 (WebSocket 실시간 영상 처리용)"""
        return self.analyze_frame_sync(frame_bytes)

    def analyze_frame_sync(self, frame_bytes: bytes) -> Optional[bytes]:
        """동기 버전 (얼굴을 검출하여 사각형을 그린 이미지 바이너리를 리턴)"""
        if not self._initialized:
            return frame_bytes

        try:
            cv2 = self._cv2
            
            # 1. 이미지 디코딩 및 좌우반전
            image = self._decode_frame(frame_bytes)
            if image is None:
                return frame_bytes

            # 2. BGR → RGB 변환 (MediaPipe 분석용)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 3. AI 모델로 얼굴 위치 분석
            results = self._face_detection.process(rgb_image)

            # 4. 얼굴이 검출되었다면 이미지 위에 박스/랜드마크 드로잉
            if results.detections:
                for detection in results.detections:
                    self._mp_drawing.draw_detection(image, detection)

            # 5. 그린 결과물(BGR)을 다시 웹 브라우저용 .jpg 포맷으로 압축
            success, encoded_image = cv2.imencode('.jpg', image)
            if not success:
                return frame_bytes

            # 6. 바이너리 데이터로 변환하여 프론트엔드로 전송할 준비
            return encoded_image.tobytes()

        except Exception as e:
            logger.error(f"프레임 얼굴 검출 오류: {e}")
            return frame_bytes

    async def analyze_video(self, video_path: str) -> dict:
        """비디오 파일 전체 분석용 Stub 함수 (에러 방지용 유지)"""
        return {
            "eye_contact_score": 100.0,
            "posture_score": 100.0,
            "expression_data": [],
            "dominant_expression": "neutral",
            "total_frames": 0,
        }


mediapipe_service = MediaPipeService()