#!/usr/bin/env python3
"""
AI 서비스 동작 테스트 스크립트

Usage:
  cd backend
  source .venv/Scripts/activate
  python test_ai_services.py
"""
import asyncio
import sys
import os
import logging

# backend 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.WARNING,  # 서비스 내부 로그는 숨기고 테스트 결과만 표시
    format="%(levelname)s [%(name)s]: %(message)s",
)

SAMPLE_QUESTION = "자신의 가장 큰 강점과 그것을 업무에 어떻게 활용하는지 설명해주세요."
SAMPLE_ANSWER = (
    "저의 가장 큰 강점은 문제 해결 능력입니다. 이전 프로젝트에서 데이터베이스 성능 이슈가 "
    "발생했을 때, 원인을 체계적으로 분석하여 쿼리 최적화와 인덱싱을 통해 응답 시간을 70% "
    "단축시킨 경험이 있습니다. 이러한 분석적 사고방식을 활용하여 문제의 근본 원인을 파악하고 "
    "효과적인 해결책을 도출합니다."
)

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def section(title: str):
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")


# ─────────────────────────────────────────────────────────
# 1. Gemini API
# ─────────────────────────────────────────────────────────
async def test_gemini() -> bool:
    section("1. Gemini API")
    try:
        from services.llm.gemini_service import MODEL_NAME, analyze_answer_with_gemini, analyze_answers_batch_with_gemini

        print(f"{PASS} 모델 설정 확인됨: {MODEL_NAME}")

        # 즉시 피드백
        print("\n[즉시 피드백 테스트]")
        result = await analyze_answer_with_gemini(
            SAMPLE_QUESTION, SAMPLE_ANSWER
        )
        if isinstance(result, dict):
            print(f"  → 점수: {result.get('score')}")
            print(f"  → 피드백: {result.get('feedback', '')[:80]}...")

        # 배치 분석
        print("\n[배치 분석 테스트]")
        results = await analyze_answers_batch_with_gemini([
            {"question": SAMPLE_QUESTION, "answer": SAMPLE_ANSWER, "audio_image_bytes": None}
        ])
        r = results[0]
        if isinstance(r, dict):
            scores = {k: v for k, v in r.items() if k.endswith("_score")}
            print(f"  → 점수: {scores}")
            print(f"  → 피드백: {str(r.get('feedback', ''))[:80]}")
        else:
            print(f"  → 결과: {r}")

        return True
    except Exception as e:
        print(f"{FAIL} 오류: {e}")
        return False


# ─────────────────────────────────────────────────────────
# 2. KoBERT
# ─────────────────────────────────────────────────────────
async def test_kobert() -> bool:
    section("2. KoBERT")
    try:
        from services.llm.kobert_service import kobert_service

        print("모델 로딩 중... (최초 실행 시 수 분 소요)")
        await kobert_service.load_model()

        if kobert_service.model is None:
            print(f"{FAIL} 모델 로드 실패 - HuggingFace Hub 연결 또는 sentencepiece 확인")
            return False
        print(f"{PASS} 모델 로드 성공 (device: {kobert_service.device})")

        print("\n[답변 분석 테스트]")
        result = await kobert_service.analyze_answer(SAMPLE_QUESTION, SAMPLE_ANSWER)
        if result["status"] == "success":
            print(f"  relevance_score : {result['relevance_score']}")
            print(f"  content_score   : {result['content_score']}")
            print(f"  clarity_score   : {result['clarity_score']}")
            print(f"  keywords        : {result['keywords']}")
            print(f"  feedback        : {result['feedback']}")
        else:
            print(f"{FAIL} 분석 실패: {result['feedback']}")
            return False

        # 짧은 답변 vs 긴 답변 비교
        print("\n[답변 길이별 점수 비교]")
        for label, ans in [
            ("짧은 답변 (10자)", "잘 모르겠습니다."),
            ("적절한 답변 (100자+)", SAMPLE_ANSWER),
        ]:
            r = await kobert_service.analyze_answer(SAMPLE_QUESTION, ans)
            print(f"  {label}: content={r['content_score']}, relevance={r['relevance_score']}")

        return True
    except Exception as e:
        print(f"{FAIL} 오류: {e}")
        return False


# ─────────────────────────────────────────────────────────
# 3. MediaPipe (비전 분석)
# ─────────────────────────────────────────────────────────
async def test_mediapipe() -> bool:
    section("3. MediaPipe 비전 분석")
    try:
        import mediapipe as mp
        import cv2
        print(f"{PASS} mediapipe {mp.__version__} 로드 성공")
        print(f"{PASS} opencv {cv2.__version__} 로드 성공")

        from services.vision.mediapipe_service import mediapipe_service
        await mediapipe_service.initialize()

        if mediapipe_service._initialized:
            print(f"{PASS} MediaPipe 초기화 성공 (FaceLandmarker + PoseLandmarker)")

            # 더미 프레임(480x640 흑백 이미지)으로 analyze_frame 테스트
            import numpy as np
            dummy_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
            _, buf = cv2.imencode(".jpg", dummy_rgb)
            result = await mediapipe_service.analyze_frame(buf.tobytes())
            print(f"  → eye_contact : {result.get('eye_contact')}")
            print(f"  → posture_ok  : {result.get('posture_ok')}")
            print(f"  → head_pose   : {result.get('head_pose')}")
        else:
            print(f"{WARN} MediaPipe Stub 모드 (패키지 미설치 또는 모델 오류)")
            result = await mediapipe_service.analyze_frame(b"")
            print(f"  → stub 응답: {result}")

        return True
    except ImportError as e:
        print(f"{WARN} mediapipe/opencv 미설치 — Stub 모드로 동작: {e}")
        from services.vision.mediapipe_service import mediapipe_service
        result = await mediapipe_service.analyze_frame(b"")
        print(f"  → stub 응답: {result}")
        return True
    except Exception as e:
        print(f"{FAIL} 오류: {e}")
        return False


# ─────────────────────────────────────────────────────────
# 5. Librosa (음성 특징 분석)
# ─────────────────────────────────────────────────────────
async def test_librosa() -> bool:
    section("5. Librosa 음성 분석")
    try:
        import librosa
        import numpy as np
        print(f"{PASS} librosa {librosa.__version__} 로드 성공")

        # 합성 사인파로 기능 테스트
        sr = 22050
        duration = 2
        t = np.linspace(0, duration, int(sr * duration))
        y = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

        rms = librosa.feature.rms(y=y)
        energy = float(np.mean(rms))
        print(f"  합성 440Hz 신호 에너지: {energy:.4f}")

        return True
    except ImportError as e:
        print(f"{FAIL} librosa 미설치: {e}")
        return False
    except Exception as e:
        print(f"{FAIL} 오류: {e}")
        return False


# ─────────────────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────────────────
async def main():
    print("\nAI 서비스 통합 테스트")
    print("=" * 55)

    results = {}
    results["Gemini API"]  = await test_gemini()
    results["KoBERT"]      = await test_kobert()
    results["MediaPipe"]   = await test_mediapipe()
    results["Librosa"]     = await test_librosa()

    section("테스트 결과 요약")
    all_pass = True
    for name, passed in results.items():
        status = f"{PASS} 정상" if passed else f"{FAIL} 실패"
        print(f"  {name:<15} {status}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print(f"{PASS} 모든 AI 서비스 정상 동작")
    else:
        failed = [n for n, p in results.items() if not p]
        print(f"{FAIL} 실패한 서비스: {', '.join(failed)}")
        print("  위 출력의 오류 메시지를 확인하세요.")

    return 0 if all_pass else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
