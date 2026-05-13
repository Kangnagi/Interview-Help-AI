import logging
import google.generativeai as genai
from core.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            # core/config.py에 설정된 API 키 사용
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
            self.initialized = True
            logger.info("Gemini Service 초기화 완료")

    async def generate_interview_feedback(self, qa_list: list) -> dict:
        """
        면접 질문과 답변 목록을 받아 종합 피드백, 강점, 개선점을 생성합니다.
        """
        # 프롬프트 구성
        prompt = "당신은 전문 면접관입니다. 아래 제공된 면접 질문과 답변 내용을 분석하여 종합 피드백과 강점, 개선점을 작성해주세요.\n\n"
        
        for i, qa in enumerate(qa_list):
            prompt += f"질문 {i+1}: {qa['question']}\n"
            prompt += f"답변 {i+1}: {qa['answer']}\n\n"
        
        prompt += """
        형식은 반드시 아래와 같은 JSON 구조로 응답해주세요:
        {
          "feedback_summary": "전체적인 면접 답변 내용에 대한 요약 피드백",
          "strengths": ["잘한 점 1", "잘한 점 2"],
          "improvements": ["개선할 점 1", "개선할 점 2"]
        }
        """

        try:
            # 비동기 호출처럼 실행하기 위해 generate_content 사용
            response = self.model.generate_content(prompt)
            # 결과 텍스트에서 JSON 부분 추출 (Gemini 응답 특성상 마크다운 제거 필요할 수 있음)
            import json
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Gemini 피드백 생성 실패: {e}")
            return {
                "feedback_summary": "분석 중 오류가 발생했습니다.",
                "strengths": [],
                "improvements": []
            }

gemini_service = GeminiService()