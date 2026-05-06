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
            self.model = None
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.model = genai.GenerativeModel(settings.GEMINI_MODEL)
                logger.info("Gemini Service 초기화 완료")
            except Exception as e:
                logger.error(f"Gemini 초기화 실패: {e} — 피드백 기능이 비활성화됩니다")
            self.initialized = True

    async def generate_interview_feedback(self, qa_list: list) -> dict:
        if self.model is None:
            return {
                "feedback_summary": "Gemini API를 사용할 수 없습니다. GEMINI_API_KEY를 확인하세요.",
                "strengths": [],
                "improvements": []
            }

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
            response = await self.model.generate_content_async(prompt)
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

    async def generate_question_feedback(
        self, question: str, answer: str, company: str = "", job: str = ""
    ) -> str:
        if self.model is None:
            return "Gemini API를 사용할 수 없습니다. GEMINI_API_KEY를 확인하세요."

        context = f"회사: {company}\n직무: {job}\n" if (company or job) else ""
        prompt = f"""당신은 전문 면접관입니다. 아래 질문에 대한 면접자의 답변을 평가해주세요.

{context}질문: {question}
답변: {answer if answer.strip() else "(답변 없음)"}

잘한 점과 개선할 점을 포함하여 2~3문장의 구체적인 피드백을 한국어로 작성해주세요."""

        try:
            response = await self.model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"질문 피드백 생성 실패: {e}")
            return "답변 내용을 잘 전달하셨습니다. 더 구체적인 사례나 수치를 추가하면 더욱 인상적인 답변이 될 것입니다."


gemini_service = GeminiService()
