"""
파인튜닝된 Llama-3.2-3B-Instruct(LoRA)로 답변을 채점하고 피드백을 생성하는 서비스 — 채점에 Gemini 미사용.

베이스 모델 1개 위에 LoRA 어댑터 2개를 올려 두고 용도에 따라 바꿔 쓴다.
  - interview_score    : 질문+답변 -> {"score","feedback","tip"} JSON (메인 채점기)
                         training/generate_teacher_scores.py가 만든 선생님(Qwen2.5-14B) 데이터로 학습.
  - interview_feedback : 질문+답변 -> 피드백 텍스트 (채점 어댑터가 실패했을 때 피드백 폴백용)
  - 어댑터 없음(베이스) : 종합 총평, 자기소개서 기반 질문 생성

채점·총평이 실패하면(모델 미로딩, JSON 파싱 실패 등) Gemini로 넘기지 않고 규칙 기반으로 대체한다.
음성(발화) 분석은 services/voice/librosa_service.analyze_speech가 파형을 직접 분석한다.
→ 서비스 동작 경로에서 Gemini를 전혀 쓰지 않는다.
"""
import asyncio
import json
import logging
import os
import re
from contextlib import nullcontext
from typing import Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from core.config import settings

logger = logging.getLogger(__name__)


def _parse_json(text: str):
    """모델 출력에서 JSON 추출 — 마크다운 코드블록·앞뒤 텍스트 제거 후 파싱"""
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        text = m.group(1).strip() if m else re.sub(r"```(?:json)?", "", text).strip()
    for s, e in [("{", "}"), ("[", "]")]:
        si, ei = text.find(s), text.rfind(e)
        if si != -1 and ei > si:
            return json.loads(text[si:ei + 1])
    return json.loads(text)

FEEDBACK_ADAPTER = "interview_feedback"
SCORE_ADAPTER = "interview_score"

# training/generate_teacher_scores.py의 SCORING_SYSTEM_PROMPT와 글자 하나까지 같아야 한다.
# (채점 어댑터는 이 프롬프트로만 학습됐기 때문에 조금만 달라져도 출력 형식·점수가 흔들린다.)
SCORING_SYSTEM_PROMPT = (
    "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
    "지원자의 면접 질문과 답변을 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지).\n"
    "feedback의 각 항목은 1~2문장으로 간결하게 작성하세요.\n"
    '{"score":0~100,"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안",'
    '"tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}'
)
SCORE_MAX_NEW_TOKENS = 600   # 학습 라벨(JSON) 길이 기준 여유치 — 평가에서 60/60 완결됨
SCORE_BATCH_SIZE = 8         # 한 번에 채점할 답변 수 (VRAM·지연 시간 균형)
MAX_ANSWER_CHARS = 2000      # 비정상적으로 긴 답변은 잘라서 채점


class LlamaService:
    """싱글톤. 베이스 모델 1개 + LoRA 어댑터들을 메모리에 유지한다."""

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
            self.has_score_adapter = False
            # generate()는 스레드로 넘어가므로, 같은 모델 인스턴스에 대한 동시
            # 호출(어댑터 전환 포함)이 서로 섞이지 않도록 직렬화한다.
            self._lock = asyncio.Lock()
            self.initialized = True

    async def load_model(self):
        if self.model is not None:
            return
        logger.info("Llama 모델 로딩 중...")
        try:
            await asyncio.to_thread(self._load_model_sync)
            logger.info(f"Llama 로딩 완료 (device: {self.device}, 채점 어댑터: {self.has_score_adapter})")
        except Exception as e:
            logger.error(f"Llama 로딩 실패 (규칙 기반 채점으로 동작): {e}")
            self.model = None
            self.tokenizer = None
            self.has_score_adapter = False

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
        self.tokenizer.padding_side = "left"   # 여러 답변을 한 번에 생성(배치)할 때 필요

        base_model = AutoModelForCausalLM.from_pretrained(
            settings.LLAMA_BASE_MODEL,
            quantization_config=quantization_config,
            torch_dtype=compute_dtype,
            device_map={"": 0} if self.device == "cuda" else None,
        )
        self.model = PeftModel.from_pretrained(
            base_model, settings.LLAMA_ADAPTER_PATH, adapter_name=FEEDBACK_ADAPTER
        )
        if os.path.isdir(settings.LLAMA_SCORE_ADAPTER_PATH):
            self.model.load_adapter(settings.LLAMA_SCORE_ADAPTER_PATH, adapter_name=SCORE_ADAPTER)
            self.has_score_adapter = True
        else:
            logger.warning(f"채점 어댑터 없음: {settings.LLAMA_SCORE_ADAPTER_PATH} — 규칙 기반 채점으로 동작")
        self.model.eval()

    def _generate_sync(self, conversations: list, max_new_tokens: int, adapter: Optional[str], greedy: bool) -> list:
        if adapter:
            self.model.set_adapter(adapter)
            ctx = nullcontext()
        else:
            ctx = self.model.disable_adapter()

        if greedy:
            # 채점: 학습·평가와 같은 조건(탐욕적 디코딩)으로 — 같은 답변엔 항상 같은 점수
            gen_kwargs = {"do_sample": False}
        else:
            gen_kwargs = {
                "do_sample": True, "temperature": 0.7, "top_p": 0.9,
                "repetition_penalty": 1.15, "no_repeat_ngram_size": 3,
            }

        with ctx:
            prompts = [
                self.tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
                for m in conversations
            ]
            encoding = self.tokenizer(prompts, return_tensors="pt", padding=True).to(self.model.device)
            input_len = encoding["input_ids"].shape[-1]
            with torch.no_grad():
                output = self.model.generate(
                    **encoding,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=self.tokenizer.pad_token_id,
                    **gen_kwargs,
                )
            return [self.tokenizer.decode(o[input_len:], skip_special_tokens=True) for o in output]

    async def generate_batch(self, conversations: list, max_new_tokens: int,
                             adapter: Optional[str], greedy: bool = False) -> list:
        if self.model is None:
            raise RuntimeError("Llama 모델이 로드되지 않았습니다.")
        async with self._lock:
            return await asyncio.to_thread(self._generate_sync, conversations, max_new_tokens, adapter, greedy)

    async def generate(self, messages: list, max_new_tokens: int = None, use_adapter: bool = True) -> str:
        max_new_tokens = max_new_tokens or settings.LLAMA_MAX_NEW_TOKENS
        adapter = FEEDBACK_ADAPTER if use_adapter else None
        return (await self.generate_batch([messages], max_new_tokens, adapter))[0]


llama_service = LlamaService()


# ── 채점 ─────────────────────────────────────────────────────────────────────
def _scoring_messages(question: str, answer: str) -> list:
    # user 메시지 형식도 학습 데이터와 동일해야 한다.
    return [
        {"role": "system", "content": SCORING_SYSTEM_PROMPT},
        {"role": "user", "content": f"면접 질문: {question}\n지원자 답변: {answer[:MAX_ANSWER_CHARS]}"},
    ]


def _short_answer_result(answer: str) -> Optional[dict]:
    """빈 답변·극단적으로 짧은 답변은 모델 없이 바로 채점.

    점수는 사람 검토 결과("잘 모르겠습니다"·"asdasd"에 35점은 너무 높음)에 맞춰 낮게 잡았다.
    """
    if not answer:
        return {
            "score": 0,
            "feedback": "답변을 입력하지 않으셨습니다. 짧더라도 자신의 생각을 반드시 전달해야 합니다.",
            "tip": "모르더라도 관련 경험이나 학습 의지를 짧게 표현해 보세요.",
        }
    if len(answer) < 10:
        return {
            "score": 10,
            "feedback": "답변이 너무 짧습니다. 이유와 구체적인 경험을 덧붙여 주세요.",
            "tip": "STAR 기법(상황→과제→행동→결과)으로 구조화하면 짧은 답변도 풍성해집니다.",
        }
    # 인코딩이 깨져 '?'·'�'로 바뀐 답변 — 모델에 넣으면 내용 없이도 높은 점수가 나와서 따로 처리
    if sum(ch in "?�" for ch in answer) > len(answer) * 0.3:
        return {
            "score": 20,
            "feedback": "답변 내용을 인식하지 못했습니다 (글자가 깨져 저장됨). 다시 답변해 주세요.",
            "tip": "음성 답변이라면 마이크 상태를 확인하고 다시 녹음해 보세요.",
        }
    return None


def _parse_score_output(text: str) -> Optional[dict]:
    try:
        r = _parse_json(text)
        score = int(r["score"])
        feedback, tip = r.get("feedback"), r.get("tip")
        if not (0 <= score <= 100 and isinstance(feedback, str) and feedback.strip() and isinstance(tip, str)):
            return None
        return {"score": score, "feedback": feedback.strip(), "tip": tip.strip()}
    except Exception:
        return None


async def _fallback_result(question: str, answer: str) -> dict:
    """채점 어댑터를 못 쓸 때: 답변 길이 기반 점수 + (가능하면) 피드백 어댑터 텍스트. Gemini 미사용."""
    n = len(answer)
    score = 45 if n < 50 else 55 if n < 200 else 65
    feedback = await generate_feedback_text(question, answer) if llama_service.model is not None else None
    return {
        "score": score,
        "feedback": feedback or (
            "1. 질문에 대한 답변을 제시했습니다.\n"
            "2. 구체적인 경험과 수치를 더하면 설득력이 높아집니다.\n"
            "3. 상황→과제→행동→결과(STAR) 순서로 답변을 구조화해 보세요."
        ),
        "tip": "다음 답변에서는 구체적인 경험과 수치를 활용해 보세요.",
    }


def score_model_version() -> str:
    """지금 채점 어댑터 이름 (예: llama-score-adapter-v21) — DB에 점수와 함께 남겨 버전별로 비교한다."""
    return os.path.basename(os.path.normpath(settings.LLAMA_SCORE_ADAPTER_PATH))


async def score_answers(qna_list: list) -> list:
    """질문·답변 목록을 채점해 [{"score","feedback","tip","model_version"}]를 입력 순서대로 반환. 항상 길이가 같다.

    model_version: 채점 어댑터 이름 / "rule"(짧은·깨진 답변 규칙) / "fallback"(어댑터 실패 시 길이 기반)
    """
    answers = [(q.get("answer") or "").strip() for q in qna_list]
    results = [_short_answer_result(a) for a in answers]
    for r in results:
        if r is not None:
            r["model_version"] = "rule"
    todo = [i for i, r in enumerate(results) if r is None]

    if todo and llama_service.has_score_adapter:
        for b in range(0, len(todo), SCORE_BATCH_SIZE):
            chunk = todo[b:b + SCORE_BATCH_SIZE]
            try:
                texts = await llama_service.generate_batch(
                    [_scoring_messages(qna_list[i]["question"], answers[i]) for i in chunk],
                    SCORE_MAX_NEW_TOKENS, adapter=SCORE_ADAPTER, greedy=True,
                )
            except Exception as e:
                logger.error(f"Llama 채점 실패: {e}")
                continue
            for i, text in zip(chunk, texts):
                results[i] = _parse_score_output(text)
                if results[i] is None:
                    logger.warning(f"Llama 채점 출력 파싱 실패 — 규칙 기반 폴백: {text[:120]!r}")
                else:
                    results[i]["model_version"] = score_model_version()

    for i, r in enumerate(results):
        if r is None:
            results[i] = {**await _fallback_result(qna_list[i]["question"], answers[i]), "model_version": "fallback"}
    return results


# ── 피드백 텍스트 (폴백용 어댑터) ──────────────────────────────────────────────
def _feedback_messages(question: str, answer: str) -> list:
    return [
        {"role": "system", "content": "당신은 AI 면접 도우미입니다. 면접관의 질문과 지원자의 답변을 분석하여 핵심 내용을 요약하고 피드백을 제공합니다."},
        {"role": "user", "content": f"질문: {question}\n답변: {answer}\n\n위 지원자의 답변을 요약하고 평가해주세요."},
    ]


FEEDBACK_MAX_NEW_TOKENS = 200  # 학습 데이터의 assistant 응답 길이(평균 87, p99 134 토큰) 기준 여유치.
# 이보다 크게 잡으면 학습 분포를 벗어나 모델이 종료 시점을 못 찾고 같은 말을 반복하며 늘어진다.


async def generate_feedback_text(question: str, answer: str) -> Optional[str]:
    """피드백 어댑터로 단일 질문/답변 피드백 텍스트 생성. 실패 시 None."""
    try:
        text = await llama_service.generate(
            _feedback_messages(question, answer), max_new_tokens=FEEDBACK_MAX_NEW_TOKENS, use_adapter=True
        )
        return text.strip() or None
    except Exception as e:
        logger.error(f"Llama 피드백 생성 실패: {e}")
        return None


# ── 라우터가 쓰는 공개 함수 ─────────────────────────────────────────────────────
async def analyze_answer_with_llama(question: str, answer: str, audio_image_bytes: bytes = None, kobert_scores: dict = None) -> dict:
    """단일 답변 즉시 채점: {"score","feedback","tip"}. (audio_image_bytes, kobert_scores는 하위 호환용으로만 받음)"""
    return (await score_answers([{"question": question, "answer": answer}]))[0]


async def analyze_answers_batch_with_llama(qna_list: list) -> list:
    """면접 종료 후 일괄 채점. 기존 Gemini 배치 결과와 같은 키를 돌려준다.

    채점 어댑터는 종합 점수 하나만 내므로 content/relevance/clarity에 같은 값을 넣는다.
    speech/posture/eye_contact는 분석 파이프라인에서 음성·MediaPipe 결과로 덮어쓴다.
    """
    if not qna_list:
        return []
    scored = await score_answers(qna_list)
    return [
        {
            "content_score": r["score"],
            "relevance_score": r["score"],
            "clarity_score": r["score"],
            "speech_score": 70,
            "posture_score": 80,
            "eye_contact_score": 80,
            "feedback": r["feedback"],
            "tip": r["tip"],
            "model_version": r["model_version"],
        }
        for r in scored
    ]


def _feedback_line(feedback: str, number: int) -> Optional[str]:
    """'1. ...\\n2. ...\\n3. ...' 형식 피드백에서 n번째 항목 문장을 꺼낸다."""
    m = re.search(rf"(?m)^\s*{number}\.\s*(.+?)\s*$", feedback or "")
    return m.group(1) if m else None


def _rule_based_summary(qna_feedbacks: list) -> dict:
    """Llama 총평 생성이 실패했을 때: 질문별 점수·피드백으로 총평을 만든다 (Gemini 미사용).

    강점 = 점수가 높은 질문들의 피드백 1번(잘한 점), 개선점 = 점수가 낮은 질문들의 피드백 2번(아쉬운 점).
    """
    if not qna_feedbacks:
        return {"feedback_summary": "분석할 답변이 없습니다.", "strengths": [], "improvements": []}

    scored = [item for item in qna_feedbacks if isinstance(item.get("score"), (int, float))]
    avg = round(sum(i["score"] for i in scored) / len(scored)) if scored else None
    level = ("전반적으로 구체적이고 완성도 높은 답변을 했습니다" if avg is not None and avg >= 75 else
             "질문에 맞게 답했지만 구체적인 사례와 근거를 보완하면 더 좋아집니다" if avg is not None and avg >= 50 else
             "답변의 구체성과 완성도를 높이는 연습이 필요합니다")
    summary = f"총 {len(qna_feedbacks)}개 질문" + (f"의 평균 점수는 {avg}점으로, {level}." if avg is not None else f"에 답했습니다. {level}.")
    if len(scored) >= 2:
        best, worst = max(scored, key=lambda i: i["score"]), min(scored, key=lambda i: i["score"])
        if best["score"] != worst["score"]:
            summary += (f" 가장 좋았던 답변은 '{best['question'][:30]}'({best['score']}점), "
                        f"가장 보완이 필요한 답변은 '{worst['question'][:30]}'({worst['score']}점)입니다.")

    ordered = sorted(scored, key=lambda i: i["score"], reverse=True)
    strengths = [s for s in (_feedback_line(i.get("feedback"), 1) for i in ordered[:3]) if s]
    improvements = [s for s in (_feedback_line(i.get("feedback"), 2) for i in reversed(ordered[-3:])) if s]
    return {"feedback_summary": summary, "strengths": strengths, "improvements": improvements}


async def generate_overall_summary_with_llama(qna_feedbacks: list) -> dict:
    """베이스 Llama(어댑터 비활성화)로 종합 총평 생성. 실패하면 규칙 기반 총평으로 대체."""
    if not qna_feedbacks:
        return _rule_based_summary(qna_feedbacks)

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
        logger.error(f"Llama 총평 생성 실패, 규칙 기반 총평으로 대체: {e}")
    return _rule_based_summary(qna_feedbacks)


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
