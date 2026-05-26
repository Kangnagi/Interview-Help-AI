"""
KoBERT 답변 분석 서비스

역할: 면접 답변 텍스트를 KoBERT로 임베딩하여 관련성·내용·명확성 점수 산출.

점수 산출 방식:
  relevance_score — 질문·답변 임베딩 코사인 유사도 기반
  content_score   — 답변 길이 휴리스틱 (30~400자 기준)
  clarity_score   — 어휘 다양성 (unique ratio)

싱글톤 패턴:
  서버 전체에서 모델을 1개만 유지 (메모리 절약).
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
            # use_fast=False: KoBERT는 SentencePiece 기반 XLNetTokenizer — fast tokenizer 미지원
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, use_fast=False
            )
            self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()   # 드롭아웃·배치정규화를 추론 모드로 전환
            logger.info(f"KoBERT 로딩 완료 (device: {self.device})")
        except Exception as e:
            logger.error(f"KoBERT 로딩 실패 (stub 모드로 동작): {e}")
            self.model = None
            self.tokenizer = None

    def _encode(self, text: str) -> "torch.Tensor":
        """텍스트를 KoBERT 임베딩 벡터(평균 풀링)로 변환."""
        encoding = self.tokenizer.encode_plus(
            text,
            max_length=128,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)
        # KoBERT의 token_type 임베딩 테이블은 크기 2 (0 또는 1) —
        # XLNetTokenizer가 반환하는 token_type_ids가 범위를 벗어나므로 0으로 강제.
        token_type_ids = torch.zeros_like(input_ids)

        with torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                token_type_ids=token_type_ids,
            )
        return outputs.last_hidden_state.mean(dim=1)  # [1, hidden_dim]

    async def analyze_answer(self, question: str, answer: str) -> dict:
        """
        질문-답변 쌍을 분석하여 점수 딕셔너리를 반환.

        점수 산출 방식:
          relevance_score — 질문·답변 임베딩 간 코사인 유사도 (0~1 → 0~100 변환)
          content_score   — 답변 길이 기반 휴리스틱 (짧으면 감점, 너무 길어도 감점)
          clarity_score   — 어휘 다양성 (unique tokens / total tokens × 100)
        """
        if not answer.strip():
            return self._empty_result()

        if self.model is None or self.tokenizer is None:
            return self._empty_result("모델이 아직 로드되지 않았습니다.")

        try:
            q_emb = self._encode(question)
            a_emb = self._encode(answer)

            # 코사인 유사도: [-1, 1] → 선형 변환으로 [0, 100]
            cos_sim = torch.nn.functional.cosine_similarity(q_emb, a_emb).item()
            relevance_score = round(min(100.0, max(0.0, (cos_sim - 0.3) / 0.7 * 100)), 1)

            # 답변 길이 기반 내용 충실도 (한국어 기준 100~400자가 적절)
            char_len = len(answer)
            if char_len < 30:
                content_score = 30.0
            elif char_len < 100:
                content_score = round(30.0 + (char_len - 30) / 70.0 * 40.0, 1)
            elif char_len < 400:
                content_score = round(70.0 + (char_len - 100) / 300.0 * 20.0, 1)
            else:
                content_score = round(min(95.0, 90.0 + (char_len - 400) / 600.0 * 5.0), 1)

            # 어휘 다양성 (명확성 지표)
            tokens = answer.split()
            unique_ratio = len(set(tokens)) / max(len(tokens), 1)
            clarity_score = round(min(90.0, max(40.0, unique_ratio * 100.0)), 1)

            # 대표 키워드: 길이 1 이하 토큰 제외
            keywords = [w for w in tokens if len(w) > 1][:5]

            return {
                "status": "success",
                "content_score":   content_score,
                "relevance_score": relevance_score,
                "clarity_score":   clarity_score,
                "keywords":        keywords,
                "sentiment":       "neutral",
                "feedback":        f"관련성 {relevance_score:.0f}점 / 내용 {content_score:.0f}점 / 명확성 {clarity_score:.0f}점",
                "embedding_shape": list(a_emb.shape),
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
