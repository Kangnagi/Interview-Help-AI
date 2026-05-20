import io
import os
import asyncio
import matplotlib
matplotlib.use('Agg') # GUI가 없는 서버 환경에서 오류 방지
import matplotlib.pyplot as plt
import librosa
import librosa.display

class AudioAnalyzer:
    @staticmethod
    def analyze_features_from_bytes(audio_bytes: bytes) -> dict:
        """오디오 바이트 데이터에서 목소리 특징(음량, 길이 등)을 분석합니다."""
        try:
            import soundfile as sf
            import numpy as np
            with io.BytesIO(audio_bytes) as f:
                y, sr = sf.read(f)
            if len(y) == 0:
                return {}
            
            # 간단한 RMS(음량) 계산
            rms = librosa.feature.rms(y=y)
            return {
                "duration_sec": len(y) / sr,
                "avg_volume": float(np.mean(rms))
            }
        except Exception as e:
            print(f"AudioAnalyzer 분석 중 오류 발생: {e}")
            return {}

def _create_spectrogram_sync(audio_path: str) -> bytes:
    """동기적으로 스펙트로그램 이미지를 생성하는 내부 함수"""
    if not os.path.exists(audio_path):
        return None
        
    try:
        # 1. 오디오 로드
        y, sr = librosa.load(audio_path, sr=None)
        
        if len(y) == 0:
            return None

        # 2. 멜 스펙트로그램 생성
        plt.figure(figsize=(10, 4))
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
        S_dB = librosa.power_to_db(S, ref=max)
        
        # 3. 이미지 그리기 및 바이트 데이터로 추출
        librosa.display.specshow(S_dB, sr=sr, x_axis='time', y_axis='mel')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        plt.close()
        buf.seek(0)
        return buf.read()
    except Exception as e:
        print(f"Librosa 스펙트로그램 생성 중 오류: {e}")
        return None

async def generate_audio_spectrogram(audio_path: str) -> bytes:
    """
    저장된 오디오 파일을 읽어들여 멜 스펙트로그램 이미지로 변환합니다.
    (서버 멈춤을 방지하기 위해 비동기 논블로킹 스레드에서 실행됩니다.)
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create_spectrogram_sync, audio_path)