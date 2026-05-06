import librosa
import numpy as np
import logging

logger = logging.getLogger(__name__)

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
