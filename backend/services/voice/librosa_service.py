import io
import os
import librosa
import numpy as np
import logging

logger = logging.getLogger(__name__)


async def generate_audio_spectrogram(audio_path: str):
    """오디오 파일을 멜 스펙트로그램 PNG bytes로 변환. 파일 없거나 오류 시 None 반환."""
    if not os.path.exists(audio_path):
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import librosa.display

        y, sr = librosa.load(audio_path, duration=30)
        S = librosa.feature.melspectrogram(y=y, sr=sr)
        S_db = librosa.power_to_db(S, ref=np.max)

        fig, ax = plt.subplots(figsize=(6, 3))
        librosa.display.specshow(S_db, sr=sr, ax=ax)
        ax.axis("off")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        logger.error(f"스펙트로그램 생성 실패: {e}")
        return None

class AudioAnalyzer:
    @staticmethod
    def analyze_features(audio_path: str):
        """
        Librosa를 사용하여 음성 신호의 특징(피치, 에너지, 무음 비율)을 추출합니다.
        """
        try:
            y, sr = librosa.load(audio_path)

            # 1. 피치(Pitch) 추출
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch = np.mean(pitches[pitches > 0]) if np.any(pitches > 0) else 0

            # 2. 에너지(RMS): 목소리 크기
            rms = librosa.feature.rms(y=y)
            energy = np.mean(rms)

            # 3. 무음 구간 비율 (Silence)
            intervals = librosa.effects.split(y, top_db=30)
            total_duration = len(y) / sr
            speech_duration = sum([(end - start) for start, end in intervals]) / sr
            silence_ratio = (total_duration - speech_duration) / total_duration if total_duration > 0 else 0

            return {
                "avg_pitch": round(float(pitch), 2),
                "avg_energy": round(float(energy), 4),
                "silence_ratio": round(silence_ratio, 2)
            }
        except Exception as e:
            logger.error(f"Librosa 분석 오류: {e}")
            return None
