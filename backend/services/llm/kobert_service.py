import logging
import torch
from typing import Optional
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)


class KoBERTService:
    """KoBERT 답변 분석 서비스"""

    _instance: Optional["KoBERTService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            # ✅ 모델 통일 (중요)
            self.model_name = "skt/kobert-base-v1"

            self.tokenizer = None
            self.model = None

            self.initialized = True

    # ✅ 서버 시작 시 1회 실행
    async def load_model(self):
        if self.model is not None:
            return

        logger.info("⏳ KoBERT 모델 로딩 중...")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                use_fast=False
            )

            self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()

            logger.info(f"✅ KoBERT 로딩 완료 (device: {self.device})")

        except Exception as e:
            logger.error(f"❌ KoBERT 로딩 실패: {e}")
            raise e

    # ✅ 답변 분석
    async def analyze_answer(self, question: str, answer: str) -> dict:
        if not answer.strip():
            return self._empty_result()

        if self.model is None or self.tokenizer is None:
            return self._empty_result("모델이 아직 로드되지 않았습니다.")

        try:
            inputs = self.tokenizer(
                answer,
                return_tensors="pt",
                padding=True,
                truncation=True
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)

            hidden_states = outputs.last_hidden_state

            # ✅ 문장 임베딩
            embedding = hidden_states.mean(dim=1)

            return {
                "status": "success",
                "content_score": float(torch.rand(1).item() * 100),  # TODO: 실제 로직 교체
                "relevance_score": float(torch.rand(1).item() * 100),
                "clarity_score": float(torch.rand(1).item() * 100),
                "keywords": answer.split()[:5],
                "sentiment": "neutral",
                "feedback": "분석 완료",
                "embedding_shape": list(embedding.shape),
            }

        except Exception as e:
            logger.error(f"❌ 분석 실패: {e}")
            return self._empty_result(str(e))

    def _empty_result(self, message: str = "답변 내용이 없습니다.") -> dict:
        return {
            "status": "error",
            "content_score": 0.0,
            "relevance_score": 0.0,
            "clarity_score": 0.0,
            "keywords": [],
            "sentiment": "neutral",
            "feedback": message,
        }


# ✅ 싱글톤 인스턴스
kobert_service = KoBERTService()
