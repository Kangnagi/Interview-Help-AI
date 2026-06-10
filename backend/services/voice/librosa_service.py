import io
import os
import asyncio
import uuid
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")  # GUI가 없는 서버 환경에서 오류 방지

import matplotlib.pyplot as plt
import librosa
import librosa.display


def _create_spectrogram_sync(audio_path: str) -> bytes | None:
    """오디오 파일을 멜 스펙트로그램 이미지 PNG bytes로 변환하는 내부 함수"""

    if not os.path.exists(audio_path):
        return None

    try:
        # 1. 오디오 파일 로드
        y, sr = librosa.load(audio_path, sr=None)

        if len(y) == 0:
            return None

        # 2. 멜 스펙트로그램 생성
        plt.figure(figsize=(10, 4))

        S = librosa.feature.melspectrogram(
            y=y,
            sr=sr,
            n_mels=128
        )

        # 3. dB 단위로 변환
        S_dB = librosa.power_to_db(S, ref=np.max)

        # 4. 스펙트로그램 이미지 그리기
        librosa.display.specshow(
            S_dB,
            sr=sr,
            x_axis="time",
            y_axis="mel"
        )

        # 5. PNG bytes로 변환
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
        plt.close()

        buf.seek(0)
        return buf.read()

    except Exception as e:
        print(f"Librosa 스펙트로그램 생성 중 오류: {e}")
        return None


async def generate_audio_spectrogram(audio_path: str) -> bytes | None:
    """
    저장된 오디오 파일을 읽어 멜 스펙트로그램 이미지로 변환합니다.
    서버가 멈추지 않도록 별도 스레드에서 실행합니다.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        _create_spectrogram_sync,
        audio_path
    )


async def save_audio_spectrogram(audio_path: str) -> str | None:
    """
    오디오 파일을 멜 스펙트로그램 이미지로 변환한 뒤
    backend/uploads/librosa_img 폴더에 PNG로 저장합니다.
    """
    image_bytes = await generate_audio_spectrogram(audio_path)

    if image_bytes is None:
        return None

    # 현재 파일 위치: backend/services/voice/librosa_service.py
    # parents[2] = backend
    backend_dir = Path(__file__).resolve().parents[2]

    save_dir = backend_dir / "uploads" / "librosa_img"
    save_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4()}.png"
    save_path = save_dir / filename

    with open(save_path, "wb") as f:
        f.write(image_bytes)

    return str(save_path)


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 길이를 초(second) 단위로 반환합니다."""
    if not audio_path or not os.path.exists(audio_path):
        return 0.0

    try:
        # librosa.get_duration은 파일을 전체 로드하지 않고 길이를 반환합니다.
        return float(librosa.get_duration(path=audio_path))
    except Exception:
        return 0.0