"""
공통 전처리: 음성 1개 → 로그-멜 스펙트로그램 1개
01(대량 추출) · 03(예측)이 모두 이 파일을 불러 씀
→ 학습 때와 예측 때 전처리가 1비트도 다르지 않도록 한 곳에서 관리
"""
import numpy as np
import librosa

# ---------------- 전처리 설정 ----------------
SR = 16000       # 샘플링 레이트: 1초 = 16,000개 숫자
N_FFT = 512      # FFT 크기
WIN = 400        # 창 길이 25ms: 이 구간을 한 덩어리로 보고 주파수 분석
HOP = 320        # 이동 간격 20ms: 1초에 50개 프레임
FMIN, FMAX = 50, 7600
MAX_SEC = 180


def wav_to_logmel(path, n_mels=64):
    """음성 파일 1개 → 로그-멜 스펙트로그램 1개 (n_mels × T, float16)"""
    # 1) 파형 읽기: 80초면 약 128만 개 숫자
    y, _ = librosa.load(path, sr=SR, mono=True, duration=MAX_SEC)
    return waveform_to_logmel(y, n_mels)


def waveform_to_logmel(y, n_mels=64):
    """16kHz 모노 파형 → 로그-멜 (wav_to_logmel의 2~5단계).
    서버는 브라우저 녹음(webm)을 PyAV로 디코딩하고 질문 구간만 잘라 파형으로 넘기므로 파일 대신 파형을 받는다."""
    y = y[: SR * MAX_SEC]
    # 2) 25ms 창을 20ms씩 옮기며 FFT → 주파수별 세기, 3) 사람 귀 특성의 멜 필터 64개로 묶기
    S = librosa.feature.melspectrogram(y=y, sr=SR, n_fft=N_FFT, win_length=WIN,
                                       hop_length=HOP, n_mels=n_mels, fmin=FMIN, fmax=FMAX)
    # 4) 로그(dB) 변환: 사람은 소리 크기를 로그로 느낌. ref=max라 녹음 음량과 무관
    L = librosa.power_to_db(S, ref=np.max, top_db=80)
    # 5) 대역별 평균·분산 정규화(CMVN): 마이크·채널·평균 음색 제거, '변화'만 남김
    L = (L - L.mean(axis=1, keepdims=True)) / (L.std(axis=1, keepdims=True) + 1e-5)
    return L.astype(np.float16)
