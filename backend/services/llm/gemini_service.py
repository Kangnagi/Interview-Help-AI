import os
import re
import json
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv(override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# .env의 GEMINI_MODEL을 우선 사용, 없으면 gemini-2.0-flash 기본값
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
client = None

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        # m.name은 'models/gemini-2.0-flash' 형태이므로 prefix 제거 후 비교
        available_models = [m.name.replace("models/", "") for m in client.models.list()]
        print(f"사용 가능한 모델: {available_models}")
        preferred = [MODEL_NAME, 'gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.0-pro']
        for p in preferred:
            if p in available_models:
                MODEL_NAME = p
                break
        else:
            if available_models:
                MODEL_NAME = available_models[0]
    except APIError as e:
        print(f"모델 목록 조회 실패 (API 오류): {e}")
    except Exception as e:
        print(f"모델 목록 조회 실패: {e}")
else:
    print("GEMINI_API_KEY를 찾을 수 없습니다.")

print(f"선택된 Gemini 모델: {MODEL_NAME}")


def _parse_json(text: str):
    """Gemini 응답에서 JSON 추출 — 마크다운 코드블록·앞뒤 텍스트 제거 후 파싱"""
    text = text.strip()
    if "```" in text:
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        text = m.group(1).strip() if m else re.sub(r'```(?:json)?', '', text).strip()
    # 객체 또는 배열 경계 탐색
    for s, e in [('{', '}'), ('[', ']')]:
        si, ei = text.find(s), text.rfind(e)
        if si != -1 and ei > si:
            return json.loads(text[si:ei + 1])
    return json.loads(text)


# ── 1) 질문별 즉시 피드백 (연습·실전 면접 중 실시간 호출) ─────────────────────────
async def analyze_answer_with_gemini(question: str, answer: str, audio_image_bytes: bytes = None, kobert_scores: dict = None) -> dict:
    if not GEMINI_API_KEY:
        return {"score": 0, "feedback": "서버 오류: Gemini API 키가 설정되지 않았습니다.", "tip": ""}

    answer_clean = (answer or "").strip()

    if not answer_clean:
        return {
            "score": 20,
            "feedback": "답변을 입력하지 않으셨습니다. 짧더라도 자신의 생각을 반드시 전달해야 합니다.",
            "tip": "모르더라도 관련 경험이나 학습 의지를 짧게 표현해 보세요.",
        }
    if len(answer_clean) < 10:
        return {
            "score": 35,
            "feedback": "답변이 너무 짧습니다. 이유와 구체적인 경험을 덧붙여 주세요.",
            "tip": "STAR 기법(상황→과제→행동→결과)으로 구조화하면 짧은 답변도 풍성해집니다.",
        }
    kobert_context = ""
    if kobert_scores and kobert_scores.get("status") == "success":
        kobert_context = (
            f"\n\n[참고 자료: KoBERT 모델의 1차 정량적 분석 결과]\n"
            f"- 질문과 답변의 맥락 관련성: {kobert_scores.get('relevance_score', 0)}/100점\n"
            f"- 답변 분량 및 내용 충실도: {kobert_scores.get('content_score', 0)}/100점\n"
            f"- 어휘 다양성 및 명확성: {kobert_scores.get('clarity_score', 0)}/100점\n"
            f"위 점수들을 면밀히 참고하여, 지원자가 어떤 부분(관련성, 충실도, 명확성 등)이 부족했거나 뛰어났는지 피드백에 자연스럽게 반영해 주세요."
        )

    prompt = (
        "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
        "지원자의 면접 질문과 답변, 그리고 AI의 1차 정량 평가 결과를 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지):\n"
        '{"score":0~100,"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안","tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}\n\n'
        f"면접 질문: {question}\n"
        f"지원자 답변: {answer_clean}"
        f"{kobert_context}"
    )
    contents = [prompt]
    if audio_image_bytes:
        contents.append({"mime_type": "image/png", "data": audio_image_bytes})

    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL_NAME, contents=contents),
                timeout=25.0,
            )
            return _parse_json(response.text)
        except Exception as e:
            err_str = str(e)
            is_quota = "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str
            print(f"Gemini 피드백 생성 오류 (시도 {attempt + 1}/3): {e}")
            if is_quota:
                await asyncio.sleep(20)
            elif attempt < 2:
                await asyncio.sleep(5)

    return {
        "score": 60,
        "feedback": "답변이 저장되었습니다. 면접 종료 후 종합 분석에서 상세 피드백을 확인하세요.",
        "tip": "다음 질문에서는 구체적인 경험과 수치를 활용해 답변해 보세요.",
    }


# ── 2) 배치 분석 (면접 종료 후 전체 질문 일괄 평가) ───────────────────────────────
async def analyze_answers_batch_with_gemini(qna_list: list) -> list:
    n = len(qna_list)
    fallback = [
        {"content_score": 70, "relevance_score": 70, "clarity_score": 70,
         "speech_score": 70, "posture_score": 70, "eye_contact_score": 70, "feedback": ""}
        for _ in range(n)
    ]

    if not GEMINI_API_KEY or not qna_list:
        return fallback

    items = "\n\n".join(
        f"[질문 {i + 1}]\n질문: {q['question']}\n지원자 답변: {q['answer'] or '없음'}"
        for i, q in enumerate(qna_list)
    )

    prompt = (
        "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
        f"아래 면접 Q&A {n}개를 분석하여 반드시 아래 형식의 JSON 배열로만 응답하세요 (코드블록 금지).\n"
        "배열 순서는 입력 순서와 반드시 일치해야 합니다.\n\n"
        '형식: [{"content_score":점수,"relevance_score":점수,"clarity_score":점수,'
        '"speech_score":점수,"posture_score":점수,"eye_contact_score":점수,'
        '"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성"}]\n\n'
        f"{items}"
    )

    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL_NAME, contents=prompt),
                timeout=60.0,
            )
            result = _parse_json(response.text)
            if isinstance(result, dict) and len(result) == 1:
                result = list(result.values())[0]
            if isinstance(result, list):
                while len(result) < n:
                    result.append(fallback[0])
                return result[:n]
        except Exception as e:
            wait = 10 + attempt * 10
            print(f"Gemini 배치 분석 오류 (시도 {attempt + 1}/3): {e} -> {wait}s 대기")
            await asyncio.sleep(wait)

    return fallback


# ── 3) 종합 총평 생성 (파이프라인 마지막 단계) ────────────────────────────────────
async def generate_overall_summary_with_gemini(qna_feedbacks: list[dict]) -> dict:
    default = {
        "feedback_summary": "AI 서비스 일시 오류로 총평을 생성할 수 없습니다. 질문별 피드백을 참고하세요.",
        "strengths": [
            "모든 질문에 성실하게 답변하셨습니다",
            "면접에 끝까지 적극적으로 참여하셨습니다",
            "자기소개서 기반 맞춤 질문에 빠짐없이 응하셨습니다",
        ],
        "improvements": [
            "구체적인 경험과 수치를 활용해 답변하면 더욱 설득력이 높아집니다",
            "STAR 기법(상황→과제→행동→결과)으로 답변을 구조화해 보세요",
            "스토리텔링 방식으로 답변하면 면접관에게 더 인상적으로 전달됩니다",
        ],
    }

    if not GEMINI_API_KEY or not qna_feedbacks:
        return default

    items_text = "\n\n".join(
        f"Q{i + 1}: {item['question']}\n답변: {item['answer'] or '없음'}"
        for i, item in enumerate(qna_feedbacks)
    )

    prompt = (
        "당신은 10년 차 전문 인사담당자입니다. 아래 면접 전체 내용을 종합 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지).\n"
        '{"feedback_summary":"전체 면접에 대한 종합 총평 2~3문장","strengths":["잘한 점 1","잘한 점 2","잘한 점 3"],"improvements":["개선할 점 1","개선할 점 2","개선할 점 3"]}\n\n'
        f"면접 내용:\n{items_text}"
    )

    for attempt in range(3):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL_NAME, contents=prompt),
                timeout=45.0,
            )
            result = _parse_json(response.text)
            if isinstance(result, dict) and "feedback_summary" in result:
                result.setdefault("strengths", [])
                result.setdefault("improvements", [])
                return result
        except Exception as e:
            print(f"Gemini 총평 생성 오류 (시도 {attempt + 1}/3): {e}")
            await asyncio.sleep(5)

    return default


# ── 4) 짧은 즉시 피드백 (현재 미사용, 하위 호환 유지) ─────────────────────────────
async def analyze_answer_with_gemini_short(question: str, answer: str, audio_image_bytes: bytes = None) -> str:
    if not GEMINI_API_KEY:
        return "서버 오류: Gemini API 키가 설정되지 않았습니다."
    answer_clean = (answer or "").strip()
    if not answer_clean:
        return "답변 내용이 없어 피드백을 생성할 수 없습니다."

    prompt = f"질문: {question[:80]}\n답변: {answer_clean[:150]}\n2문장 이내로 핵심 피드백만 작성하세요."
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL_NAME, contents=prompt),
                timeout=10.0,
            )
            return response.text
        except Exception as e:
            print(f"Gemini 짧은 피드백 오류 (시도 {attempt + 1}/2): {e}")
            await asyncio.sleep(3)
    return "피드백 생성에 실패했습니다."


# ── 5) 자기소개서 기반 질문 생성 ────────────────────────────────────────────────
async def generate_questions_from_resume(resume_text: str, category: str, num_questions: int = 5) -> list[str]:
    if not GEMINI_API_KEY:
        raise ValueError("서버 오류: Gemini API 키가 설정되지 않았습니다.")

    ai_num = max(0, num_questions - 2)

    prompt = (
        f"당신은 채용 담당자입니다. 아래 자기소개서를 바탕으로 면접 질문 {ai_num}개를 생성하세요.\n\n"
        "규칙:\n"
        "1. 자기소개·지원동기는 제외 (이미 진행됨)\n"
        "2. 자기소개서 내용에 직접 기반한 구체적 질문\n"
        "3. 독립적으로 답할 수 있는 질문 (꼬리 질문 제외)\n"
        "4. 순수 JSON 배열로만 반환: [\"질문1\", \"질문2\"]\n\n"
        f"직무: {category}\n\n"
        f"자기소개서:\n{resume_text[:2000]}"
    )

    try:
        response = await client.aio.models.generate_content(model=MODEL_NAME, contents=prompt)
        questions = _parse_json(response.text)
        if isinstance(questions, dict):
            for val in questions.values():
                if isinstance(val, list):
                    questions = val
                    break
        fixed = [
            "간단한 자기소개 부탁드립니다.",
            "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?",
        ]
        if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
            return fixed + questions[:ai_num]
        raise ValueError("올바른 형식의 질문 리스트가 아닙니다.")
    except Exception as e:
        print(f"Gemini 질문 생성 오류: {e}")
        return []
