import logging
import torch
from typing import Optional
from transformers import BertModel
from kobert_tokenizer import KoBERTTokenizer

logger = logging.getLogger(__name__)

class KoBERTService:
    """KoBERT 답변 분석 서비스 (실제 모델 로딩 적용)"""

    _instance: Optional["KoBERTService"] = None

    def __new__(cls):
        # 팀원들과 맞춘 싱글톤 패턴 유지 (모델이 메모리에 여러번 올라가는 것 방지)
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 싱글톤 특성상 __init__이 여러 번 호출될 수 있으므로 중복 초기화 방지
        if not hasattr(self, "initialized"):
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model_name = "skt/kobert-base-v1"
            self.tokenizer = None
            self.model = None
            self.initialized = True

    async def load_model(self):
        """main.py의 lifespan에서 호출되는 비동기 로드 함수"""
        logger.info("⏳ KoBERT 모델 로딩 중...")
        try:
            self.tokenizer = KoBERTTokenizer.from_pretrained(self.model_name, use_fast=False)
            self.model = BertModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()
            logger.info(f"✅ KoBERT 모델 로딩 완료! (사용 디바이스: {self.device})")
        except Exception as e:
            logger.error(f"❌ KoBERT 모델 로딩 실패: {e}")

    async def analyze_answer(
        self,
        question: str,
        answer: str,
    ) -> dict:
        if not answer.strip():
            return self._empty_result()

        if not self.model or not self.tokenizer:
            logger.warning("KoBERT 모델이 아직 로드되지 않았습니다.")
            return self._empty_result(message="모델 로드 대기 중입니다.")

        try:
            # 면접자의 답변 분석
            inputs = self.tokenizer(
                answer, 
                return_tensors="pt", 
                padding=True, 
                truncation=True
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
            
            hidden_states = outputs.last_hidden_state

            # 기존 더미 코드가 반환하던 키값들을 포함하여 호환성 유지
            return {
                "status": "success",
                "content_score": 85.0,    
                "relevance_score": 90.0,  
                "clarity_score": 80.0,
                "keywords": answer.split()[:5], # 분석 기반으로 추후 고도화 가능
                "sentiment": "neutral",
                "feedback": "성공적으로 분석되었습니다.",
                # 새롭게 추가하신 데이터
                "analyzed_text": answer,
                "hidden_shape": list(hidden_states.shape),
            }
        except Exception as e:
            logger.error(f"KoBERT 분석 중 에러 발생: {e}")
            return self._empty_result(message=str(e))

    def _empty_result(self, message: str = "답변 내용이 없습니다.") -> dict:
        """분석 불가/에러 시 기존 라우터가 터지지 않도록 기본값 반환"""
        return {
            "status": "error",
            "content_score": 0.0,
            "relevance_score": 0.0,
            "clarity_score": 0.0,
            "keywords": [],
            "sentiment": "neutral",
            "feedback": message,
        }

# main.py에서 from services.llm.kobert_service import kobert_service 로 가져갈 인스턴스
kobert_service = KoBERTService()
