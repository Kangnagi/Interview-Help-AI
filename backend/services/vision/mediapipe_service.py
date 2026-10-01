"""
MediaPipe 얼굴 랜드마크(Face Landmarker - Tasks API) 서버 서비스
"""

import os
import logging
import csv
import time
import asyncio
from pathlib import Path
import numpy as np
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)


class MediaPipeService:
    """MediaPipe 비전 분석 서비스"""

    _instance: Optional["MediaPipeService"] = None
    _detector = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self):
        """MediaPipe Face Landmarker 초기화"""

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            import cv2

            self._mp = mp
            self._cv2 = cv2

            # =========================================================
            # 1. 모델 파일 경로
            # =========================================================

            current_dir = os.path.dirname(__file__)

            model_path = os.path.join(
                current_dir,
                "face_landmarker.task"
            )

            # 모델이 같은 폴더에 없으면 프로젝트 루트에서도 탐색
            if not os.path.exists(model_path):

                root_model_path = os.path.abspath(
                    os.path.join(
                        current_dir,
                        "..",
                        "..",
                        "..",
                        "face_landmarker.task"
                    )
                )

                if os.path.exists(root_model_path):
                    model_path = root_model_path

                else:
                    logger.warning(
                        f"face_landmarker.task 모델 파일을 찾을 수 없습니다: "
                        f"{model_path}"
                    )
                    return

            # =========================================================
            # 2. MediaPipe Face Landmarker 옵션
            # =========================================================

            base_options = python.BaseOptions(
                model_asset_path=model_path
            )

            options = vision.FaceLandmarkerOptions(
                base_options=base_options,

                # 표정 / 눈 깜빡임 등의 Blendshape 데이터 활성화
                output_face_blendshapes=True,

                # 얼굴 1명만 분석
                num_faces=1
            )

            # =========================================================
            # 3. Face Landmarker 생성
            # =========================================================

            self._detector = (
                vision.FaceLandmarker.create_from_options(
                    options
                )
            )

            self._initialized = True

            logger.info(
                "MediaPipe Face Landmarker 서비스 초기화 완료 ✅"
            )

        except ImportError:
            logger.warning(
                "MediaPipe 미설치 — Stub 모드로 동작합니다. "
                "pip install mediapipe opencv-python"
            )

        except Exception as e:
            logger.error(
                f"MediaPipe 초기화 실패: {e}"
            )

    # =============================================================
    # 프레임 디코딩
    # =============================================================

    def _decode_frame(self, frame_bytes: bytes):
        """
        프론트엔드가 보낸 이미지 bytes를
        OpenCV BGR 이미지로 변환
        """

        cv2 = self._cv2

        nparr = np.frombuffer(
            frame_bytes,
            np.uint8
        )

        image = cv2.imdecode(
            nparr,
            cv2.IMREAD_COLOR
        )

        if image is None:
            return None

        # 좌우 반전
        image = cv2.flip(image, 1)

        return image

    # =============================================================
    # 실시간 프레임 분석
    # =============================================================

    async def analyze_frame(
        self,
        frame_bytes: bytes
    ) -> Optional[bytes]:
        """
        비동기 버전
        WebSocket 실시간 영상 처리용
        """

        return self.analyze_frame_sync(frame_bytes)

    # =============================================================
    # 랜드마크를 화면에 그리는 기능
    # =============================================================

    def analyze_frame_sync(
        self,
        frame_bytes: bytes
    ) -> Optional[bytes]:
        """
        얼굴 랜드마크를 검출하고
        얼굴 위에 랜드마크를 그린 JPG 이미지 반환
        """

        if (
            not self._initialized
            or self._detector is None
        ):
            return frame_bytes

        try:

            cv2 = self._cv2
            mp = self._mp

            # -----------------------------------------------------
            # 1. 이미지 디코딩
            # -----------------------------------------------------

            image = self._decode_frame(
                frame_bytes
            )

            if image is None:
                return frame_bytes

            # -----------------------------------------------------
            # 2. BGR → RGB
            # -----------------------------------------------------

            rgb_image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB
            )

            # -----------------------------------------------------
            # 3. MediaPipe Image 생성
            # -----------------------------------------------------

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_image
            )

            # -----------------------------------------------------
            # 4. 얼굴 랜드마크 분석
            # -----------------------------------------------------

            results = self._detector.detect(
                mp_image
            )

            # -----------------------------------------------------
            # 5. 랜드마크 그리기
            # -----------------------------------------------------

            if results.face_landmarks:

                for face_landmarks in results.face_landmarks:

                    h, w, _ = image.shape

                    for landmark in face_landmarks:

                        cx = int(
                            landmark.x * w
                        )

                        cy = int(
                            landmark.y * h
                        )

                        cv2.circle(
                            image,
                            (cx, cy),
                            1,
                            (0, 255, 0),
                            -1
                        )

            # -----------------------------------------------------
            # 6. JPG로 변환
            # -----------------------------------------------------

            success, encoded_image = cv2.imencode(
                ".jpg",
                image
            )

            if not success:
                return frame_bytes

            return encoded_image.tobytes()

        except Exception as e:

            logger.error(
                f"프레임 얼굴 검출 오류: {e}"
            )

            return frame_bytes

    # =============================================================
    # ★ 얼굴 랜드마크 + Blendshape 수치 분석
    # =============================================================

       # =============================================================
    # ★ 얼굴 랜드마크 + Blendshape + 실시간 수치 분석
    # =============================================================

    def analyze_landmarks(
        self,
        frame_bytes: bytes
    ) -> dict:
        """
        실시간 얼굴 분석

        반환 데이터:

        {
            "face_detected": True,
            "face_score": 100.0,
            "blink_score": 93.5,
            "expression_score": 76.2,
            "eye_contact_score": 87.4,
            "landmark_count": 478
        }

        ---------------------------------------------------------
        face_score
        ---------------------------------------------------------
        얼굴이 검출되면 100
        얼굴이 없으면 0

        ---------------------------------------------------------
        blink_score
        ---------------------------------------------------------
        현재 눈을 뜨고 있는 정도를 0~100으로 표시

        ---------------------------------------------------------
        expression_score
        ---------------------------------------------------------
        입 주변 Blendshape를 이용한 표정 점수

        ---------------------------------------------------------
        eye_contact_score
        ---------------------------------------------------------
        양쪽 홍채의 위치를 이용한 시선/눈맞춤 점수
        0~100
        """

        # =========================================================
        # 0. MediaPipe 초기화 확인
        # =========================================================

        if (
            not self._initialized
            or self._detector is None
        ):
            return {
                "face_detected": False,
                "face_score": 0.0,
                "blink_score": 0.0,
                "expression_score": 0.0,
                "eye_contact_score": 0.0,
                "landmark_count": 0
            }

        try:

            cv2 = self._cv2
            mp = self._mp

            # =====================================================
            # 1. 이미지 디코딩
            # =====================================================

            image = self._decode_frame(
                frame_bytes
            )

            if image is None:

                return {
                    "face_detected": False,
                    "face_score": 0.0,
                    "blink_score": 0.0,
                    "expression_score": 0.0,
                    "eye_contact_score": 0.0,
                    "landmark_count": 0
                }

            # =====================================================
            # 2. BGR → RGB
            # =====================================================

            rgb_image = cv2.cvtColor(
                image,
                cv2.COLOR_BGR2RGB
            )

            # =====================================================
            # 3. MediaPipe Image 생성
            # =====================================================

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_image
            )

            # =====================================================
            # 4. Face Landmarker 분석
            # =====================================================

            results = self._detector.detect(
                mp_image
            )

            # =====================================================
            # 5. 얼굴 미검출
            # =====================================================

            if not results.face_landmarks:

                return {
                    "face_detected": False,
                    "face_score": 0.0,
                    "blink_score": 0.0,
                    "expression_score": 0.0,
                    "eye_contact_score": 0.0,
                    "landmark_count": 0
                }

            # =====================================================
            # 얼굴 검출됨
            # =====================================================

            landmarks = results.face_landmarks[0]

            # 얼굴 검출 점수
            face_score = 100.0

            # 기본값
            blink_score = 0.0
            expression_score = 50.0
            eye_contact_score = 50.0

            # =====================================================
            # 6. 눈맞춤 / 시선 분석
            # =====================================================

            try:

                # -------------------------------------------------
                # 왼쪽 눈 양끝
                # -------------------------------------------------

                left_eye_left = landmarks[33]
                left_eye_right = landmarks[133]

                # -------------------------------------------------
                # 오른쪽 눈 양끝
                # -------------------------------------------------

                right_eye_left = landmarks[362]
                right_eye_right = landmarks[263]

                # -------------------------------------------------
                # 홍채 중심
                # -------------------------------------------------

                left_iris = landmarks[468]
                right_iris = landmarks[473]

                # -------------------------------------------------
                # 왼쪽 홍채 위치
                #
                # 0.0 = 왼쪽
                # 0.5 = 중앙
                # 1.0 = 오른쪽
                # -------------------------------------------------

                left_eye_width = max(
                    abs(
                        left_eye_right.x
                        - left_eye_left.x
                    ),
                    0.001
                )

                left_ratio = (
                    left_iris.x
                    - left_eye_left.x
                ) / left_eye_width

                # -------------------------------------------------
                # 오른쪽 홍채 위치
                # -------------------------------------------------

                right_eye_width = max(
                    abs(
                        right_eye_right.x
                        - right_eye_left.x
                    ),
                    0.001
                )

                right_ratio = (
                    right_iris.x
                    - right_eye_left.x
                ) / right_eye_width

                # -------------------------------------------------
                # 중앙에서 가까울수록 높은 점수
                # -------------------------------------------------

                left_score = (
                    1.0
                    - abs(
                        left_ratio - 0.5
                    ) * 2.0
                )

                right_score = (
                    1.0
                    - abs(
                        right_ratio - 0.5
                    ) * 2.0
                )

                # -------------------------------------------------
                # 0~1 범위 제한
                # -------------------------------------------------

                left_score = max(
                    0.0,
                    min(
                        1.0,
                        left_score
                    )
                )

                right_score = max(
                    0.0,
                    min(
                        1.0,
                        right_score
                    )
                )

                # -------------------------------------------------
                # 양쪽 눈 평균 → 0~100
                # -------------------------------------------------

                eye_contact_score = (
                    (
                        left_score
                        + right_score
                    ) / 2.0
                ) * 100.0

                eye_contact_score = max(
                    0.0,
                    min(
                        100.0,
                        eye_contact_score
                    )
                )

            except Exception as e:

                logger.warning(
                    f"눈맞춤 계산 실패: {e}"
                )

                eye_contact_score = 50.0

            # =====================================================
            # 7. Blendshape 분석
            # =====================================================

            if results.face_blendshapes:

                blendshapes = (
                    results.face_blendshapes[0]
                )

                values = {}

                # -------------------------------------------------
                # Blendshape를 dictionary로 변환
                # -------------------------------------------------

                for category in blendshapes:

                    values[
                        category.category_name
                    ] = category.score

                # =================================================
                # 7-1. 눈 깜빡임 / 눈 개방 정도
                # =================================================

                left_blink = values.get(
                    "eyeBlinkLeft",
                    0.0
                )

                right_blink = values.get(
                    "eyeBlinkRight",
                    0.0
                )

                # 양쪽 눈 평균
                blink = (
                    left_blink
                    + right_blink
                ) / 2.0

                # -------------------------------------------------
                # 눈을 뜨고 있는 정도
                #
                # 눈 감음 = 낮은 점수
                # 눈 뜸   = 높은 점수
                # -------------------------------------------------

                blink_score = (
                    1.0 - blink
                ) * 100.0

                blink_score = max(
                    0.0,
                    min(
                        100.0,
                        blink_score
                    )
                )

                # =================================================
                # 7-2. 표정 분석
                # =================================================

                smile_left = values.get(
                    "mouthSmileLeft",
                    0.0
                )

                smile_right = values.get(
                    "mouthSmileRight",
                    0.0
                )

                # 양쪽 미소 평균
                smile = (
                    smile_left
                    + smile_right
                ) / 2.0

                # -------------------------------------------------
                # 기본 50점
                # 미소가 강할수록 점수 증가
                # -------------------------------------------------

                expression_score = (
                    50.0
                    + smile * 50.0
                )

                expression_score = max(
                    0.0,
                    min(
                        100.0,
                        expression_score
                    )
                )

            # =====================================================
            # 8. 최종 결과 반환
            # =====================================================

            return {
                "face_detected": True,

                "face_score": round(
                    face_score,
                    1
                ),

                "blink_score": round(
                    blink_score,
                    1
                ),

                "expression_score": round(
                    expression_score,
                    1
                ),

                "eye_contact_score": round(
                    eye_contact_score,
                    1
                ),

                "landmark_count": len(
                    landmarks
                )
            }

        # =========================================================
        # 전체 분석 오류
        # =========================================================

        except Exception as e:

            logger.error(
                f"얼굴 랜드마크 분석 오류: {e}"
            )

            return {
                "face_detected": False,
                "face_score": 0.0,
                "blink_score": 0.0,
                "expression_score": 0.0,
                "eye_contact_score": 0.0,
                "landmark_count": 0,
                "error": str(e)
            }

    # =============================================================
    # 비디오 전체 분석
    # =============================================================

    async def analyze_video(
        self,
        video_path: str
    ) -> dict:
        """
        비디오 파일 전체 분석용

        현재는 기본 Stub 결과를 반환한다.
        """

        return {
            "eye_contact_score": 100.0,
            "posture_score": 100.0,
            "expression_data": [],
            "dominant_expression": "neutral",
            "total_frames": 0,
        }


    # =============================================================
    # 30초 웹캠 얼굴 인식 테스트
    # =============================================================

    @staticmethod
    def _find_webcam(max_index: int = 8):
        """Windows에서 사용 가능한 웹캠을 자동 탐색합니다."""
        cv2 = MediaPipeService._cv2

        for index in range(max_index):
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    print(f"[웹캠 발견] camera_index={index}")
                    return cap, index
            cap.release()

            cap = cv2.VideoCapture(index)
            if cap.isOpened():
                ok, frame = cap.read()
                if ok and frame is not None and frame.size > 0:
                    print(f"[웹캠 발견] camera_index={index}")
                    return cap, index
            cap.release()

        return None, None

    @staticmethod
    def _save_webcam_charts(records, output_dir: Path):
        """측정 데이터로 분석 PNG를 생성합니다."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as e:
            raise RuntimeError(
                "matplotlib가 없습니다. 'pip install matplotlib'을 실행하세요."
            ) from e

        times = [r["time_sec"] for r in records]
        blink = [r["blink_score"] for r in records]
        expression = [r["expression_score"] for r in records]
        landmarks = [r["landmark_count"] for r in records]
        face_rate = sum(r["face_detected"] for r in records) / len(records) * 100
        landmark_rate = sum(r["landmark_detected"] for r in records) / len(records) * 100

        plt.figure(figsize=(10, 6))
        plt.bar(
            ["Face detection", "Landmark detection"],
            [face_rate, landmark_rate],
        )
        plt.ylim(0, 100)
        plt.ylabel("Detection rate (%)")
        plt.title("MediaPipe Face Detection Test")
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "detection_summary.png", dpi=150)
        plt.close()

        plt.figure(figsize=(12, 6))
        plt.plot(times, blink, label="Blink score")
        plt.plot(times, expression, label="Expression score")
        plt.ylim(0, 100)
        plt.xlabel("Time (seconds)")
        plt.ylabel("Score")
        plt.title("Blink and Expression Over Time")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "face_metrics_over_time.png", dpi=150)
        plt.close()

        plt.figure(figsize=(12, 6))
        plt.plot(times, landmarks, label="Landmark count")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Number of landmarks")
        plt.title("Detected Landmark Count Over Time")
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(output_dir / "landmark_count_over_time.png", dpi=150)
        plt.close()

        return {
            "face_detection_rate": face_rate,
            "landmark_detection_rate": landmark_rate,
            "average_blink_score": sum(blink) / len(blink),
            "average_expression_score": sum(expression) / len(expression),
            "max_landmark_count": max(landmarks),
        }

    def run_webcam_test(
        self,
        duration=30,
        camera_index=None,
        sample_interval=0.2,
        output_dir=None,
    ):
        """
        외장/내장 웹캠을 자동 탐색하여 30초 동안 얼굴 인식을 측정합니다.
        Q 키를 누르면 조기 종료합니다.
        """
        if not self._initialized:
            self.initialize()

        cv2 = self._cv2

        if camera_index is None:
            cap, camera_index = self._find_webcam()
        else:
            cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(camera_index)

        if cap is None or not cap.isOpened():
            raise RuntimeError(
                "웹캠을 열 수 없습니다. USB 연결, Windows 카메라 권한, "
                "다른 프로그램의 카메라 사용 여부를 확인하세요."
            )

        result_dir = (
            Path(output_dir)
            if output_dir
            else Path(__file__).resolve().parent / "webcam_test_results"
        )
        result_dir.mkdir(parents=True, exist_ok=True)

        records = []
        start = time.perf_counter()
        next_sample = 0.0
        sample_no = 0

        print("\n" + "=" * 60)
        print("MediaPipe 30초 웹캠 얼굴 인식 테스트")
        print("=" * 60)
        print(f"카메라 번호: {camera_index}")
        print("웹캠을 바라보세요. 종료하려면 Q를 누르세요.")

        try:
            while True:
                ok, frame = cap.read()
                if not ok or frame is None:
                    print("[경고] 웹캠 프레임을 읽지 못했습니다.")
                    break

                elapsed = time.perf_counter() - start
                if elapsed >= duration:
                    break

                display = frame.copy()

                if elapsed >= next_sample:
                    sample_no += 1
                    encoded_ok, encoded = cv2.imencode(".jpg", frame)

                    if encoded_ok:
                        result = self.analyze_landmarks(encoded.tobytes())
                        face_detected = bool(result.get("face_detected", False))
                        landmark_count = int(result.get("landmark_count", 0) or 0)

                        records.append({
                            "sample": sample_no,
                            "time_sec": round(elapsed, 3),
                            "face_detected": int(face_detected),
                            "landmark_detected": int(landmark_count > 0),
                            "landmark_count": landmark_count,
                            "blink_score": round(float(result.get("blink_score", 0) or 0), 3),
                            "expression_score": round(float(result.get("expression_score", 0) or 0), 3),
                        })

                        status = "FACE DETECTED" if face_detected else "NO FACE"
                        cv2.putText(
                            display, status, (20, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                            (0, 255, 0) if face_detected else (0, 0, 255), 2
                        )
                        cv2.putText(
                            display, f"Landmarks: {landmark_count}", (20, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
                        )
                        cv2.putText(
                            display, f"Blink: {records[-1]['blink_score']:.1f}", (20, 105),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
                        )
                        cv2.putText(
                            display, f"Expression: {records[-1]['expression_score']:.1f}", (20, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
                        )

                    next_sample += sample_interval

                remaining = max(0, duration - elapsed)
                cv2.putText(
                    display, f"Time left: {remaining:.1f}s",
                    (20, display.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2
                )

                cv2.imshow("MediaPipe Webcam Test - Press Q to stop", display)
                if (cv2.waitKey(1) & 0xFF) in (ord("q"), ord("Q")):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

        if not records:
            raise RuntimeError("측정 데이터가 없습니다.")

        csv_path = result_dir / "webcam_face_analysis.csv"
        fields = [
            "sample", "time_sec", "face_detected", "landmark_detected",
            "landmark_count", "blink_score", "expression_score"
        ]

        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(records)

        summary = self._save_webcam_charts(records, result_dir)

        summary_path = result_dir / "test_summary.txt"
        with summary_path.open("w", encoding="utf-8") as f:
            f.write("MediaPipe Webcam Face Analysis Test\n")
            f.write("=" * 50 + "\n")
            f.write(f"Camera index: {camera_index}\n")
            f.write(f"Samples: {len(records)}\n")
            f.write(f"Face detection rate: {summary['face_detection_rate']:.2f}%\n")
            f.write(f"Landmark detection rate: {summary['landmark_detection_rate']:.2f}%\n")
            f.write(f"Average blink score: {summary['average_blink_score']:.2f}\n")
            f.write(f"Average expression score: {summary['average_expression_score']:.2f}\n")
            f.write(f"Maximum landmark count: {summary['max_landmark_count']}\n")

        print("\n[테스트 완료]")
        print(f"얼굴 검출률: {summary['face_detection_rate']:.2f}%")
        print(f"랜드마크 검출률: {summary['landmark_detection_rate']:.2f}%")
        print(f"평균 Blink: {summary['average_blink_score']:.2f}")
        print(f"평균 Expression: {summary['average_expression_score']:.2f}")
        print(f"\n결과 폴더: {result_dir}")

        return {
            "camera_index": camera_index,
            "sample_count": len(records),
            "csv_path": str(csv_path),
            "summary_path": str(summary_path),
            **summary,
        }

    async def run_webcam_test_async(
        self, duration=30, camera_index=None, sample_interval=0.2, output_dir=None
    ):
        return await asyncio.to_thread(
            self.run_webcam_test,
            duration,
            camera_index,
            sample_interval,
            output_dir,
        )


# =============================================================
# Singleton
# =============================================================

mediapipe_service = MediaPipeService()

# =============================================================
# 직접 실행: 외장/내장 웹캠 자동 탐색 → 30초 테스트 → 차트 생성
# FastAPI에서 import될 때는 실행되지 않습니다.
# =============================================================

if __name__ == "__main__":
    try:
        mediapipe_service.initialize()
        mediapipe_service.run_webcam_test(
            duration=30,
            camera_index=None,     # None이면 카메라 0~7 자동 탐색
            sample_interval=0.2,
        )
    except KeyboardInterrupt:
        print("\n테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n[오류] {e}")
        logging.exception("웹캠 테스트 오류")
