"""
음성 합격/불합격 추론 모델(VoiceScoreNet) 서버 연결
- 서버 시작 때 한 번 불러 두고(main.py lifespan), 발화 분석(librosa_service.analyze_speech)이 질문 구간 파형을 넘겨 부른다.
- 전처리는 학습과 같은 audio_features를 쓴다 (03_predict.py와 같은 계산).
- 모델 파일이 없거나 불러오지 못하면 비활성 — 발화 분석은 예전처럼 규칙 점수만 쓴다.
"""
import logging
import math
import os

import numpy as np

from core.config import settings
from services.voice.audio_features import SR, waveform_to_logmel

logger = logging.getLogger(__name__)

PASS_SCORE = 60   # 모델 판정 기준(합격/불합격 경계)이 되는 점수 — 60점 이상 = 모델이 합격으로 본 답변


class VoiceModelService:
    def __init__(self):
        self.model = None
        self.n_mels = 64
        self.max_frames = 6000
        self.pos_weight = 4.18
        self.threshold = 0.5

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        path = settings.VOICE_MODEL_PATH
        if not path:
            logger.info("[VoiceModel] VOICE_MODEL_PATH가 비어 있어 음성 모델을 쓰지 않음 (규칙 점수만)")
            return
        if not os.path.isfile(path):
            logger.warning(f"[VoiceModel] 모델 파일 없음: {path} — 규칙 점수만 사용")
            return
        try:
            import torch
            from services.voice.voice_score_model import VoiceScoreNet

            # 모델이 작아(4MB) CPU로 충분 — GPU는 Llama가 쓰고 있어 나눠 쓰지 않는다
            ck = torch.load(path, map_location="cpu")
            model = VoiceScoreNet(n_mels=ck["n_mels"])
            model.load_state_dict(ck["state_dict"])
            model.eval()
            self.n_mels = ck["n_mels"]
            self.max_frames = ck.get("max_frames", 6000)
            self.pos_weight = ck.get("pos_weight", 4.18)   # 예전 체크포인트엔 없으므로 전체 라벨 기준값 (03_predict.py와 같게)
            self.threshold = ck["threshold"]
            self.model = model
            logger.info(f"[VoiceModel] 로드 완료: {path} (임계값 {self.threshold:.2f}, pos_weight {self.pos_weight:.2f})")
        except Exception:
            logger.exception(f"[VoiceModel] 로드 실패: {path} — 규칙 점수만 사용")
            self.model = None

    def score_from_logit(self, logit: float) -> int:
        """logit → 발화 점수 (30~100). 판정 기준(threshold)이 정확히 PASS_SCORE점이 되게 고정한다.

        확률(sigmoid 뒤)은 0 · 1 근처에서 납작해져 점수가 양 끝으로 몰리므로 sigmoid 전 값(logit)을 쓴다.
        pos_weight 보정은 logit을 일정하게 빼는 것이라 기준과의 차이(th_logit - logit)에는 영향이 없다.
        """
        th = min(max(self.threshold, 1e-6), 1 - 1e-6)
        th_logit = math.log(th / (1 - th))
        score = PASS_SCORE + settings.VOICE_SCORE_PER_LOGIT * (th_logit - logit)
        return int(round(min(100, max(30, score))))

    def predict_sync(self, y: np.ndarray) -> dict | None:
        """16kHz 모노 파형 → {"p_fail", "p_fail_raw", "passed"}. 동기(CPU) 함수라 별도 스레드에서 부른다. 실패하면 None."""
        if self.model is None or y.size < SR:   # 1초 미만은 평가하지 않음
            return None
        try:
            import torch

            L = waveform_to_logmel(y, self.n_mels)[:, : self.max_frames].astype(np.float32)
            x = torch.from_numpy(L)[None, None]
            with torch.no_grad():
                logit = self.model(x, torch.tensor([L.shape[1]])).item()   # sigmoid 전 값 — 클수록 불합격 쪽
            prob = 1 / (1 + math.exp(-logit)) if logit >= 0 else math.exp(logit) / (1 + math.exp(logit))   # 큰 음수에서 넘침 방지
            # 학습 때 불합격에 pos_weight를 줘서 원본 확률이 부풀려져 있음 → 오즈를 pos_weight로 나눠 보정 (03_predict.py와 같은 식)
            p_cal = prob / (prob + self.pos_weight * (1 - prob))
            return {"score": self.score_from_logit(logit), "logit": round(logit, 3),
                    "p_fail": round(p_cal, 4), "p_fail_raw": round(prob, 4), "passed": prob < self.threshold}
        except Exception:
            logger.exception("[VoiceModel] 추론 실패")
            return None


voice_model_service = VoiceModelService()
