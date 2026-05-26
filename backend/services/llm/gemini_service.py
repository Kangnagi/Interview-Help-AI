import os
import json
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

# 1. 환경 변수 로드
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 기본 모델 설정 (최신 표준인 gemini-2.5-flash 권장, 원하시면 1.5-flash로 두셔도 됩니다)
MODEL_NAME = 'gemini-2.5-flash' 
client = None

if GEMINI_API_KEY:
    # 2. 새로운 방식으로 클라이언트 생성
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    try:
        # 3. 사용 가능한 모델 리스트 조회 (새로운 API 방식)
        available_models = [m.name for m in client.models.list()]
        print(f"✅ 내 API 키로 사용 가능한 모델 리스트: {available_models}")
        
        # 4. 모델 자동 선택 로직
        preferred = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.0-pro']
        for p in preferred:
            if p in available_models:
                MODEL_NAME = p
                break
        else:
            if available_models:
                MODEL_NAME = available_models[0]
                
    except APIError as e:
        print(f"⚠️ 모델 목록 조회 실패 (API 오류): {e}")
    except Exception as e:
        print(f"⚠️ 모델 목록 조회 실패 (기타 오류): {e}")
else:
    print("❌ GEMINI_API_KEY를 찾을 수 없습니다. .env 파일을 확인해 주세요.")

print(f"✅ 최종 선택된 Gemini 모델: {MODEL_NAME}")

async def analyze_answer_with_gemini(question: str, answer: str, audio_image_bytes: bytes = None) -> dict:
    """
    면접 질문과 지원자의 답변을 받아 Gemini API를 통해 면접 피드백을 비동기로 생성합니다.
    """
    if not GEMINI_API_KEY:
        return {"feedback": "서버 오류: Gemini API 키가 설정되지 않았습니다."}

    if not answer or answer.strip() == "답변 없음" or len(answer.strip()) < 5:
        return {"feedback": "답변 내용이 너무 짧거나 입력되지 않아 피드백을 생성할 수 없었습니다."}

    prompt_text = f"""
    당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.
    지원자의 면접 질문과 텍스트 답변, 그리고 (제공된 경우) 음성을 시각화한 파형(멜 스펙트로그램) 이미지를 바탕으로 피드백을 작성해 주세요.
    
    아래 항목들을 포함하여 반드시 JSON 형식으로만 응답해 주세요:
    {{
      "feedback": "1. 잘한 점\\n2. 아쉬운 점 / 개선 방향 (음성 이미지가 있다면 파형을 분석해 목소리 톤/안정성 피드백 포함)\\n3. 모범 답변 방향성 제안"
    }}

    면접 질문: {question}
    지원자 답변: {answer}
    """
    
    contents = [prompt_text]
    if audio_image_bytes:
        contents.append({
            "mime_type": "image/png",
            "data": audio_image_bytes
        })
        
    for attempt in range(3):
        try:
            response = await client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text.strip())
        except Exception as e:
            print(f"Gemini API 피드백 생성 오류 (시도 {attempt+1}/3): {e}")
            await asyncio.sleep(10) # 제한(Rate Limit) 방지를 위한 2초 대기
            
    return {"feedback": "API 요청 제한으로 인해 피드백을 생성하지 못했습니다."}

async def analyze_answers_batch_with_gemini(qna_list: list) -> list:
    """
    여러 개의 면접 질문과 답변을 한 번의 API 호출로 묶어서(Batch) 분석합니다. (API 호출 횟수 최적화)
    """
    fallback_result = [{"feedback": "API 요청 제한으로 인해 피드백을 생성하지 못했습니다."} for _ in qna_list]
    
    if not GEMINI_API_KEY or not qna_list:
        return fallback_result

    prompt_text = """
    당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.
    아래에 제공된 여러 개의 면접 질문과 지원자의 답변, 그리고 음성 파형(멜 스펙트로그램) 이미지들을 한 번에 분석해 주세요.
    
    각 질문/답변에 대해 아래 항목을 포함하는 JSON 객체를 작성하고, 이를 배열(Array)에 담아 반환해야 합니다.
    배열의 순서는 입력된 질문의 순서와 정확히 동일해야 합니다.
    
    [
      {
        "content_score": 0~100 (내용 및 논리성),
        "relevance_score": 0~100 (질문 적합성),
        "clarity_score": 0~100 (명확성 및 전달력),
        "speech_score": 0~100 (음성 품질 및 톤 안정성),
        "posture_score": 0~100 (자세 및 태도 추론),
        "eye_contact_score": 0~100 (눈맞춤 및 시선 추론),
        "feedback": "1. 잘한 점\\n2. 아쉬운 점 / 개선 방향\\n3. 모범 답변 방향성 제안"
      }
    ]
    """
    
    contents = [prompt_text]
    for i, qna in enumerate(qna_list):
        contents.append(f"\n\n--- [질문 {i+1}] ---\n질문: {qna['question']}\n지원자 답변: {qna['answer']}\n")
        if qna.get('audio_image_bytes'):
            contents.append(f"(질문 {i+1}의 음성 파형 이미지)")
            contents.append({"mime_type": "image/png", "data": qna['audio_image_bytes']})
            
    for attempt in range(4):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL_NAME, contents=contents),
                timeout=60.0,
            )
            text = response.text.strip()
            if text.startswith("```"): text = text.split("\n", 1)[-1].replace("```", "").strip()
            
            result_json = json.loads(text)
            if isinstance(result_json, dict) and len(result_json) == 1: result_json = list(result_json.values())[0]
            if isinstance(result_json, list) and len(result_json) == len(qna_list): return result_json
        except Exception as e:
            wait_time = 15 + (attempt * 15)  # # 무료 API 제한을 피하기 위해 15초, 30초, 45초로 대기 시간을 길게 잡습니다.
            print(f"Gemini API 일괄(Batch) 분석 오류 (시도 {attempt+1}/4): {e} -> {wait_time}초 대기...")
            await asyncio.sleep(wait_time)
            
    return fallback_result

async def analyze_answer_with_gemini_short(question: str, answer: str, audio_image_bytes: bytes = None) -> str:
    """연습 면접 시 즉각적으로 보여줄 2~3문장 이내의 짧은 피드백 생성"""
    if not GEMINI_API_KEY:
        return "서버 오류: Gemini API 키가 설정되지 않았습니다."

    if not answer or answer.strip() == "답변 없음" or len(answer.strip()) < 5:
        return "답변 내용이 너무 짧아 피드백을 생성할 수 없었습니다."

    prompt_text = f"""
    당신은 친절하고 핵심을 잘 짚어주는 AI 면접관입니다.
    지원자의 면접 질문과 답변을 읽고 **2~3문장 이내의 아주 짧고 간결한 피드백**을 제공해 주세요.
    잘한 점과 개선할 점을 합쳐서 핵심만 빠르게 전달해야 합니다.

    면접 질문: {question}
    지원자 답변: {answer}
    """
    
    contents = [prompt_text]
        
    last_error = ""
    for attempt in range(2):
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(model=MODEL_NAME, contents=contents),
                timeout=10.0,
            )
            try:
                return response.text
            except ValueError:
                return "안전 필터에 의해 답변이 차단되었거나 생성할 수 없습니다."
        except Exception as e:
            last_error = str(e)
            print(f"Gemini API 짧은 피드백 생성 오류 (시도 {attempt+1}/2): {e}")
            await asyncio.sleep(5)
            
    return f"피드백 생성 실패 (에러: {last_error})"

async def generate_questions_from_resume(resume_text: str, category: str, num_questions: int = 5) -> list[str]:
    """
    자기소개서와 직무 카테고리를 기반으로 Gemini API를 통해 면접 질문을 생성합니다.
    JSON 형식으로 질문 리스트를 반환하도록 요청합니다.
    """
    if not GEMINI_API_KEY:
        raise ValueError("서버 오류: Gemini API 키가 설정되지 않았습니다.")

    ai_num = max(0, num_questions - 2)

    prompt = f"""
    당신은 10년 차 채용 담당자입니다. 
    지원자가 작성한 아래의 [지원자 정보 및 자기소개서] 내용을 꼼꼼히 읽고, 실제 면접에서 물어볼 만한 질문 {ai_num}개를 만들어주세요.

    [지침]
    1. 면접의 첫 2개 질문(자기소개, 지원동기)은 이미 진행되었다고 가정합니다.
    2. 특정 프로젝트나 경험에만 국한되지 않고, 지원자가 작성한 자기소개서의 전반적인 내용과 주장을 파악하거나 검증할 수 있는 맞춤형 질문을 생성하세요.
    3. 일반적이고 뻔한 질문은 철저히 배제하고, 반드시 입력된 텍스트 내용에 직접적으로 기반해야 합니다.
    4. 꼬리 질문(연쇄 질문)은 제외하고, 각각 독립적으로 대답할 수 있는 깔끔한 질문이어야 합니다.
    5. 반드시 JSON 형식의 문자열 배열(list of strings)로만 반환하세요. 예시: ["질문 1", "질문 2", "질문 3"]

    [직무 분야]
    {category}

    [지원자 정보 및 자기소개서]
    {resume_text}

    [출력 형식]
    JSON
    """

    try:
        # Gemini에 JSON 형식의 응답을 요청합니다.
        # 구버전(gemini-pro) 호환성을 위해 JSON config를 제거하고 프롬프트에 의존합니다.
        response = await client.aio.models.generate_content(model=MODEL_NAME, contents=prompt)
        
        text = response.text.strip()
        # 마크다운 코드 블록이 섞여올 경우 제거
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text[:-3]
                
        questions = json.loads(text.strip())
        
        # {"questions": ["질문1", "질문2"]} 형태로 올 경우 배열만 추출
        if isinstance(questions, dict):
            for val in questions.values():
                if isinstance(val, list):
                    questions = val
                    break

        fixed_questions = [
            "간단한 자기소개 부탁드립니다.",
            "해당 직무(또는 회사)에 지원하게 된 동기가 무엇인가요?"
        ]

        if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
            return fixed_questions + questions[:ai_num]
        raise ValueError("Gemini가 올바른 형식의 질문 리스트를 반환하지 않았습니다.")
    except Exception as e:
        print(f"Gemini 질문 생성 또는 JSON 파싱 중 오류 발생: {e}")
        return [] # 실패 시 빈 리스트 반환
