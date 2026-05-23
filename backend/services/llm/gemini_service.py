import logging
import json
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

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
            self.model_name = settings.GEMINI_MODEL or "gemini-1.5-flash"
            try:
                if settings.GEMINI_API_KEY:
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    self.model = genai.GenerativeModel(self.model_name)
                    logger.info("Gemini Service 초기화 완료")
                else:
                    logger.warning("GEMINI_API_KEY 미설정 — stub 모드로 동작")
            except Exception as e:
                logger.error(f"Gemini 초기화 실패 (stub 모드): {e}")
            self.initialized = True

    async def generate_interview_feedback(self, qa_list: list) -> dict:
        """
        면접 질문과 답변 목록을 받아 종합 피드백, 강점, 개선점을 생성합니다.
        """
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
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Gemini 피드백 생성 실패: {e}")
            return self._stub_feedback()

    async def generate_question_feedback(
        self, question: str, answer: str, company: str = "", job: str = ""
    ) -> str:
        """질문-답변 쌍에 대해 즉시 피드백 한 단락을 생성합니다."""
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

    def _stub_feedback(self) -> dict:
        return {
            "feedback_summary": "전반적으로 성실하게 답변하셨습니다. 구체적인 경험을 바탕으로 답변하면 더욱 설득력이 높아집니다.",
            "strengths": ["답변을 끝까지 완성하는 성실함", "질문 의도를 파악하려는 노력"],
            "improvements": ["구체적인 수치나 사례를 추가하면 좋습니다", "결론을 먼저 말한 뒤 이유를 설명하는 구조를 추천합니다"],
        }


gemini_service = GeminiService()


async def analyze_answers_batch_with_gemini(qna_list: list) -> list:
    """
    여러 Q&A를 한 번의 Gemini 호출로 분석.
    Returns: list of dicts with content_score, relevance_score, clarity_score,
             speech_score, posture_score, eye_contact_score, feedback
    """
    if gemini_service.model is None or not qna_list:
        return [_stub_score() for _ in qna_list]

    prompt = (
        "당신은 전문 면접관이자 AI 채점 시스템입니다.\n"
        "아래 면접 Q&A 목록을 분석하여 각 답변에 대해 점수와 피드백을 제공해주세요.\n\n"
    )
    for i, qna in enumerate(qna_list):
        prompt += f"[{i+1}]\n질문: {qna['question']}\n답변: {qna['answer']}\n\n"

    prompt += (
        f"위 {len(qna_list)}개의 답변 각각에 대해 아래 JSON 배열 형식으로만 응답하세요.\n"
        "각 점수는 0~100 정수입니다.\n"
        "[\n"
        '  {"content_score": 85, "relevance_score": 80, "clarity_score": 75, '
        '"speech_score": 70, "posture_score": 70, "eye_contact_score": 70, '
        '"feedback": "이 답변에 대한 간략한 피드백"}\n'
        "]\n"
        f"반드시 {len(qna_list)}개의 객체를 배열에 포함하세요."
    )

    try:
        response = await gemini_service.model.generate_content_async(prompt)
        raw = response.text.replace("```json", "").replace("```", "").strip()
        results = json.loads(raw)
        if isinstance(results, list):
            while len(results) < len(qna_list):
                results.append(_stub_score())
            return results[:len(qna_list)]
        return [_stub_score() for _ in qna_list]
    except Exception as e:
        logger.error(f"Gemini 배치 분석 실패: {e}")
        return [_stub_score() for _ in qna_list]


async def generate_questions_from_resume(resume_text: str, category: str, num_questions: int = 8) -> list:
    """자기소개서 내용을 바탕으로 면접 질문 목록 생성."""
    if gemini_service.model is None:
        return []

    prompt = (
        f"당신은 전문 면접관입니다. 아래 자기소개서를 읽고 '{category}' 유형의 면접 질문 {num_questions}개를 생성해주세요.\n\n"
        f"자기소개서:\n{resume_text}\n\n"
        f"규칙:\n"
        f"- 자기소개서의 구체적인 내용을 참고한 질문을 만드세요\n"
        f"- 각 질문은 한 문장으로 작성하세요\n"
        f"- 반드시 JSON 배열 형식으로만 응답하세요: [\"질문1\", \"질문2\", ...]"
    )

    try:
        response = await gemini_service.model.generate_content_async(prompt)
        raw = response.text.replace("```json", "").replace("```", "").strip()
        questions = json.loads(raw)
        if isinstance(questions, list):
            return [str(q) for q in questions]
        return []
    except Exception as e:
        logger.error(f"Gemini 질문 생성 실패: {e}")
        return []


async def analyze_answer_with_gemini_short(question: str, answer: str, image_bytes=None) -> dict:
    """단일 답변에 대한 즉시 피드백 생성 (연습 면접용)."""
    if gemini_service.model is None:
        return {"score": 70, "feedback": "답변이 저장되었습니다. 계속 연습하세요!", "tip": "더 구체적인 사례를 포함해 보세요."}

    prompt = (
        f"당신은 전문 면접관입니다. 아래 면접 Q&A를 평가하고 즉시 피드백을 제공해주세요.\n\n"
        f"질문: {question}\n"
        f"답변: {answer}\n\n"
        f"평가 기준: 내용 충실도, 질문 관련성, 답변 구조(두괄식 여부), 구체성\n\n"
        f"반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 금지):\n"
        f'{{"score": 75, "feedback": "답변에 대한 2~3문장 구체적 피드백", "tip": "다음 답변을 위한 실질적 개선 팁 한 문장"}}'
    )

    try:
        response = await gemini_service.model.generate_content_async(prompt)
        raw = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Gemini 단답 분석 실패: {e}")
        return {"score": 70, "feedback": "답변이 저장되었습니다.", "tip": "더 구체적인 사례를 포함해 보세요."}


def _stub_score() -> dict:
    return {
        "content_score": 70,
        "relevance_score": 70,
        "clarity_score": 70,
        "speech_score": 70,
        "posture_score": 70,
        "eye_contact_score": 70,
        "feedback": "답변이 저장되었습니다.",
    }
