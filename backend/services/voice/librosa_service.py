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


# ── 발화 분석 (Gemini 스펙트로그램 이미지 분석 대체 — 완전 로컬) ─────────────────────
# 그림을 모델에 보여주는 대신 파형에서 직접 수치를 뽑는다. 기준값은 실제 면접 녹음으로 확인한 범위에 맞춤.
MAX_SPEECH_ANALYSIS_SECONDS = 180
SILENCE_TOP_DB = 35          # 최대 음량 대비 이 dB보다 작으면 침묵으로 간주
LONG_PAUSE_SECONDS = 2.0     # 이보다 긴 침묵은 '긴 멈춤'
FILLER_WORDS = {"음", "어", "그", "저", "뭐", "음...", "어...", "그...", "아", "으"}


def _load_audio(audio_path: str, sr: int = 16000, max_seconds: float | None = None) -> np.ndarray:
    """오디오를 모노 float32 파형으로 읽는다.

    브라우저 녹음은 webm(opus)인데 librosa(soundfile/audioread)는 ffmpeg 없이 webm을 못 읽어서,
    ffmpeg가 내장된 PyAV로 먼저 디코딩하고 실패하면 librosa로 시도한다.
    (MediaRecorder가 만든 webm은 길이 메타데이터가 없는 경우가 많아 길이도 디코딩한 샘플 수로 잰다)
    """
    try:
        import av

        limit = int(max_seconds * sr) if max_seconds else None
        chunks, total = [], 0
        with av.open(audio_path) as container:
            resampler = av.AudioResampler(format="flt", layout="mono", rate=sr)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    arr = out.to_ndarray().reshape(-1)
                    chunks.append(arr)
                    total += arr.size
                if limit and total >= limit:
                    break
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
        y = np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, dtype=np.float32)
        return y[:limit] if limit else y
    except Exception:
        y, _ = librosa.load(audio_path, sr=sr, mono=True, duration=max_seconds)
        return y


def _count_syllables(text: str) -> int:
    return sum(1 for ch in text or "" if "가" <= ch <= "힣")


def extract_speech_features(audio_path: str, transcript: str = "") -> dict | None:
    """오디오 파형 + 인식된 텍스트에서 발화 지표를 계산한다. 실패하면 None."""
    if not audio_path or not os.path.isfile(audio_path):
        return None
    try:
        sr = 16000
        y = _load_audio(audio_path, sr=sr, max_seconds=MAX_SPEECH_ANALYSIS_SECONDS)
        duration = len(y) / sr
        if duration < 1.0 or float(np.max(np.abs(y))) < 1e-4:
            return None

        # 발화 구간 / 침묵
        intervals = librosa.effects.split(y, top_db=SILENCE_TOP_DB)
        voiced = sum(e - s for s, e in intervals) / sr
        gaps = [(intervals[i + 1][0] - intervals[i][1]) / sr for i in range(len(intervals) - 1)]
        long_pauses = sum(g >= LONG_PAUSE_SECONDS for g in gaps)

        # 억양 변화: 발화 구간의 기본 주파수(F0) 표준편차 (반음 단위)
        f0 = librosa.yin(y, fmin=70, fmax=400, sr=sr, frame_length=1024)
        rms_frames = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
        n = min(len(f0), len(rms_frames))
        loud = rms_frames[:n] > (np.max(rms_frames) * 10 ** (-SILENCE_TOP_DB / 20))
        f0v = f0[:n][loud]
        f0v = f0v[(f0v > 70) & (f0v < 400)]
        pitch_std_semitones = float(np.std(12 * np.log2(f0v / np.median(f0v)))) if f0v.size > 20 else None

        # 음량 안정성: 발화 프레임 RMS(dB)의 표준편차
        rms_db = 20 * np.log10(rms_frames[:n][loud] + 1e-9)
        volume_std_db = float(np.std(rms_db)) if rms_db.size > 20 else None

        syllables = _count_syllables(transcript)
        words = (transcript or "").split()
        fillers = sum(w.strip(",.?!") in FILLER_WORDS for w in words)
        return {
            "duration": round(duration, 1),
            "voiced_ratio": round(float(voiced / duration), 2),
            "long_pauses": int(long_pauses),
            "syllables_per_sec": round(syllables / duration, 2) if syllables else None,
            "pitch_std_semitones": round(pitch_std_semitones, 2) if pitch_std_semitones is not None else None,
            "volume_std_db": round(volume_std_db, 1) if volume_std_db is not None else None,
            "filler_count": int(fillers),
            "filler_per_100_syllables": round(100 * fillers / syllables, 1) if syllables else None,
        }
    except Exception:
        logger.exception("발화 지표 계산 중 오류: %s", audio_path)
        return None


def score_speech(f: dict) -> dict:
    """발화 지표 → {"speech_score", "feedback"}. 가장 크게 감점된 항목 하나를 코칭 문장으로 돌려준다.

    기준값은 한국어 말하기 연구의 일반적 범위(대화·발표 초당 3.5~5.5음절, 침묵 40% 미만 등)를 따르고,
    실제 녹음 데이터가 쌓이면 다시 맞출 수 있도록 감점 폭은 작게 잡았다.
    """
    penalties = []  # (감점, 코칭 문장)
    r = f.get("syllables_per_sec")
    if r is not None:
        if r < 3.5:
            penalties.append((min(20, (3.5 - r) * 15),
                              f"말 속도가 느린 편입니다(초당 {r}음절). 쉬는 시간을 줄이고 문장을 이어서 말해 보세요."))
        elif r > 5.5:
            penalties.append((min(20, (r - 5.5) * 15),
                              f"말 속도가 빠른 편입니다(초당 {r}음절). 핵심 문장 앞뒤로 잠깐 쉬며 천천히 말해 보세요."))
    vr = f.get("voiced_ratio")
    if vr is not None and vr < 0.6:
        penalties.append((min(15, (0.6 - vr) * 50),
                          "답변 중 침묵 시간이 깁니다. 말할 내용을 미리 두세 개의 키워드로 정리해 두세요."))
    lp = f.get("long_pauses", 0)
    if lp:
        penalties.append((min(12, lp * 4),
                          f"2초 이상 멈춘 구간이 {lp}번 있었습니다. 막힐 때는 '다시 말씀드리면'처럼 연결 표현을 써 보세요."))
    ps = f.get("pitch_std_semitones")
    if ps is not None and ps < 2.5:
        penalties.append((10 if ps < 1.5 else 5,
                          "억양 변화가 적어 단조롭게 들릴 수 있습니다. 핵심 단어에 힘을 주어 강조해 보세요."))
    vs = f.get("volume_std_db")
    if vs is not None and vs > 12:
        penalties.append((5, "목소리 크기가 들쭉날쭉합니다. 문장 끝까지 일정한 크기로 말해 보세요."))
    fr = f.get("filler_per_100_syllables")
    if fr is not None and fr > 3:
        penalties.append((min(15, (fr - 3) * 2),
                          f"'음', '어' 같은 추임새가 {f.get('filler_count')}번 나왔습니다. 말이 막힐 때는 추임새 대신 잠깐 멈춰 보세요."))

    score = max(30, round(100 - sum(p for p, _ in penalties)))
    feedback = max(penalties)[1] if penalties else "말 속도와 멈춤이 안정적입니다. 지금처럼 또렷하게 전달하세요."
    return {"speech_score": score, "feedback": feedback}


async def analyze_speech(audio_path: str, transcript: str = "") -> dict | None:
    """녹음 파일의 발화를 로컬에서 분석해 {"speech_score", "feedback", "metrics"}를 돌려준다. 분석 불가면 None."""
    features = await asyncio.to_thread(extract_speech_features, audio_path, transcript)
    if not features:
        return None
    return {**score_speech(features), "metrics": features}


def get_audio_duration(audio_path: str) -> float:
    """오디오 파일의 길이를 초(second) 단위로 반환합니다."""
    if not audio_path or not os.path.exists(audio_path):
        return 0.0

    try:
        # webm은 길이 메타데이터가 없는 경우가 많아 실제로 디코딩한 샘플 수로 잰다.
        return len(_load_audio(audio_path, sr=8000)) / 8000
    except Exception:
        return 0.0