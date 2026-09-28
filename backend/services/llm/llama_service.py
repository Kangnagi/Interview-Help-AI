"""
파인튜닝된 Llama-3.2-3B-Instruct(LoRA)로 답변 피드백을 생성하는 서비스.

학습 범위(llama-finetune/training/train_New.jsonl, train_Experienced.jsonl):
  "질문 + 답변" 단일 쌍 -> 요약 + 평가 피드백 텍스트 생성
그래서 이 서비스가 직접 대체하는 것은 "feedback 텍스트" 뿐이다.

아직 이 어댑터로 학습되지 않아 당분간 Gemini에 그대로 맡기는 것:
  - content_score / relevance_score / clarity_score 등 숫자 점수 산정
    (2단계로 점수 라벨 데이터를 만들어 추가 파인튜닝 예정)
  - analyze_speech_with_spectrogram (음성 스펙트로그램 이미지 분석 — 텍스트 전용
    모델이라 대체 불가. 자체 음성 분석 모델로 별도 이식 예정이라 이 서비스에는
    구현하지 않음. 라우터에서 계속 gemini_service 것을 직접 import해서 쓴다.)

자기소개서 기반 질문 생성(generate_questions_from_resume)도 이 어댑터의 학습
범위 밖이라, LoRA 어댑터를 끈 베이스 Llama로 생성한다 (완전 로컬, Gemini 미사용).
"""
import asyncio
import logging
from contextlib import nullcontext
from typing import Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from core.config import settings
from services.llm import gemini_service
from services.llm.gemini_service import _parse_json

logger = logging.getLogger(__name__)

ADAPTER_NAME = "interview_feedback"


class LlamaService:
    """싱글톤. 베이스 모델 1개 + LoRA 어댑터 1개를 메모리에 유지한다."""

    _instance: Optional["LlamaService"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.tokenizer = None
            self.model = None
            # generate()는 스레드로 넘어가므로, 같은 모델 인스턴스에 대한 동시
            # 호출(어댑터 on/off 전환 포함)이 서로 섞이지 않도록 직렬화한다.
            self._lock = asyncio.Lock()
            self.initialized = True

    async def load_model(self):
        if self.model is not None:
            return
        logger.info("Llama 모델 로딩 중...")
        try:
            await asyncio.to_thread(self._load_model_sync)
            logger.info(f"Llama 로딩 완료 (device: {self.device})")
        except Exception as e:
            logger.error(f"Llama 로딩 실패 (Gemini 폴백으로 동작): {e}")
            self.model = None
            self.tokenizer = None

    def _load_model_sync(self):
        compute_dtype = torch.bfloat16 if (self.device == "cuda" and torch.cuda.is_bf16_supported()) else torch.float16

        quantization_config = None
        if settings.LLAMA_USE_4BIT:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
            )

        self.tokenizer = AutoTokenizer.from_pretrained(settings.LLAMA_ADAPTER_PATH)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            settings.LLAMA_BASE_MODEL,
            quantization_config=quantization_config,
            torch_dtype=compute_dtype,
            device_map={"": 0} if self.device == "cuda" else None,
        )
        self.model = PeftModel.from_pretrained(
            base_model, settings.LLAMA_ADAPTER_PATH, adapter_name=ADAPTER_NAME
        )
        self.model.eval()

    def _generate_sync(self, messages: list, max_new_tokens: int, use_adapter: bool) -> str:
        if use_adapter:
            self.model.set_adapter(ADAPTER_NAME)
            ctx = nullcontext()
        else:
            ctx = self.model.disable_adapter()

        with ctx:
            prompt_text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            encoding = self.tokenizer(prompt_text, return_tensors="pt").to(self.model.device)
            input_len = encoding["input_ids"].shape[-1]
            with torch.no_grad():
                output = self.model.generate(
                    **encoding,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.15,
                    no_repeat_ngram_size=3,
                    pad_token_id=self.tokenizer.pad_token_id,
                )
            return self.tokenizer.decode(output[0][input_len:], skip_special_tokens=True)

    async def generate(self, messages: list, max_new_tokens: int = None, use_adapter: bool = True) -> str:
        if self.model is None:
            raise RuntimeError("Llama 모델이 로드되지 않았습니다.")
        max_new_tokens = max_new_tokens or settings.LLAMA_MAX_NEW_TOKENS
        async with self._lock:
            return await asyncio.to_thread(self._generate_sync, messages, max_new_tokens, use_adapter)


llama_service = LlamaService()


def _feedback_messages(question: str, answer: str) -> list:
    return [
        {"role": "system", "content": "당신은 AI 면접 도우미입니다. 면접관의 질문과 지원자의 답변을 분석하여 핵심 내용을 요약하고 피드백을 제공합니다."},
        {"role": "user", "content": f"질문: {question}\n답변: {answer}\n\n위 지원자의 답변을 요약하고 평가해주세요."},
    ]


FEEDBACK_MAX_NEW_TOKENS = 200  # 학습 데이터의 assistant 응답 길이(평균 87, p99 134 토큰) 기준 여유치.
# 이보다 크게 잡으면 학습 분포를 벗어나 모델이 종료 시점을 못 찾고 같은 말을 반복하며 늘어진다.


async def generate_feedback_text(question: str, answer: str) -> Optional[str]:
    """파인튜닝된 어댑터로 단일 질문/답변 피드백 텍스트 생성. 실패 시 None (호출부가 Gemini 피드백을 그대로 씀)."""
    try:
        text = await llama_service.generate(
            _feedback_messages(question, answer), max_new_tokens=FEEDBACK_MAX_NEW_TOKENS, use_adapter=True
        )
        return text.strip() or None
    except Exception as e:
        logger.error(f"Llama 피드백 생성 실패: {e}")
        return None


async def analyze_answer_with_llama(question: str, answer: str, audio_image_bytes: bytes = None, kobert_scores: dict = None) -> dict:
    """점수(score/tip)는 당분간 Gemini가 산정하고, feedback 텍스트만 파인튜닝된 로컬 Llama로 교체."""
    result = await gemini_service.analyze_answer_with_gemini(question, answer, audio_image_bytes, kobert_scores)
    llama_feedback = await generate_feedback_text(question, answer)
    if llama_feedback:
        result = dict(result)
        result["feedback"] = llama_feedback
    return result


async def analyze_answers_batch_with_llama(qna_list: list) -> list:
    """점수는 Gemini 배치 결과를 그대로 쓰고, 문항별 feedback만 로컬 Llama로 순차 교체."""
    results = await gemini_service.analyze_answers_batch_with_gemini(qna_list)
    for i, qna in enumerate(qna_list):
        if i >= len(results) or not isinstance(results[i], dict):
            continue
        llama_feedback = await generate_feedback_text(qna["question"], qna["answer"])
        if llama_feedback:
            results[i] = dict(results[i])
            results[i]["feedback"] = llama_feedback
    return results


async def generate_overall_summary_with_llama(qna_feedbacks: list) -> dict:
    """베이스 Llama(어댑터 비활성화)로 종합 총평 생성. 실패하면 Gemini로 폴백."""
    if not qna_feedbacks:
        return await gemini_service.generate_overall_summary_with_gemini(qna_feedbacks)

    items_text = "\n\n".join(
        f"[질문 {i + 1}]\n질문: {item['question']}\n답변: {item['answer'] or '없음'}\n"
        f"종합 점수: {item.get('score', '?')}점\nAI 피드백: {(item.get('feedback') or '').strip()[:300] or '없음'}"
        for i, item in enumerate(qna_feedbacks)
    )
    messages = [
        {"role": "system", "content": "당신은 10년 차 전문 인사담당자입니다."},
        {"role": "user", "content": (
            "아래 면접 내용과 각 질문별 점수·피드백을 종합 분석하여 지원자 전체 평가를 작성하세요.\n"
            "반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지).\n\n"
            '{"feedback_summary":"전체 면접 종합 총평 3~4문장","strengths":["강점1","강점2"],"improvements":["개선점1","개선점2"]}\n\n'
            f"면접 내용:\n{items_text}"
        )},
    ]
    try:
        text = await llama_service.generate(messages, max_new_tokens=600, use_adapter=False)
        result = _parse_json(text)
        if isinstance(result, dict) and "feedback_summary" in result:
            result.setdefault("strengths", [])
            result.setdefault("improvements", [])
            return result
    except Exception as e:
        logger.error(f"Llama 총평 생성 실패, Gemini로 폴백: {e}")
    return await gemini_service.generate_overall_summary_with_gemini(qna_feedbacks)


async def generate_questions_from_resume(resume_text: str, category: str, num_questions: int = 5) -> list:
    """베이스 Llama(어댑터 비활성화)로 자기소개서 기반 질문 생성. 완전 로컬 — Gemini 미사용.

    실패 시 빈 리스트를 반환 (호출부인 routers/interview.py 가 자체 폴백 질문 목록을 사용).
    """
    ai_num = max(0, num_questions - 2)
    messages = [
        {"role": "system", "content": "당신은 채용 담당자입니다."},
        {"role": "user", "content": (
            f"아래 자기소개서를 바탕으로 면접 질문 {ai_num}개를 생성하세요.\n\n"
            "규칙:\n"
            "1. 자기소개·지원동기는 제외 (이미 진행됨)\n"
            "2. 자기소개서 내용에 직접 기반한 구체적 질문\n"
            "3. 독립적으로 답할 수 있는 질문 (꼬리 질문 제외)\n"
            "4. 순수 JSON 배열로만 반환: [\"질문1\", \"질문2\"]\n\n"
            f"직무: {category}\n\n"
            f"자기소개서:\n{resume_text[:2000]}"
        )},
    ]
    try:
        text = await llama_service.generate(messages, max_new_tokens=400, use_adapter=False)
        questions = _parse_json(text)
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
    except Exception as e:
        logger.error(f"Llama 질문 생성 실패: {e}")
    return []
