import io
import logging
import asyncio
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
import ffmpeg
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from core.config import settings
from services.voice.librosa_service import AudioAnalyzer

logger = logging.getLogger(__name__)

class WhisperService:
    _instance: Optional["WhisperService"] = None
    _model = None
    # CPU 집약적 작업을 위한 스레드 풀 (동시 분석 제한)
    _executor = ThreadPoolExecutor(max_workers=3)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def load_model(self):
        """서버 시작 시 모델 로드"""
        if self._model is None:
            # 설정값에 따라 모델 사이즈 결정 (base, small 등)
            # device="auto"로 설정하면 GPU가 있으면 GPU, 없으면 CPU를 가장 효율적으로 사용합니다.
            self._model = WhisperModel(settings.WHISPER_MODEL_SIZE, device="auto", compute_type="default")
            logger.info(f"Whisper: {settings.WHISPER_MODEL_SIZE} 모델 로드 완료")

    async def transcribe_bytes(self, audio_bytes: bytes) -> dict:
        """전체 오디오 바이너리를 텍스트로 변환 (STT)"""
        if not audio_bytes:
            return {"text": "", "segments": []}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._run_whisper_inference, audio_bytes)

    def _run_whisper_inference(self, audio_bytes: bytes):
        """[Thread] 실제 Whisper 추론"""
        try:
            # Safari MP4 등 파이프 파싱 에러 방지를 위해 임시 파일 저장 후 변환
            with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                out, _ = (
                    ffmpeg.input(tmp_path)
                    .output('pipe:1', format='f32le', acodec='pcm_f32le', ac=1, ar=16000)
                    .run(capture_stdout=True, capture_stderr=True)
                )
                audio_data = np.frombuffer(out, np.float32)
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg 오디오 변환 에러: {e.stderr.decode()}")
                return {"text": "", "error": "오디오 포맷 변환 실패"}
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            segments, info = self._model.transcribe(
                audio_data, 
                language=settings.WHISPER_LANGUAGE or "ko", 
                task="transcribe",
                temperature=[0.0, 0.2, 0.4, 0.6], # faster-whisper는 list를 선호합니다
                condition_on_previous_text=False, # 이전 노이즈에 갇혀 반복되는 현상 방지
                initial_prompt="아, 음, 그, 어 등 무의미한 추임새는 생략하고, 앞뒤 문맥을 고려하여 명확하고 논리적인 한국어 완성형 문장으로 교정하여 출력해 주세요.",
                beam_size=5,             # 탐색 범위를 넓혀 가장 자연스러운 문장 도출
                best_of=5,               # 여러 후보 중 가장 품질이 높은 문장 선택
                no_speech_threshold=0.6, # 침묵 구간에서 외계어를 지어내는 환각 완벽 차단
                log_prob_threshold=-1.0, # faster-whisper는 log_prob_threshold 로 언더바(_)가 들어갑니다
                vad_filter=True,         # 사람 목소리가 없는 잡음/정적 구간은 아예 분석에서 제외 (환각 원천 차단)
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            # faster-whisper는 텍스트를 조각(generator)으로 반환하므로 반복문을 돌려 합쳐줍니다.
            text = ""
            seg_list = []
            for segment in segments:
                text += segment.text + " "
                seg_list.append({"start": segment.start, "end": segment.end, "text": segment.text.strip()})
                
            return {
                "text": text.strip(),
                "segments": seg_list
            }
        except Exception as e:
            logger.error(f"Whisper 추론 중 오류 발생: {e}")
            return {"text": "", "error": str(e)}

    async def analyze_speech_bytes(self, audio_bytes: bytes) -> dict:
        """전체 오디오의 음성 특징 분석 (Librosa 활용)"""
        loop = asyncio.get_event_loop()
        # 이전에 만든 AudioAnalyzer 클래스의 메서드 호출
        result = await loop.run_in_executor(
            self._executor, 
            AudioAnalyzer.analyze_features_from_bytes, 
            audio_bytes
        )
        return result or {}

whisper_service = WhisperService()