import io
import os
import asyncio
import logging
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import librosa
import librosa.display

logger = logging.getLogger(__name__)


def _create_spectrogram_sync(audio_path: str) -> bytes:
    """동기적으로 멜 스펙트로그램 이미지를 생성 (비동기 executor에서 호출)."""
    if not os.path.exists(audio_path):
        return None
    try:
        y, sr = librosa.load(audio_path, sr=None)
        if len(y) == 0:
            return None

        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
        S_db = librosa.power_to_db(S, ref=np.max)

        fig, ax = plt.subplots(figsize=(10, 4))
        librosa.display.specshow(S_db, sr=sr, x_axis="time", y_axis="mel", ax=ax)
        ax.axis("off")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.error(f"Librosa 스펙트로그램 생성 중 오류: {e}")
        return None


async def generate_audio_spectrogram(audio_path: str) -> bytes:
    """저장된 오디오 파일을 멜 스펙트로그램 PNG bytes로 변환 (논블로킹)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create_spectrogram_sync, audio_path)


class AudioAnalyzer:
    @staticmethod
    def analyze_features_from_bytes(audio_bytes: bytes) -> dict:
        """오디오 바이트 데이터에서 목소리 특징(음량, 길이 등)을 분석."""
        try:
            import soundfile as sf
            with io.BytesIO(audio_bytes) as f:
                y, sr = sf.read(f)
            if len(y) == 0:
                return {}
            rms = librosa.feature.rms(y=y)
            return {
                "duration_sec": len(y) / sr,
                "avg_volume": float(np.mean(rms)),
            }
        except Exception as e:
            logger.error(f"AudioAnalyzer 분석 중 오류 발생: {e}")
            return {}

    @staticmethod
    def analyze_features(audio_path: str) -> dict:
        """파일 경로로 음성 특징 분석."""
        try:
            y, sr = librosa.load(audio_path, sr=None)
            if len(y) == 0:
                return {}
            rms = librosa.feature.rms(y=y)
            silence_ratio = float(np.mean(rms < 0.01))
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            avg_pitch = float(np.mean(pitches[magnitudes > np.max(magnitudes) * 0.1])) if magnitudes.max() > 0 else 0.0
            return {
                "duration_sec": len(y) / sr,
                "avg_energy": float(np.mean(rms)),
                "silence_ratio": silence_ratio,
                "avg_pitch": avg_pitch,
            }
        except Exception as e:
            logger.error(f"AudioAnalyzer.analyze_features 오류: {e}")
            return {}
