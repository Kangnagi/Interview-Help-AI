"""
MediaPipe 비전 분석 서비스

역할: 웹캠 프레임(실시간) 또는 녹화 영상(사후 분석)에서 눈맞춤·고개 기울기·자세를 측정.

분석 모듈:
  FaceDetection — 얼굴 존재 여부 감지 (실시간용)
  FaceMesh     — 468개 얼굴 랜드마크 → 눈맞춤·고개 방향 계산
  Pose         — 33개 신체 랜드마크 → 어깨 수평 여부 판단

두 가지 동작 모드:
  analyze_frame_sync() — WebSocket 실시간 분석 (동기, 매 프레임 즉시 응답)
  analyze_video()      — 면접 종료 후 영상 전체 집계 분석 (비동기)

MediaPipe/OpenCV가 설치되지 않은 경우 Stub 모드로 자동 폴백.
"""
import logging
import numpy as np
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)


class MediaPipeService:

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
        """
        MediaPipe 3개 모듈 초기화 — 서버 시작 시 1회 호출.

        ImportError 발생 시 경고만 출력하고 Stub 모드 유지.
        Stub 모드에서는 분석 결과 대신 고정 더미값을 반환함.
        """
        try:
            import mediapipe as mp
            import cv2

            self._mp  = mp
            self._cv2 = cv2
            self._mp_drawing = mp.solutions.drawing_utils

            # 웹캠 실시간 얼굴 감지 (model_selection=0: 근거리 모델)
            self._face_detection = mp.solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.5,
            )

            # 얼굴 468개 랜드마크 — 눈맞춤·고개 기울기 계산에 사용
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,    # 동영상 모드 (프레임 간 추적 활성화)
                max_num_faces=1,            # 면접자 1명만 추적
                refine_landmarks=True,      # 홍채 랜드마크 포함 (눈맞춤 정밀도 향상)
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

            # 신체 33개 랜드마크 — 어깨 좌우 높이 차이로 자세 판단
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                model_complexity=1,         # 0=빠름, 1=균형, 2=정밀 — 실시간에 1이 적합
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )

            self._initialized = True
            logger.info("MediaPipe 초기화 완료")

        except ImportError:
            logger.warning("MediaPipe 미설치 — Stub 모드로 동작합니다. pip install mediapipe opencv-python")
        except Exception as e:
            logger.error(f"MediaPipe 초기화 실패: {e}")

    def _decode_frame(self, frame_bytes: bytes):
        """
        WebSocket으로 수신한 JPEG/PNG bytes → numpy RGB 배열 변환.

        cv2.flip(bgr, 1): 좌우 반전 — 웹캠은 거울 모드로 송출하므로
        원래 방향으로 되돌려야 랜드마크 좌표가 실제 위치와 일치함.
        """
        cv2 = self._cv2
        nparr = np.frombuffer(frame_bytes, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        bgr = cv2.flip(bgr, 1)                          # 좌우 반전 (거울 보정)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)      # MediaPipe는 RGB 입력 필요

    def _analyze_eye_contact(self, face_mesh_results) -> bool:
        """
        얼굴 랜드마크 기반 눈맞춤 여부 판단.

        코 끝(landmark 1)의 x 좌표와 양쪽 눈 외각(33, 263)의 중간 x 좌표를 비교.
        고개가 정면을 향할수록 두 값의 차이(yaw)가 작아짐.
        yaw < 0.08 → 정면 ±8% 이내 → 눈맞춤으로 판정.
        """
        if not face_mesh_results or not face_mesh_results.multi_face_landmarks:
            return False
        lm = face_mesh_results.multi_face_landmarks[0].landmark
        nose      = lm[1]    # 코 끝
        left_eye  = lm[33]   # 왼쪽 눈 외각
        right_eye = lm[263]  # 오른쪽 눈 외각

        yaw = abs(nose.x - (left_eye.x + right_eye.x) / 2)
        return yaw < 0.08

    def _analyze_head_pose(self, face_mesh_results) -> dict:
        """
        고개 방향 근사 추정 — pitch(상하), yaw(좌우), roll(기울기).

        정확한 3D 추정(solvePnP)을 대신해 랜드마크 상대 좌표로 근사값을 계산.
        시각화·피드백용으로만 사용하므로 근사 정밀도로 충분.
        """
        if not face_mesh_results or not face_mesh_results.multi_face_landmarks:
            return {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}
        lm = face_mesh_results.multi_face_landmarks[0].landmark
        nose      = lm[1]
        chin      = lm[152]
        left_eye  = lm[33]
        right_eye = lm[263]

        # * 100: 정규화된 좌표(0~1)를 퍼센트 스케일로 변환
        pitch = (chin.y - nose.y) * 100 - 10   # 고개 숙임 양수, 위 들기 음수
        yaw   = (nose.x - (left_eye.x + right_eye.x) / 2) * 100
        roll  = (right_eye.y - left_eye.y) * 100

        return {
            "pitch": round(pitch, 2),
            "yaw":   round(yaw, 2),
            "roll":  round(roll, 2),
        }

    def _analyze_posture(self, pose_results) -> bool:
        """
        어깨 수평 여부로 자세 양호/불량 판정.

        좌우 어깨 y 좌표 차이 > 5%이면 기울어진 것으로 판단.
        pose_results가 없으면 (얼굴만 보이는 경우) 양호로 기본 처리.
        """
        if not pose_results or not pose_results.pose_landmarks:
            return True   # 랜드마크 감지 불가 → 판정 불가 → 양호로 처리
        mp = self._mp
        lm = pose_results.pose_landmarks.landmark
        left_shoulder  = lm[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = lm[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]

        diff = abs(left_shoulder.y - right_shoulder.y)
        return diff < 0.05   # 5% 미만 차이 = 어깨 수평 = 자세 양호

    async def analyze_frame(self, frame_bytes: bytes) -> dict:
        """단일 프레임 비동기 분석 — 향후 비동기 파이프라인 연동용."""
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
                "expression":  "neutral",   # 추후 py-feat 연동 예정
                "posture_ok":  self._analyze_posture(pose_results),
            }
        except Exception as e:
            logger.error(f"프레임 분석 오류: {e}")
            return self._stub_frame()

    def analyze_frame_sync(self, frame_bytes: bytes) -> dict:
        """
        단일 프레임 동기 분석 — WebSocket 실시간 루프에서 호출.

        WebSocket 핸들러가 이미 async이므로 내부에서 동기 함수를 직접 호출해도 무방.
        MediaPipe 자체가 동기 API이므로 별도 스레드 실행 없이 사용.
        """
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
        """
        면접 영상 전체 분석 — 프레임 단위 집계 후 평균 점수 산출.

        5프레임마다 분석하는 이유:
          30fps 영상을 매 프레임 분석하면 CPU 부하가 매우 큼.
          면접 자세·눈맞춤은 초 단위로 변하므로 6fps(5프레임 간격) 분석으로 충분.

        eye_scores / posture_scores: 각 프레임의 bool 값을 float(1.0/0.0)으로 쌓아
          최종 평균을 0~100 점수로 환산.
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

                if frame_count % 5 == 0:   # 5프레임 간격 샘플링
                    frame = cv2.flip(frame, 1)
                    rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mesh  = self._face_mesh.process(rgb)
                    pose  = self._pose.process(rgb)
                    eye_scores.append(1.0 if self._analyze_eye_contact(mesh) else 0.0)
                    posture_scores.append(1.0 if self._analyze_posture(pose) else 0.0)

                frame_count += 1

            cap.release()

            # 감지된 프레임이 없으면 중간값으로 폴백 (오류 방지)
            eye_score     = round(np.mean(eye_scores) * 100, 1)     if eye_scores     else 75.0
            posture_score = round(np.mean(posture_scores) * 100, 1) if posture_scores else 80.0

            return {
                "eye_contact_score":   eye_score,
                "posture_score":       posture_score,
                "expression_data":     [],      # 추후 py-feat 프레임별 표정 데이터
                "dominant_expression": "neutral",
                "total_frames":        frame_count,
            }

        except Exception as e:
            logger.error(f"비디오 분석 오류: {e}")
            return self._stub_video()

    def _stub_frame(self) -> dict:
        """MediaPipe 미초기화 시 반환하는 프레임 분석 더미값."""
        return {
            "eye_contact": True,
            "head_pose":   {"pitch": 0.0, "yaw": 0.0, "roll": 0.0},
            "expression":  "neutral",
            "posture_ok":  True,
        }

    def _stub_video(self) -> dict:
        """MediaPipe 미초기화 시 반환하는 영상 분석 더미값."""
        return {
            "eye_contact_score":   75.0,
            "posture_score":       80.0,
            "expression_data":     [],
            "dominant_expression": "neutral",
        }


mediapipe_service = MediaPipeService()  # 모듈 로드 시 싱글톤 인스턴스 생성
