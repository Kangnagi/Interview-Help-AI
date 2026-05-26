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
        from services.llm.gemini_service import gemini_service, analyze_answers_batch_with_gemini

        if gemini_service.model is None:
            print(f"{FAIL} 초기화 실패 - .env의 GEMINI_API_KEY 확인 필요")
            return False
        print(f"{PASS} 모델 초기화 성공 ({gemini_service.model_name})")

        # 즉시 피드백
        print("\n[즉시 피드백 테스트]")
        feedback = await gemini_service.generate_question_feedback(
            SAMPLE_QUESTION, SAMPLE_ANSWER, company="테스트", job="백엔드 개발자"
        )
        print(f"  → {feedback[:120]}{'...' if len(feedback) > 120 else ''}")

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
# 3. MediaPipe
# ─────────────────────────────────────────────────────────
async def test_mediapipe() -> bool:
    section("3. MediaPipe")
    try:
        from services.vision.mediapipe_service import mediapipe_service

        await mediapipe_service.initialize()

        if not mediapipe_service._initialized:
            print(f"{WARN}초기화 실패 - stub 모드 동작 중")
            print("  pip install mediapipe opencv-python 후 재시도")
            return False
        print(f"{PASS} 초기화 성공 (FaceDetection + FaceMesh + Pose)")

        # 빈 프레임으로 분석 테스트
        print("\n[프레임 분석 테스트 (검은 화면)]")
        try:
            import numpy as np
            import cv2
            dummy = np.zeros((480, 640, 3), dtype=np.uint8)
            _, encoded = cv2.imencode(".jpg", dummy)
            result = mediapipe_service.analyze_frame_sync(encoded.tobytes())
            print(f"  eye_contact : {result['eye_contact']}")
            print(f"  posture_ok  : {result['posture_ok']}")
            print(f"  head_pose   : {result['head_pose']}")
            print(f"  (얼굴 미감지 시 기본값 반환 - 정상)")
        except ImportError:
            print(f"{WARN}numpy/cv2 없음 - 프레임 테스트 건너뜀")

        return True
    except Exception as e:
        print(f"{FAIL} 오류: {e}")
        return False


# ─────────────────────────────────────────────────────────
# 4. Whisper
# ─────────────────────────────────────────────────────────
async def test_whisper() -> bool:
    section("4. Whisper STT")
    try:
        from services.voice.whisper_service import whisper_service

        print(f"모델 로딩 중... (model_size: {__import__('core.config', fromlist=['settings']).settings.WHISPER_MODEL_SIZE})")
        await whisper_service.load_model()

        if whisper_service._model is None:
            print(f"{FAIL} 모델 로드 실패 - ffmpeg 설치 및 openai-whisper 확인")
            print("  ffmpeg: https://ffmpeg.org/download.html (PATH에 추가 필요)")
            return False
        print(f"{PASS} 모델 로드 성공")

        # 실제 오디오 파일이 있으면 STT 테스트
        test_audio = "./uploads/test_audio.webm"
        if os.path.exists(test_audio):
            print(f"\n[STT 테스트: {test_audio}]")
            result = await whisper_service.transcribe(test_audio)
            print(f"  인식 결과: {result.get('text', '(없음)')}")
        else:
            print(f"\n{WARN}STT 테스트 오디오 없음 ({test_audio})")
            print("  모델 로드만 확인됨 - 실제 오디오로는 정상 동작 예상")

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

        from services.voice.whisper_service import whisper_service
        analyze_result = await whisper_service.analyze_speech("./uploads/nonexistent.webm")
        print(f"  파일 없음 fallback: {analyze_result}")

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
    results["Whisper STT"] = await test_whisper()
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
