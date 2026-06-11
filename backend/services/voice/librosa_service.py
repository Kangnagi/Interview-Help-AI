import io
import os
import asyncio
import logging
import threading
import uuid
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")  # GUI가 없는 서버 환경에서 오류 방지

from matplotlib.figure import Figure
import librosa
import librosa.display


logger = logging.getLogger(__name__)

MAX_SPECTROGRAM_DURATION_SECONDS = 30
_PLOT_LOCK = threading.Lock()


def _create_spectrogram_sync(audio_path: str) -> bytes | None:
    """오디오 파일을 멜 스펙트로그램 이미지 PNG bytes로 변환하는 내부 함수"""

    if not audio_path or not os.path.isfile(audio_path):
        return None

    try:
        # 긴 답변이 서버 메모리와 분석 시간을 과도하게 사용하지 않도록 앞부분만 분석합니다.
        y, sr = librosa.load(
            audio_path,
            sr=None,
            mono=True,
            duration=MAX_SPECTROGRAM_DURATION_SECONDS,
        )

        if y.size == 0:
            return None

        mel_spectrogram = librosa.feature.melspectrogram(
            y=y,
            sr=sr,
            n_mels=128,
        )
        spectrogram_db = librosa.power_to_db(mel_spectrogram, ref=np.max)
        
        # RMS Energy 계산
        rms = librosa.feature.rms(y=y)[0]
        times = librosa.times_like(rms, sr=sr)

        # Matplotlib 내부 상태는 완전히 thread-safe하지 않아 렌더링 구간을 보호합니다.
        with _PLOT_LOCK:
            # 2개의 서브플롯을 위아래로 배치
            figure = Figure(figsize=(10, 6))
            axes = figure.subplots(nrows=2, ncols=1, sharex=True, gridspec_kw={'height_ratios': [3, 1]})
            
            # 1. Mel Spectrogram
            librosa.display.specshow(
                spectrogram_db,
                sr=sr,
                x_axis="time",
                y_axis="mel",
                ax=axes[0],
            )
            axes[0].set_title("Mel Spectrogram")
            axes[0].set_xlabel("") # 공유 x축이므로 위쪽 그래프의 x축 라벨 제거
            
            # 2. RMS Energy
            axes[1].semilogy(times, rms, label="RMS Energy", color="b")
            axes[1].set_ylabel("RMS Energy")
            axes[1].set_xlabel("Time (s)")
            axes[1].set_xlim([times.min(), times.max()])
            axes[1].legend(loc="upper right")
            
            figure.tight_layout()

            with io.BytesIO() as buffer:
                figure.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0.1)
                return buffer.getvalue()

    except Exception:
        logger.exception("Librosa 스펙트로그램 생성 중 오류: %s", audio_path)
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