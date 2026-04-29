"""
MediaPipe 표정/자세 분석 서비스
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
    _face_mesh = None
    _pose = None
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

            # Face Detection (웹캠 실시간용)
            self._face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5
            )

            # Face Mesh (눈맞춤, 고개 기울기)
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

            # Pose (어깨, 척추 자세)
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

            self._initialized = True
            logger.info("MediaPipe 초기화 완료 ✅")

        except ImportError:
            logger.warning("MediaPipe 미설치 — Stub 모드로 동작합니다. pip install mediapipe opencv-python")
        except Exception as e:
            logger.error(f"MediaPipe 초기화 실패: {e}")

    def _decode_frame(self, frame_bytes: bytes):
        """bytes → numpy RGB 이미지"""
        cv2 = self._cv2
        nparr = np.frombuffer(frame_bytes, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        bgr = cv2.flip(bgr, 1)          # 좌우 반전 (거울 모드)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def _analyze_eye_contact(self, face_mesh_results) -> bool:
        """얼굴 랜드마크로 눈맞춤 여부 판단"""
        if not face_mesh_results or not face_mesh_results.multi_face_landmarks:
            return False
        lm = face_mesh_results.multi_face_landmarks[0].landmark
        # 코 끝(1)과 양쪽 눈 외각(33, 263) 기준으로 고개 방향 추정
        nose = lm[1]
        left_eye = lm[33]
        right_eye = lm[263]
        yaw = abs(nose.x - (left_eye.x + right_eye.x) / 2)
        return yaw < 0.08   # 정면 기준 ±8% 이내면 눈맞춤

    def _analyze_head_pose(self, face_mesh_results) -> dict:
        """고개 기울기 추정 (pitch/yaw/roll 근사값)"""
        if not face_mesh_results or not face_mesh_results.multi_face_landmarks:
            return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        lm = face_mesh_results.multi_face_landmarks[0].landmark
        nose = lm[1]
        chin = lm[152]
        left_eye = lm[33]
        right_eye = lm[263]

        pitch = (chin.y - nose.y) * 100 - 10   # 아래로 숙임 +
        yaw   = (nose.x - (left_eye.x + right_eye.x) / 2) * 100
        roll  = (right_eye.y - left_eye.y) * 100

        return {
            "pitch": round(pitch, 2),
            "yaw":   round(yaw, 2),
            "roll":  round(roll, 2),
        }

    def _analyze_posture(self, pose_results) -> bool:
        """어깨 수평 여부로 자세 판단"""
        if not pose_results or not pose_results.pose_landmarks:
            return True
        mp = self._mp
        lm = pose_results.pose_landmarks.landmark
        left_shoulder  = lm[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = lm[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]
        diff = abs(left_shoulder.y - right_shoulder.y)
        return diff < 0.05   # 5% 이상 기울면 자세 불량

    async def analyze_frame(self, frame_bytes: bytes) -> dict:
        """단일 프레임 분석 (WebSocket 실시간용)"""
        if not self._initialized:
            return self._stub_frame()

        try:
            rgb = self._decode_frame(frame_bytes)
            if rgb is None:
                return self._stub_frame()

            mesh_results = self._face_mesh.process(rgb)
            pose_results = self._pose.process(rgb)

            eye_contact = self._analyze_eye_contact(mesh_results)
            head_pose   = self._analyze_head_pose(mesh_results)
            posture_ok  = self._analyze_posture(pose_results)

            # 표정은 추후 py-feat 연동
            expression = "neutral"

            return {
                "eye_contact": eye_contact,
                "head_pose":   head_pose,
                "expression":  expression,
                "posture_ok":  posture_ok,
            }
        except Exception as e:
            logger.error(f"프레임 분석 오류: {e}")
            return self._stub_frame()

    def analyze_frame_sync(self, frame_bytes: bytes) -> dict:
        """동기 버전 (WebSocket 실시간 분석용)"""
        if not self._initialized:
            return self._stub_frame()

        try:
            rgb = self._decode_frame(frame_bytes)
            if rgb is None:
                return self._stub_frame()

            mesh_results = self._face_mesh.process(rgb)
            pose_results = self._pose.process(rgb)

            return {
                "eye_contact": self._analyze_eye_contact(mesh_results),
                "head_pose":   self._analyze_head_pose(mesh_results),
                "expression":  "neutral",
                "posture_ok":  self._analyze_posture(pose_results),
            }
        except Exception as e:
            logger.error(f"동기 프레임 분석 오류: {e}")
            return self._stub_frame()

    async def analyze_video(self, video_path: str) -> dict:
        """면접 영상 전체 분석 — 프레임 단위 집계"""
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

                # 5프레임마다 분석 (성능)
                if frame_count % 5 == 0:
                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mesh = self._face_mesh.process(rgb)
                    pose = self._pose.process(rgb)
                    eye_scores.append(1.0 if self._analyze_eye_contact(mesh) else 0.0)
                    posture_scores.append(1.0 if self._analyze_posture(pose) else 0.0)

                frame_count += 1

            cap.release()

            eye_score     = round(np.mean(eye_scores) * 100, 1) if eye_scores else 75.0
            posture_score = round(np.mean(posture_scores) * 100, 1) if posture_scores else 80.0

            return {
                "eye_contact_score":    eye_score,
                "posture_score":        posture_score,
                "expression_data":      [],
                "dominant_expression":  "neutral",
                "total_frames":         frame_count,
            }

        except Exception as e:
            logger.error(f"비디오 분석 오류: {e}")
            return self._stub_video()

    def _stub_frame(self) -> dict:
        return {
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
