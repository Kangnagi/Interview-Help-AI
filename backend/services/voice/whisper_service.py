"""
Whisper 음성 인식 서비스
현재는 Stub — 다음 단계에서 실제 모델 로딩 구현

사용 예정: openai/whisper (base 또는 small 모델, 한국어)
나중에 추가: Librosa (발화 속도, 음높이, 에너지 분석)
"""
import logging
from typing import Optional
from pathlib import Path
from core.config import settings

logger = logging.getLogger(__name__)


class WhisperService:
    """Whisper STT + 음성 분석 서비스"""

    _instance: Optional["WhisperService"] = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def load_model(self):
        """
        다음 단계에서 구현:
        import whisper
        self._model = whisper.load_model(settings.WHISPER_MODEL_SIZE)
        """
        logger.info(f"Whisper: {settings.WHISPER_MODEL_SIZE} 모델 로드 준비 (현재 Stub)")

    async def transcribe(self, audio_path: str) -> dict:
        """
        오디오 파일 → 텍스트 변환
        다음 단계에서 실제 Whisper 추론으로 교체
        """
        path = Path(audio_path)
        if not path.exists():
            return {"text": "", "error": "파일을 찾을 수 없습니다"}

        # TODO:
        # result = self._model.transcribe(audio_path, language=settings.WHISPER_LANGUAGE)
        # return {"text": result["text"], "segments": result["segments"]}

        logger.info(f"Whisper STT (Stub): {audio_path}")
        return {
            "text": "(음성 인식 결과가 여기에 표시됩니다)",
            "language": "ko",
            "segments": [],
        }

    async def analyze_speech(self, audio_path: str) -> dict:
        """
        음성 특징 분석
        Librosa 추가 시: 발화 속도, 음높이 변화, 음량, 무음 구간 등
        """
        # TODO: Librosa 분석
        # import librosa
        # y, sr = librosa.load(audio_path)
        # tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        return {
            "speech_pace": 120.0,          # WPM (더미)
            "filler_word_count": 0,        # 습관어 횟수
            "silence_ratio": 0.15,         # 무음 비율
            "speech_score": 70.0,
        }


whisper_service = WhisperService()
