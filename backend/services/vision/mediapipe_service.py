"""
MediaPipe 비전 분석 서비스

역할: 웹캠 프레임(실시간) 또는 녹화 영상(사후 분석)에서 눈맞춤·고개 기울기·자세를 측정.

분석 모듈:
  FaceLandmarker — 478개 얼굴 랜드마크 → 눈맞춤·고개 방향 계산, 표정 계수(blendshapes) → 눈 감김 · 미소
  PoseLandmarker — 33개 신체 랜드마크 → 어깨 수평 여부 판단

두 가지 동작 모드:
  analyze_frame_sync() — WebSocket 실시간 분석 (동기, 매 프레임 즉시 응답)
  analyze_video()      — 면접 종료 후 영상 전체 집계 분석 (비동기)

MediaPipe/OpenCV가 설치되지 않은 경우 Stub 모드로 자동 폴백.
"""
import logging
import os
import threading
import urllib.request
import numpy as np
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)

# 어깨 랜드마크 인덱스 (MediaPipe Pose 기준)
_LEFT_SHOULDER  = 11
_RIGHT_SHOULDER = 12

# 랜드마커 동시 실행 방지 — MediaPipe Tasks 인스턴스는 여러 스레드에서 동시에 쓰기에 안전하다고 보장되지 않는다
_DETECT_LOCK = threading.Lock()

# 모델 파일 저장 경로 (서비스 파일 옆 models/ 폴더)
_MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

_MODEL_URLS = {
    "face_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models"
        "/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models"
        "/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
    ),
}


def _ensure_model(filename: str) -> str:
    """모델 파일이 없으면 다운로드하고 경로를 반환."""
    os.makedirs(_MODELS_DIR, exist_ok=True)
    path = os.path.join(_MODELS_DIR, filename)
    if not os.path.exists(path):
        logger.info(f"모델 다운로드 중: {filename}")
        urllib.request.urlretrieve(_MODEL_URLS[filename], path)
        logger.info(f"모델 다운로드 완료: {filename}")
    return path


class MediaPipeService:

    _instance: Optional["MediaPipeService"] = None
    _face_landmarker = None
    _pose_landmarker = None
    _cv2              = None
    _mp               = None
    _initialized      = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """
        MediaPipe Tasks API 초기화 — 서버 시작 시 1회 호출.

        모델 파일이 없으면 자동 다운로드 후 FaceLandmarker·PoseLandmarker 생성.
        실패 시 경고만 출력하고 Stub 모드 유지.
        """
        try:
            import mediapipe as mp
            import cv2
            from mediapipe.tasks.python.core.base_options import BaseOptions
            from mediapipe.tasks.python import vision as mp_vision

            self._mp  = mp
            self._cv2 = cv2

            face_path = _ensure_model("face_landmarker.task")
            pose_path = _ensure_model("pose_landmarker_lite.task")

            face_opts = mp_vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=face_path),
                running_mode=mp_vision.RunningMode.IMAGE,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=True,   # 눈 깜빡임 · 미소 정도 (52개 표정 계수, 0~1)
            )
            self._face_landmarker = mp_vision.FaceLandmarker.create_from_options(face_opts)

            pose_opts = mp_vision.PoseLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=pose_path),
                running_mode=mp_vision.RunningMode.IMAGE,
                num_poses=1,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._pose_landmarker = mp_vision.PoseLandmarker.create_from_options(pose_opts)

            self._initialized = True
            logger.info("MediaPipe 초기화 완료")

        except ImportError:
            logger.warning("MediaPipe 미설치 — Stub 모드로 동작합니다. pip install mediapipe opencv-python")
        except Exception as e:
            logger.error(f"MediaPipe 초기화 실패: {e}")

    def _decode_frame(self, frame_bytes: bytes):
        """
        WebSocket으로 수신한 JPEG/PNG bytes → numpy RGB 배열 변환.

        cv2.flip(bgr, 1): 좌우 반전 — 웹캠 거울 모드 보정.
        """
        cv2   = self._cv2
        nparr = np.frombuffer(frame_bytes, np.uint8)
        bgr   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        bgr = cv2.flip(bgr, 1)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def _to_mp_image(self, rgb: np.ndarray):
        """numpy RGB 배열 → MediaPipe Image 객체 변환."""
        mp = self._mp
        return mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    def _analyze_eye_contact(self, face_result) -> bool:
        """
        얼굴 랜드마크 기반 눈맞춤 여부 판단.

        코 끝(landmark 1)의 x 좌표와 양쪽 눈 외각(33, 263)의 중간 x 좌표를 비교.
        yaw < 0.08 → 정면 ±8% 이내 → 눈맞춤으로 판정.
        """
        if not face_result or not face_result.face_landmarks:
            return False
        lm        = face_result.face_landmarks[0]
        nose      = lm[1]
        left_eye  = lm[33]
        right_eye = lm[263]
        yaw = abs(nose.x - (left_eye.x + right_eye.x) / 2)
        return yaw < 0.08

    def _analyze_head_pose(self, face_result) -> dict:
        """
        고개 방향 근사 추정 — pitch(상하), yaw(좌우), roll(기울기).

        정규화된 좌표(0~1)를 퍼센트 스케일로 변환해 반환.
        """
        if not face_result or not face_result.face_landmarks:
            return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        lm        = face_result.face_landmarks[0]
        nose      = lm[1]
        chin      = lm[152]
        left_eye  = lm[33]
        right_eye = lm[263]

        pitch = (chin.y - nose.y) * 100 - 10
        yaw   = (nose.x - (left_eye.x + right_eye.x) / 2) * 100
        roll  = (right_eye.y - left_eye.y) * 100

        return {
            "pitch": round(pitch, 2),
            "yaw":   round(yaw, 2),
            "roll":  round(roll, 2),
        }

    def _blendshapes(self, face_result) -> dict:
        """얼굴 표정 계수 {이름: 0~1} — 첫 번째 얼굴만. 얼굴이 없으면 빈 dict."""
        if not face_result or not getattr(face_result, "face_blendshapes", None):
            return {}
        return {c.category_name: float(c.score) for c in face_result.face_blendshapes[0]}

    def _analyze_face_detail(self, face_result) -> dict:
        """눈 깜빡임 · 표정 (2026-10 영상 담당 mediapipe 브랜치가 화면에 보내려던 항목을 실제 측정값으로).

        eyes_closed: 양쪽 눈 감김 계수 평균 > 0.5 (이 프레임에서 눈을 감고 있음 — 깜빡임 순간 포함)
        smile:       양쪽 입꼬리 올림 계수 평균 (0~1), expression: 0.4 이상이면 'smile', 아니면 'neutral'
        """
        bs = self._blendshapes(face_result)
        if not bs:
            return {"eyes_closed": None, "smile": None, "expression": "unknown"}
        blink = (bs.get("eyeBlinkLeft", 0.0) + bs.get("eyeBlinkRight", 0.0)) / 2
        smile = (bs.get("mouthSmileLeft", 0.0) + bs.get("mouthSmileRight", 0.0)) / 2
        return {
            "eyes_closed": blink > 0.5,
            "smile":       round(smile, 2),
            "expression":  "smile" if smile >= 0.4 else "neutral",
        }

    def _frame_result(self, face_result, pose_result) -> dict:
        """실시간 프레임 한 장의 결과 — 화면 표시용 + 분석 집계용(core/vision_buffer)."""
        face_detected = bool(face_result and face_result.face_landmarks)
        return {
            "face_detected":  face_detected,
            "landmark_count": len(face_result.face_landmarks[0]) if face_detected else 0,
            "eye_contact":    self._analyze_eye_contact(face_result),
            "head_pose":      self._analyze_head_pose(face_result),
            "pose_detected":  bool(pose_result and pose_result.pose_landmarks),
            "posture_ok":     self._analyze_posture(pose_result),
            **self._analyze_face_detail(face_result),
        }

    def _analyze_posture(self, pose_result) -> bool:
        """
        어깨 수평 여부로 자세 양호/불량 판정.

        좌우 어깨 y 좌표 차이 > 5%이면 기울어진 것으로 판단.
        """
        if not pose_result or not pose_result.pose_landmarks:
            return True
        lm              = pose_result.pose_landmarks[0]
        left_shoulder   = lm[_LEFT_SHOULDER]
        right_shoulder  = lm[_RIGHT_SHOULDER]
        diff = abs(left_shoulder.y - right_shoulder.y)
        return diff < 0.05

    def _run_detection(self, rgb: np.ndarray):
        """RGB 배열을 MediaPipe Image로 변환 후 두 랜드마커를 실행.

        랜드마커 인스턴스 하나를 여러 사용자의 프레임(각각 별도 스레드)이 함께 쓰므로 잠금으로 한 번에 하나씩 실행한다.
        (프레임 1장 약 9ms — 초당 3장 기준 동시 사용자 수십 명까지 여유)
        """
        mp_image = self._to_mp_image(rgb)
        with _DETECT_LOCK:
            face_result = self._face_landmarker.detect(mp_image)
            pose_result = self._pose_landmarker.detect(mp_image)
        return face_result, pose_result

    def analyze_frame_sync(self, frame_bytes: bytes) -> dict:
        """단일 프레임 동기 분석 — WebSocket 실시간 루프에서 호출."""
        if not self._initialized:
            return self._stub_frame()
        try:
            rgb = self._decode_frame(frame_bytes)
            if rgb is None:
                return self._stub_frame()
            face_result, pose_result = self._run_detection(rgb)
            return self._frame_result(face_result, pose_result)
        except Exception as e:
            logger.error(f"동기 프레임 분석 오류: {e}")
            return self._stub_frame()

    async def analyze_frame(self, frame_bytes: bytes) -> dict:
        """단일 프레임 비동기 분석 — 향후 비동기 파이프라인 연동용."""
        if not self._initialized:
            return self._stub_frame()
        try:
            rgb = self._decode_frame(frame_bytes)
            if rgb is None:
                return self._stub_frame()
            face_result, pose_result = self._run_detection(rgb)
            return self._frame_result(face_result, pose_result)
        except Exception as e:
            logger.error(f"프레임 분석 오류: {e}")
            return self._stub_frame()

    async def analyze_video(self, video_path: str) -> dict:
        """
        면접 영상 전체 분석 — 5프레임 간격 샘플링 후 평균 점수 산출.

        30fps 기준 6fps 샘플링으로 CPU 부하를 줄이면서 충분한 정밀도 유지.
        """
        if not self._initialized:
            return self._stub_video()
        try:
            cv2 = self._cv2
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return self._stub_video()

            eye_scores, posture_scores = [], []
            frame_count = 0

            while cap.isOpened():
                success, frame = cap.read()
                if not success:
                    break
                if frame_count % 5 == 0:
                    frame = cv2.flip(frame, 1)
                    rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    face_result, pose_result = self._run_detection(rgb)
                    eye_scores.append(1.0 if self._analyze_eye_contact(face_result) else 0.0)
                    posture_scores.append(1.0 if self._analyze_posture(pose_result) else 0.0)
                frame_count += 1

            cap.release()

            eye_score     = round(np.mean(eye_scores)     * 100, 1) if eye_scores     else 75.0
            posture_score = round(np.mean(posture_scores) * 100, 1) if posture_scores else 80.0

            return {
                "eye_contact_score":   eye_score,
                "posture_score":       posture_score,
                "expression_data":     [],
                "dominant_expression": "neutral",
                "total_frames":        frame_count,
            }
        except Exception as e:
            logger.error(f"비디오 분석 오류: {e}")
            return self._stub_video()

    def _stub_frame(self) -> dict:
        # face_detected None = 분석 못 함 (화면은 '카메라 연결됨'으로 둔다). 버퍼에는 쌓지 않는다 (websocket.py)
        return {
            "face_detected": None,
            "landmark_count": 0,
            "eyes_closed": None,
            "smile":       None,
            "eye_contact": True,
            "head_pose":   {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
            "expression":  "neutral",
            "posture_ok":  True,
        }

    def _stub_video(self) -> dict:
        return {
            "eye_contact_score":   75.0,
            "posture_score":       80.0,
            "expression_data":     [],
            "dominant_expression": "neutral",
        }


mediapipe_service = MediaPipeService()
