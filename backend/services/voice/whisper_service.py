"""
Whisper 음성 인식 서비스

openai-whisper 모델을 사용해 WebM/WAV 오디오를 한국어 텍스트로 변환.
Librosa를 통해 음성 특징(무음 비율, 에너지)도 함께 분석.

모델 크기(WHISPER_MODEL_SIZE):
  tiny   ~ 39M  파라미터 — 빠르지만 정확도 낮음
  base   ~ 74M  파라미터 — 속도/정확도 균형 (기본값)
  small  ~ 244M 파라미터 — 한국어 정확도 높음
"""
import logging
import os
import tempfile
from typing import Optional
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)


class WhisperService:

    _instance: Optional["WhisperService"] = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def load_model(self):
        if self._model is not None:
            return
        logger.info(f"Whisper '{settings.WHISPER_MODEL_SIZE}' 모델 로딩 중...")
        try:
            import whisper
            self._model = whisper.load_model(settings.WHISPER_MODEL_SIZE)
            logger.info("Whisper 로딩 완료")
        except Exception as e:
            logger.error(f"Whisper 로딩 실패 (ffmpeg 설치 여부 확인): {e}")
            self._model = None

    async def transcribe(self, audio_path: str) -> dict:
        """오디오 파일 경로를 받아 한국어 텍스트로 변환."""
        path = Path(audio_path)
        if not path.exists():
            return {"text": "", "error": f"파일 없음: {audio_path}"}

        if self._model is None:
            logger.warning("Whisper 모델 미로드 상태 — transcribe 건너뜀")
            return {"text": "", "language": "ko", "segments": []}

        try:
            result = self._model.transcribe(
                str(path),
                language=settings.WHISPER_LANGUAGE,
                fp16=False,  # CPU 환경에서는 fp16 비활성화 필수
            )
            return {
                "text": result["text"].strip(),
                "language": result.get("language", "ko"),
                "segments": result.get("segments", []),
            }
        except Exception as e:
            logger.error(f"Whisper 변환 실패: {e}")
            return {"text": "", "error": str(e)}

    async def transcribe_bytes(self, audio_bytes: bytes) -> dict:
        """오디오 바이트를 임시 파일로 저장 후 변환."""
        if not audio_bytes:
            return {"text": "", "error": "빈 오디오 데이터"}

        if self._model is None:
            return {"text": "", "language": "ko", "segments": []}

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            return await self.transcribe(tmp_path)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    async def analyze_speech(self, audio_path: str) -> dict:
        """
        Librosa로 음성 특징 분석.
        silence_ratio 기반으로 speech_score 산출.
        """
        try:
            from services.voice.librosa_service import AudioAnalyzer
            features = AudioAnalyzer.analyze_features(audio_path)
            if features:
                silence_ratio = features.get("silence_ratio", 0.15)
                # 무음 비율이 낮을수록 발화가 충실 → 점수 높음
                speech_score = round(max(30.0, min(100.0, 100.0 - silence_ratio * 80)), 1)
                return {
                    "avg_pitch": features.get("avg_pitch", 0.0),
                    "avg_energy": features.get("avg_energy", 0.0),
                    "silence_ratio": silence_ratio,
                    "speech_score": speech_score,
                }
        except Exception as e:
            logger.error(f"음성 분석 실패: {e}")

        return {
            "avg_pitch": 0.0,
            "avg_energy": 0.0,
            "silence_ratio": 0.0,
            "speech_score": 70.0,
        }


whisper_service = WhisperService()
