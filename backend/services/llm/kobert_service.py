"""
KoBERT 기반 답변 분석 서비스
현재는 Stub — 다음 단계에서 실제 모델 로딩 구현

사용 예정 모델: monologg/kobert (HuggingFace)
태스크: 감정 분류, 핵심어 추출, 답변 품질 평가
"""
import logging
from typing import Optional
from core.config import settings

logger = logging.getLogger(__name__)


class KoBERTService:
    """KoBERT 답변 분석 서비스"""

    _instance: Optional["KoBERTService"] = None
    _model = None
    _tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def load_model(self):
        """
        모델 로드 (다음 단계에서 구현)
        from transformers import BertForSequenceClassification, BertTokenizer
        self._tokenizer = BertTokenizer.from_pretrained(settings.KOBERT_MODEL_PATH)
        self._model = BertForSequenceClassification.from_pretrained(settings.KOBERT_MODEL_PATH)
        """
        logger.info("KoBERT: 모델 로드 준비 완료 (현재 Stub)")

    async def analyze_answer(
        self,
        question: str,
        answer: str,
    ) -> dict:
        """
        답변 분석 — 현재는 더미 데이터 반환
        다음 단계에서 실제 KoBERT 추론으로 교체
        """
        if not answer.strip():
            return self._empty_result()

        # TODO: 실제 KoBERT 추론
        # inputs = self._tokenizer(question + "[SEP]" + answer, return_tensors="pt", truncation=True)
        # outputs = self._model(**inputs)

        logger.info(f"KoBERT 분석 (Stub): 질문={question[:30]}...")

        # 더미 결과
        word_count = len(answer.split())
        return {
            "content_score": min(100, word_count * 2.0),      # 단어 수 기반 임시 점수
            "relevance_score": 70.0,
            "clarity_score": 65.0,
            "keywords": answer.split()[:5],                    # 앞 5개 단어 (임시)
            "sentiment": "neutral",
            "feedback": "답변이 접수되었습니다. (AI 분석 모델 연결 예정)",
        }

    def _empty_result(self) -> dict:
        return {
            "content_score": 0.0,
            "relevance_score": 0.0,
            "clarity_score": 0.0,
            "keywords": [],
            "sentiment": "neutral",
            "feedback": "답변 내용이 없습니다.",
        }


kobert_service = KoBERTService()
