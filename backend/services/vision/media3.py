import logging
import numpy as np
from typing import Optional
import os

logger = logging.getLogger(__name__)


class MediaPipeService:
    """MediaPipe 비전 분석 서비스 (최신 Tasks API 버전)"""

    _instance: Optional["MediaPipeService"] = None
    _detector = None
    _initialized = False
    _cv2 = None
    _mp = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_initialized(self):
        """최신 Tasks API 기반 동기식 초기화 보장"""
        if self._initialized:
            return

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            import cv2

            self._mp = mp
            self._cv2 = cv2

            # 📌 다운로드 받은 .task 파일 경로 지정 (환경에 맞게 수정 가능)
            model_path = os.path.join(os.getcwd(), "core", "weights", "blaze_face_short_range.tflite")
            
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"MediaPipe 모델 파일을 찾을 수 없습니다: {model_path}")

            # 최신 Tasks API 설정 정의
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceDetectorOptions(
                base_options=base_options,
                min_detection_confidence=0.5
            )
            
            # 디텍터 객체 생성
            self._detector = vision.FaceDetector.create_from_options(options)
            self._initialized = True
            logger.info("MediaPipe Tasks 얼굴 검출 서비스 초기화 완료 ✅")

        except ImportError:
            logger.critical("필수 패키지 미설치: pip install mediapipe opencv-python")
            raise RuntimeError("필수 패키지 미설치")
        except Exception as e:
            logger.error(f"MediaPipe Tasks 초기화 치명적 실패: {e}")
            raise e

    async def initialize(self):
        self._ensure_initialized()

    def _decode_frame(self, frame_bytes: bytes):
        cv2 = self._cv2
        nparr = np.frombuffer(frame_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            return None
        return cv2.flip(image, 1)

    def analyze_frame_sync(self, frame_bytes: bytes) -> Optional[bytes]:
        if not self._initialized:
            self._ensure_initialized()

        try:
            cv2 = self._cv2
            image = self._decode_frame(frame_bytes)
            if image is None:
                raise ValueError("이미지 디코딩 실패")

            # 1. BGR -> RGB 변환
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # 2. 최신 API 전용 mp.Image 객체 포맷 생성
            mp_image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb_image)

            # 3. 얼굴 검출 수행
            detection_result = self._detector.detect(mp_image)

            # 4. 검출된 좌표를 바탕으로 직접 박스 그리기 (구형 drawing_utils 대체)
            if detection_result.detections:
                for detection in detection_result.detections:
                    bbox = detection.bounding_box
                    # Tasks API의 좌표는 절대값 픽셀 크기로 제공됩니다.
                    start_point = (int(bbox.origin_x), int(bbox.origin_y))
                    end_point = (int(bbox.origin_x + bbox.width), int(bbox.origin_y + bbox.height))
                    
                    # 녹색 사각형 그리기 (BGR 기준 두께 2)
                    cv2.rectangle(image, start_point, end_point, (0, 255, 0), 2)

            # 5. 인코딩 및 바이너리 리턴
            success, encoded_image = cv2.imencode('.jpg', image)
            if not success:
                raise ValueError("JPG 인코딩 실패")

            return encoded_image.tobytes()

        except Exception as e:
            logger.error(f"프레임 얼굴 검출 오류: {e}")
            raise e


mediapipe_service = MediaPipeService()