"""
KoBERT 답변 분석 서비스

역할: 면접 답변 텍스트를 KoBERT로 임베딩하여 내용·관련성·명확성 점수 산출.

현재 상태:
  - 모델 로드 및 임베딩 추출까지 실제 구현됨
  - 점수 산출은 torch.rand() 임시값 사용 (TODO: 실제 분류 헤드 학습 필요)

싱글톤 패턴:
  서버 전체에서 모델을 1개만 유지 (메모리 절약).
  __new__에서 인스턴스를 1번만 생성하고 이후 호출은 같은 객체를 반환.
"""
import logging
import torch
from typing import Optional
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)


class KoBERTService:

    _instance: Optional["KoBERTService"] = None

    def __new__(cls):
        # 이미 인스턴스가 있으면 새로 만들지 않고 기존 것을 반환 (싱글톤)
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            # CUDA GPU가 있으면 GPU 사용, 없으면 CPU — 추론 속도 차이가 큼
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model_name = "skt/kobert-base-v1"  # SKT 공개 KoBERT (HuggingFace Hub)
            self.tokenizer = None
            self.model = None
            self.initialized = True

    async def load_model(self):
        """
        서버 시작 시 1회 호출 — 토크나이저 + 모델을 메모리에 로드.

        이미 로드되어 있으면 스킵 (이중 로딩 방지).
        HuggingFace Hub에서 자동 다운로드 (첫 실행 시 수 분 소요).
        """
        if self.model is not None:
            return

        logger.info("KoBERT 모델 로딩 중...")
        try:
            # use_fast=False: KoBERT는 SentencePiece 기반 — fast tokenizer 미지원
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                use_fast=False,
            )
            self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()   # 드롭아웃·배치정규화를 추론 모드로 전환
            logger.info(f"KoBERT 로딩 완료 (device: {self.device})")
        except Exception as e:
            logger.error(f"KoBERT 로딩 실패 (stub 모드로 동작): {e}")
            self.model = None
            self.tokenizer = None

    async def analyze_answer(self, question: str, answer: str) -> dict:
        """
        질문-답변 쌍을 분석하여 점수 딕셔너리를 반환.

        현재 흐름:
          1) answer를 토크나이징
          2) KoBERT forward pass → last_hidden_state 추출
          3) 평균 풀링으로 문장 임베딩 생성
          4) (TODO) 임베딩을 분류 헤드에 통과시켜 실제 점수 산출
             현재는 torch.rand()로 임시 점수 반환

        question 파라미터는 향후 질문-답변 관련성 계산에 사용 예정.
        """
        if not answer.strip():
            return self._empty_result()

        if self.model is None or self.tokenizer is None:
            return self._empty_result("모델이 아직 로드되지 않았습니다.")

        try:
            # 답변 텍스트 토크나이징 — 최대 길이 초과 시 자동 truncate
            inputs = self.tokenizer(
                answer,
                return_tensors="pt",
                padding=True,
                truncation=True,
            ).to(self.device)

            # 그래디언트 계산 비활성화 — 추론 전용이므로 메모리·속도 최적화
            with torch.no_grad():
                outputs = self.model(**inputs)

            # [batch, seq_len, hidden_dim] → [batch, hidden_dim] 평균 풀링
            embedding = outputs.last_hidden_state.mean(dim=1)

            return {
                "status": "success",
                # TODO: 실제 분류 헤드(Linear + Softmax)로 교체
                "content_score":   float(torch.rand(1).item() * 100),
                "relevance_score": float(torch.rand(1).item() * 100),
                "clarity_score":   float(torch.rand(1).item() * 100),
                "keywords":        answer.split()[:5],   # 임시: 단순 앞 5단어
                "sentiment":       "neutral",
                "feedback":        "분석 완료",
                "embedding_shape": list(embedding.shape),
            }

        except Exception as e:
            logger.error(f"분석 실패: {e}")
            return self._empty_result(str(e))

    def _empty_result(self, message: str = "답변 내용이 없습니다.") -> dict:
        """분석 불가 상황에서 반환할 기본값 딕셔너리."""
        return {
            "status":          "error",
            "content_score":   0.0,
            "relevance_score": 0.0,
            "clarity_score":   0.0,
            "keywords":        [],
            "sentiment":       "neutral",
            "feedback":        message,
        }


kobert_service = KoBERTService()  # 모듈 로드 시 싱글톤 인스턴스 생성
