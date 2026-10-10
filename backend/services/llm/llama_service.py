"""
파인튜닝된 Llama-3.2-3B-Instruct(LoRA)로 답변을 채점하고 피드백을 생성하는 서비스 — 채점에 Gemini 미사용.

베이스 모델 1개 위에 LoRA 어댑터 2개를 올려 두고 용도에 따라 바꿔 쓴다.
  - interview_score    : 질문+답변 -> {"score","feedback","tip"} JSON (메인 채점기)
                         training/generate_teacher_scores.py가 만든 선생님(Qwen2.5-14B) 데이터로 학습.
  - interview_feedback : 질문+답변 -> 피드백 텍스트 (채점 어댑터가 실패했을 때 피드백 폴백용)
  - 어댑터 없음(베이스) : 한국어 글쓰기 모델을 못 불러왔을 때의 질문 생성 · 종합 총평

질문 생성 · 종합 총평은 한국어 글쓰기 모델(settings.TEXT_MODEL, 기본 Bllossom-3B — Llama-3.2-3B를 한국어
약 150GB로 추가 학습한 모델)이 따로 맡는다. 같은 7개 직무 비교에서 쓸 수 있는 질문 비율이 베이스 Llama 54% →
Bllossom 97% (베이스 Llama는 베트남어·태국어·힌디어·일본어가 자주 섞임). 채점은 a1 어댑터가 Llama 위에서
학습됐으므로 그대로 Llama.

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
    # strict=False: 모델이 문자열 안에 줄바꿈 기호 대신 실제 줄바꿈을 쓰는 경우(b3 평가 427개 중 1건)도 받아 준다
    for s, e in [("{", "}"), ("[", "]")]:
        si, ei = text.find(s), text.rfind(e)
        if si != -1 and ei > si:
            return json.loads(text[si:ei + 1], strict=False)
    return json.loads(text, strict=False)

FEEDBACK_ADAPTER = "interview_feedback"
SCORE_ADAPTER = "interview_score"
QGEN_ADAPTER = "interview_qgen"   # 질문 전용 (자기소개서 질문 풀 · 꼬리 질문) — LLAMA_QGEN_ADAPTER_PATH가 있을 때만

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

# 베이스 모델로 한국어 글(질문·총평)을 쓸 때의 샘플링 설정.
# 기본 설정의 no_repeat_ngram_size=3은 한국어에서 해롭다 — 같은 조사·어미가 다시 나오는 것까지 막고,
# 드문 한글 글자는 바이트 조각 토큰 여러 개로 쪼개지는데(실제 서비스 문장 기준 토큰의 약 5%) 그 조각 조합까지 막혀
# '인터�efe스'처럼 글자가 깨지거나 일본어·영어로 새었다.
KOREAN_TEXT_SAMPLING = {"do_sample": True, "temperature": 0.6, "top_p": 0.9, "repetition_penalty": 1.05}

_FOREIGN_OR_BROKEN = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿�]")  # 가나·한자·깨진 글자
_LOWER_EN_PHRASE = re.compile(r"\b[a-z]+\s+[a-z]+\b")  # 'how to'처럼 소문자 영어 단어가 이어짐 (기술 용어는 보통 대문자 시작)


_LOWER_EN_WORD = re.compile(r"(?<![A-Za-z])[a-z]{2,}(?![A-Za-z])")  # 소문자로만 된 영어 단어 ('experiences에서', 'comment')


def _is_clean_korean(text: str, min_hangul_ratio: float = 0.6, strict: bool = False) -> bool:
    """깨진 글자·외국 문자·영어 문장이 섞이지 않은 한국어 글인지.

    글자는 한글·영문 알파벳만 허용한다 (베트남어 'bảo', 힌디어 'बत' 같은 다른 문자는 거부).
    strict=True(질문)면 소문자 영어 단어도 거부 — 기술 용어는 보통 대문자로 시작한다 (Java, Kafka, HBM).
    """
    if not isinstance(text, str) or _FOREIGN_OR_BROKEN.search(text) or _LOWER_EN_PHRASE.search(text):
        return False
    letters = [c for c in text if c.isalpha()]
    if any(not ("가" <= c <= "힣" or c.isascii()) for c in letters):
        return False
    if strict and _LOWER_EN_WORD.search(text):
        return False
    hangul = sum("가" <= c <= "힣" for c in letters)
    return bool(letters) and hangul / len(letters) >= min_hangul_ratio


_QUESTION_ENDINGS = ("?", "요", "까", "오", "궁금합니다", "바랍니다")      # '~했습니다.' 같은 서술문은 제외
_NOT_A_QUESTION_START = ("질문", "다음 질문", "저는", "제가", "무엇")      # '질문1.', '저는 … 담당했습니다' 등
_PLACEHOLDER = re.compile(r"^(강점|개선점|질문)\s*\d*$|한 문장$")            # 형식 예시를 그대로 채운 항목 ('강점1', '…강점 한 문장')


def is_valid_question(question: str) -> bool:
    """면접 질문으로 쓸 수 있는지 — 깨끗한 한국어, 적당한 길이, 질문·요청 형태로 끝남."""
    if not isinstance(question, str):
        return False
    q = question.strip()
    return (15 <= len(q) <= 200 and q[0] not in "[{\"'" and not q.startswith(_NOT_A_QUESTION_START)
            and '", "' not in q and "assistant" not in q          # 여러 질문이 한 줄로 붙었거나 대화 표시가 섞인 출력
            and _is_clean_korean(q, strict=True) and q.rstrip(" .!\"'”").endswith(_QUESTION_ENDINGS))


def _is_clean_summary_item(text: str) -> bool:
    """총평의 강점·개선점 한 항목 — 깨끗한 한국어이고 '강점1' 같은 빈 틀이 아님."""
    return _is_clean_korean(text, 0.5) and not _PLACEHOLDER.search(text.strip()) and len(text.strip()) >= 6


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
            self.has_feedback_adapter = False
            self.has_qgen_adapter = False
            # generate()는 스레드로 넘어가므로, 같은 모델 인스턴스에 대한 동시
            # 호출(어댑터 전환 포함)이 서로 섞이지 않도록 직렬화한다.
            self._lock = asyncio.Lock()
            # 한국어 글쓰기 모델 (질문 생성 · 종합 총평) — 채점 모델과 따로 두므로 잠금도 따로
            self.text_model = None
            self.text_tokenizer = None
            self._text_lock = asyncio.Lock()
            self.initialized = True

    async def load_model(self):
        if self.model is not None:
            return
        logger.info("Llama 모델 로딩 중...")
        try:
            await asyncio.to_thread(self._load_model_sync)
            logger.info(f"Llama 로딩 완료 (device: {self.device}, 채점 어댑터: {self.has_score_adapter}, 질문 어댑터: {self.has_qgen_adapter})")
        except Exception as e:
            logger.error(f"Llama 로딩 실패 (규칙 기반 채점으로 동작): {e}")
            self.model = None
            self.tokenizer = None
            self.has_score_adapter = False
            self.has_feedback_adapter = False
            self.has_qgen_adapter = False

        if settings.TEXT_MODEL:
            logger.info(f"한국어 글쓰기 모델 로딩 중: {settings.TEXT_MODEL}")
            try:
                await asyncio.to_thread(self._load_text_model_sync)
                logger.info("한국어 글쓰기 모델 로딩 완료 (질문 생성 · 총평)")
            except Exception as e:
                logger.error(f"한국어 글쓰기 모델 로딩 실패 — 질문 생성 · 총평은 베이스 Llama로: {e}")
                self.text_model = None
                self.text_tokenizer = None

    def _load_text_model_sync(self):
        dtype = torch.bfloat16 if (self.device == "cuda" and torch.cuda.is_bf16_supported()) else torch.float16
        self.text_tokenizer = AutoTokenizer.from_pretrained(settings.TEXT_MODEL)
        self.text_model = AutoModelForCausalLM.from_pretrained(
            settings.TEXT_MODEL, dtype=dtype, device_map={"": 0} if self.device == "cuda" else None,
        ).eval()

    def _generate_text_sync(self, messages: list, max_new_tokens: int, sampling: dict) -> str:
        tok = self.text_tokenizer
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        enc = tok(prompt, return_tensors="pt").to(self.text_model.device)
        # 대화 한 턴의 끝(<|eot_id|>)에서 멈추게 한다 — Bllossom은 generation_config에 이게 빠져 있어서
        # 지정하지 않으면 'assistant…'를 붙이며 같은 답을 최대 길이까지 반복했다
        eos = [tok.eos_token_id, tok.convert_tokens_to_ids("<|eot_id|>")]
        with torch.no_grad():
            out = self.text_model.generate(**enc, max_new_tokens=max_new_tokens, pad_token_id=tok.eos_token_id,
                                           eos_token_id=eos, **sampling)
        return tok.decode(out[0][enc["input_ids"].shape[-1]:], skip_special_tokens=True)

    async def generate_text(self, messages: list, max_new_tokens: int) -> str:
        """한국어 글(질문 · 총평) 생성 — 한국어 글쓰기 모델이 있으면 그것으로, 없으면 베이스 Llama로."""
        if self.text_model is not None:
            async with self._text_lock:
                return await asyncio.to_thread(self._generate_text_sync, messages, max_new_tokens, KOREAN_TEXT_SAMPLING)
        return await self.generate(messages, max_new_tokens=max_new_tokens, use_adapter=False,
                                   sampling=KOREAN_TEXT_SAMPLING)

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

        # 피드백 어댑터는 선택 — 기본 모델을 Bllossom으로 바꾸면 Llama 위에서 학습한 이 어댑터는 맞지 않아 비워 둔다
        # (LLAMA_ADAPTER_PATH=). 그때 예비 피드백은 어댑터 없이 기본 모델이 쓴다.
        feedback_dir = settings.LLAMA_ADAPTER_PATH if settings.LLAMA_ADAPTER_PATH and os.path.isdir(settings.LLAMA_ADAPTER_PATH) else None
        score_dir = settings.LLAMA_SCORE_ADAPTER_PATH if os.path.isdir(settings.LLAMA_SCORE_ADAPTER_PATH) else None

        # 토크나이저: 피드백 어댑터 → 채점 어댑터(학습 때 저장된 그대로) → 기본 모델 순
        self.tokenizer = AutoTokenizer.from_pretrained(feedback_dir or score_dir or settings.LLAMA_BASE_MODEL)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.tokenizer.padding_side = "left"   # 여러 답변을 한 번에 생성(배치)할 때 필요

        base_model = AutoModelForCausalLM.from_pretrained(
            settings.LLAMA_BASE_MODEL,
            quantization_config=quantization_config,
            torch_dtype=compute_dtype,
            device_map={"": 0} if self.device == "cuda" else None,
        )
        if feedback_dir:
            self.model = PeftModel.from_pretrained(base_model, feedback_dir, adapter_name=FEEDBACK_ADAPTER)
            self.has_feedback_adapter = True
            if score_dir:
                self.model.load_adapter(score_dir, adapter_name=SCORE_ADAPTER)
        elif score_dir:
            self.model = PeftModel.from_pretrained(base_model, score_dir, adapter_name=SCORE_ADAPTER)
        else:
            self.model = base_model
        self.has_score_adapter = score_dir is not None
        # 질문 전용 어댑터 (선택) — 없으면 질문은 키워드 + 질문 틀 방식
        qgen_dir = settings.LLAMA_QGEN_ADAPTER_PATH if settings.LLAMA_QGEN_ADAPTER_PATH and os.path.isdir(settings.LLAMA_QGEN_ADAPTER_PATH) else None
        if qgen_dir:
            if isinstance(self.model, PeftModel):
                self.model.load_adapter(qgen_dir, adapter_name=QGEN_ADAPTER)
            else:
                self.model = PeftModel.from_pretrained(base_model, qgen_dir, adapter_name=QGEN_ADAPTER)
            self.has_qgen_adapter = True
        if not score_dir:
            logger.warning(f"채점 어댑터 없음: {settings.LLAMA_SCORE_ADAPTER_PATH} — 규칙 기반 채점으로 동작")
        self.model.eval()

    def _generate_sync(self, conversations: list, max_new_tokens: int, adapter: Optional[str], greedy: bool,
                       sampling: Optional[dict] = None) -> list:
        if adapter:
            self.model.set_adapter(adapter)
            ctx = nullcontext()
        elif isinstance(self.model, PeftModel):
            ctx = self.model.disable_adapter()
        else:
            ctx = nullcontext()   # 어댑터가 하나도 없는 경우

        if greedy:
            # 채점: 학습·평가와 같은 조건(탐욕적 디코딩)으로 — 같은 답변엔 항상 같은 점수
            gen_kwargs = {"do_sample": False}
        elif sampling is not None:
            gen_kwargs = sampling
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
            # 대화 한 턴의 끝(<|eot_id|>)에서 멈춤 — 기본 모델이 Bllossom이면 generation_config에 없어 직접 지정해야 한다
            eos = [self.tokenizer.eos_token_id, self.tokenizer.convert_tokens_to_ids("<|eot_id|>")]
            with torch.no_grad():
                output = self.model.generate(
                    **encoding,
                    max_new_tokens=max_new_tokens,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=eos,
                    **gen_kwargs,
                )
            return [self.tokenizer.decode(o[input_len:], skip_special_tokens=True) for o in output]

    async def generate_batch(self, conversations: list, max_new_tokens: int,
                             adapter: Optional[str], greedy: bool = False, sampling: Optional[dict] = None) -> list:
        if self.model is None:
            raise RuntimeError("Llama 모델이 로드되지 않았습니다.")
        async with self._lock:
            return await asyncio.to_thread(self._generate_sync, conversations, max_new_tokens, adapter, greedy, sampling)

    async def generate(self, messages: list, max_new_tokens: int = None, use_adapter: bool = True,
                       sampling: Optional[dict] = None) -> str:
        max_new_tokens = max_new_tokens or settings.LLAMA_MAX_NEW_TOKENS
        adapter = FEEDBACK_ADAPTER if (use_adapter and self.has_feedback_adapter) else None
        return (await self.generate_batch([messages], max_new_tokens, adapter, sampling=sampling))[0]


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
        # 피드백 어댑터가 없으면(기본 모델 Bllossom) 기본 모델이 한국어 글쓰기 샘플링으로 쓴다
        text = await llama_service.generate(
            _feedback_messages(question, answer), max_new_tokens=FEEDBACK_MAX_NEW_TOKENS, use_adapter=True,
            sampling=None if llama_service.has_feedback_adapter else KOREAN_TEXT_SAMPLING,
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


STRENGTH_MIN_SCORE = 40   # 가장 높은 질문 점수가 이보다 낮으면 강점을 쓰지 않는다
# 답변이 모두 짧아 질문별 피드백에서 개선점을 뽑을 수 없을 때 (예전엔 강점 · 개선점이 둘 다 빈칸이었다)
DEFAULT_IMPROVEMENTS = [
    "질문마다 본인의 경험 하나를 골라 상황 → 본인이 한 행동 → 결과 순서로 1분 안팎으로 말해 보세요",
    "'잘 모르겠습니다'로 끝내기보다 관련된 경험이나 지금 알고 있는 만큼이라도 이유와 함께 말해 보세요",
]


def _question_label(item: dict, index: int) -> str:
    """총평에서 질문을 부르는 이름 — 결과 화면의 'Q{order}'와 같게 (예전엔 질문 문장을 30자에서 잘라 인용해 따옴표가 겹쳤다)."""
    order = item.get("order")
    return f"Q{order}" if isinstance(order, int) else f"{index + 1}번째 질문"


def _model_feedback(item: dict) -> bool:
    """채점 모델이 쓴 '1. 2. 3.' 피드백인지 (짧은 답변 · 빈 답변은 규칙 문구 한 줄)."""
    return _feedback_line(item.get("feedback"), 1) is not None


def _rule_based_summary(qna_feedbacks: list) -> dict:
    """Llama 총평 생성이 실패했을 때: 질문별 점수·피드백으로 총평을 만든다 (Gemini 미사용).

    강점 = 점수가 높은 질문들의 피드백 1번(잘한 점), 개선점 = 점수가 낮은 질문들의 피드백 2번(아쉬운 점).
    짧은 답변의 규칙 문구('답변이 너무 짧습니다…')는 번호가 없어 그 문구를 그대로 개선점으로 쓴다.
    """
    if not qna_feedbacks:
        return {"feedback_summary": "분석할 답변이 없습니다.", "strengths": [], "improvements": list(DEFAULT_IMPROVEMENTS)}

    labeled = [(item, _question_label(item, i)) for i, item in enumerate(qna_feedbacks)]
    scored = [(item, label) for item, label in labeled if isinstance(item.get("score"), (int, float))]
    avg = round(sum(i["score"] for i, _ in scored) / len(scored)) if scored else None
    if qna_feedbacks and not any(_model_feedback(i) for i in qna_feedbacks):
        summary = (f"총 {len(qna_feedbacks)}개 질문 모두 답변이 너무 짧아 내용을 평가하기 어려웠습니다. "
                   "다음 면접에서는 질문마다 본인의 경험을 구체적으로 이야기해 보세요.")
    else:
        level = ("전반적으로 구체적이고 완성도 높은 답변을 했습니다" if avg is not None and avg >= 75 else
                 "질문에 맞게 답했지만 구체적인 사례와 근거를 보완하면 더 좋아집니다" if avg is not None and avg >= 50 else
                 "답변의 구체성과 완성도를 높이는 연습이 필요합니다")
        summary = f"총 {len(qna_feedbacks)}개 질문" + (f"의 평균 점수는 {avg}점으로, {level}." if avg is not None else f"에 답했습니다. {level}.")
        if len(scored) >= 2:
            (best, best_label), (worst, worst_label) = max(scored, key=lambda s: s[0]["score"]), min(scored, key=lambda s: s[0]["score"])
            if best["score"] != worst["score"]:
                summary += (f" 가장 좋았던 답변은 {best_label}({round(best['score'])}점), "
                            f"가장 보완이 필요한 답변은 {worst_label}({round(worst['score'])}점)입니다.")

    ordered = sorted((i for i, _ in scored), key=lambda i: i["score"], reverse=True)
    strengths = []
    if ordered and ordered[0]["score"] >= STRENGTH_MIN_SCORE:
        strengths = [s for s in (_feedback_line(i.get("feedback"), 1) for i in ordered[:3]) if s]
    improvements = []
    for i in reversed(ordered[-3:]):
        line = _feedback_line(i.get("feedback"), 2)
        if line is None:   # 규칙 문구 — 음성 코칭이 뒤에 붙어 있으면 떼어 낸다
            line = (i.get("feedback") or "").split("\n\n")[0].strip() or None
        if line and line not in improvements:
            improvements.append(line)
    if not any(_model_feedback(i) for i in qna_feedbacks):   # 모두 짧은 답변 — 같은 문구 하나뿐이라 일반 안내를 덧붙인다
        improvements = (improvements + [s for s in DEFAULT_IMPROVEMENTS if s not in improvements])[:3]
    return {"feedback_summary": summary, "strengths": strengths, "improvements": improvements or list(DEFAULT_IMPROVEMENTS)}


def _summary_messages(qna_feedbacks: list) -> list:
    items_text = "\n\n".join(
        f"[{_question_label(item, i)}]\n질문: {item['question']}\n답변: {item['answer'] or '없음'}\n"
        f"종합 점수: {item.get('score', '?')}점\nAI 피드백: {(item.get('feedback') or '').strip()[:300] or '없음'}"
        for i, item in enumerate(qna_feedbacks)
    )
    return [
        {"role": "system", "content": "당신은 10년 차 전문 인사담당자입니다."},
        {"role": "user", "content": (
            "아래 면접 내용과 각 질문별 점수·피드백을 종합 분석하여 지원자 전체 평가를 작성하세요.\n"
            "반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지). 강점·개선점은 각각 2~3개,\n"
            "답변 내용에 근거한 구체적인 한 문장으로 쓰세요.\n\n"
            # ('강점1' 같은 짧은 틀을 주면 3B 모델이 그 글자를 그대로 채워 넣어서, 설명형 틀을 준다)
            '{"feedback_summary":"전체 면접 종합 총평 3~4문장",'
            '"strengths":["답변에서 드러난 구체적인 강점 한 문장"],'
            '"improvements":["다음 면접을 위한 구체적인 개선점 한 문장"]}\n\n'
            f"면접 내용:\n{items_text}"
        )},
    ]


_TEMPLATE_ECHO = re.compile(r"종합 총평\s*\d+\s*~\s*\d+\s*문장")   # 형식 예시를 그대로 베낀 총평


def _parse_summary(text: str) -> dict:
    """총평 출력 → {"feedback_summary", "strengths", "improvements"} — 3B 모델의 흔한 형식 실수를 받아 준다.

    실제로 본 실수: 강점을 목록 대신 문장 하나로 씀, 키 이름 오타('strongnesses'),
    따옴표·쉼표가 빠져 JSON이 깨짐. 깨지면 키별로 값을 정규식으로 꺼낸다.
    """
    try:
        raw = _parse_json(text)
    except Exception:
        raw = None
    if not isinstance(raw, dict):
        raw = {}
        m = re.search(r'"feedback_summary"\s*:\s*"(.+?)"(?=\s*[,}\n"])', text, re.S)   # 뒤 쉼표가 빠져도
        if m:
            raw["feedback_summary"] = m.group(1)
        for key in ("strengths", "improvements"):
            m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', text, re.S)
            if m:
                raw[key] = re.findall(r'"((?:[^"\\]|\\.)+)"', m.group(1))
    out = {"feedback_summary": raw.get("feedback_summary") if isinstance(raw.get("feedback_summary"), str) else None}
    for key, prefix in (("strengths", "str"), ("improvements", "impro")):
        val = raw.get(key)
        if val is None:   # 키 이름 오타
            val = next((v for k, v in raw.items() if isinstance(k, str) and k.lower().startswith(prefix)), None)
        if isinstance(val, str):
            val = [val]
        out[key] = [s.strip() for s in val if isinstance(s, str)] if isinstance(val, list) else []
    return out


async def generate_overall_summary_with_llama(qna_feedbacks: list) -> dict:
    """한국어 글쓰기 모델(없으면 베이스 Llama)로 종합 총평 생성. 실패하면 규칙 기반 총평으로 대체."""
    if not qna_feedbacks or not SUMMARY_USE_MODEL:
        return _rule_based_summary(qna_feedbacks)
    # 답변이 모두 짧으면(모델이 채점하지 않은 규칙 문구뿐) 모델에 맡기지 않는다
    # — 10/4 실제 면접: '네' 같은 답변 5개에 모델이 '직무에 대한 이해가 깊었음'을 강점으로 썼다
    if not any(_model_feedback(i) for i in qna_feedbacks):
        return _rule_based_summary(qna_feedbacks)

    messages = _summary_messages(qna_feedbacks)
    # 샘플링이라 가끔 JSON이 깨진다(쉼표 누락 등) → 한 번 더 생성해 보고, 그래도 안 되면 규칙 기반 총평
    for attempt in range(SUMMARY_GEN_ATTEMPTS):
        try:
            text = await llama_service.generate_text(messages, max_new_tokens=600)
            result = _parse_summary(text)
            summary_text = result.get("feedback_summary")
            if (_is_clean_korean(summary_text, 0.5) and len(summary_text.strip()) >= 20
                    and not _TEMPLATE_ECHO.search(summary_text)):
                # 강점·개선점은 깨진 항목만 빼고 쓰고, 비면 질문별 피드백에서 뽑은 규칙 기반 항목으로 채운다
                rule = _rule_based_summary(qna_feedbacks)
                for key in ("strengths", "improvements"):
                    items = result.get(key)
                    items = [s for s in items if _is_clean_summary_item(s)] if isinstance(items, list) else []
                    result[key] = items or rule[key]
                # 채점 점수가 모두 낮으면 모델이 쓴 강점도 근거가 없다 (규칙 쪽과 같은 기준)
                scores = [i["score"] for i in qna_feedbacks if isinstance(i.get("score"), (int, float))]
                if scores and max(scores) < STRENGTH_MIN_SCORE:
                    result["strengths"] = []
                return result
            logger.warning(f"총평 형식·글자 이상 ({attempt + 1}회차): {text[:120]!r}")
        except Exception as e:
            logger.warning(f"총평 생성 실패 ({attempt + 1}회차): {e}")
    logger.error("총평 생성 실패 — 규칙 기반 총평으로 대체")
    return _rule_based_summary(qna_feedbacks)


QUESTION_GEN_ATTEMPTS = 2   # 깨진 질문을 걸러내고 모자라면 한 번 더 생성 (한 번에 약 수 초)
SUMMARY_GEN_ATTEMPTS = 2    # 총평 JSON이 깨지면 한 번 더 (한 번에 약 2~3초)
# 총평을 베이스 모델에 맡길지 — 10/6 시험(같은 면접 2개 × 5회)에서 10번 중 약 4번이 지시문을 되풀이한 빈 총평
# ('강점과 개선점을 종합하여 총평을 작성하였습니다'), 21점 면접에 '역량을 잘 제시했습니다', 개선점을 강점 칸에 씀.
# → 꺼 두고 규칙 기반 총평(평균 · 최고/최저 질문 + 채점 모델이 질문별로 쓴 잘한 점 · 아쉬운 점)을 쓴다.
#   총평 전용 학습 등으로 품질이 확인되면 다시 켠다.
SUMMARY_USE_MODEL = False


def _question_messages(resume_text: str, count: int) -> list:
    return [
        {"role": "system", "content": "당신은 한국 기업의 채용 면접관입니다. 모든 질문은 자연스러운 한국어 존댓말로만 작성합니다."},
        {"role": "user", "content": (
            f"아래 지원 정보를 바탕으로 면접 질문 {count}개를 만드세요.\n\n"
            "규칙:\n"
            "1. 자기소개·지원동기 질문은 제외 (이미 진행됨)\n"
            "2. 지원 회사·직무·직무 설명에 나온 내용과 직접 연결된 구체적인 질문\n"
            "3. 한 질문은 한 문장, 40~120자, '~말씀해 주세요.' 또는 '~무엇인가요?'처럼 끝내기\n"
            "4. 한국어로만 작성 (일본어·한자·영어 문장 금지, 기술 용어만 영어 허용)\n"
            "5. 지원자의 실제 경험(상황, 본인이 한 일, 결과)을 묻는 질문을 우선\n"
            "6. 순수 JSON 배열로만 출력: [\"질문1\", \"질문2\"]\n\n"
            # (구체적인 예시 문장을 넣으면 3B 모델이 다른 직무 면접에도 그대로 베껴 써서 넣지 않는다)
            f"지원 정보:\n{resume_text[:2000]}"
        )},
    ]


def _extract_questions(text: str) -> list:
    """모델 출력에서 질문 문자열 목록을 꺼낸다 (JSON 배열 · {"questions": [...]} · 번호 목록 모두 허용)."""
    try:
        parsed = _parse_json(text)
        if isinstance(parsed, dict):
            parsed = next((v for v in parsed.values() if isinstance(v, list)), [])
        if isinstance(parsed, list):
            return [q for q in parsed if isinstance(q, str)]
    except Exception:
        pass
    # JSON이 깨졌으면 줄 단위로 ('1. 질문', '- 질문', '"질문",')
    return [re.sub(r'^\s*(?:\d+[.)]|[-•*])\s*', "", line).strip(' ",[]')
            for line in text.splitlines() if line.strip()]


async def _generate_job_questions(info_text: str, count: int) -> list:
    """직무 정보(회사 · 직무 · 직무 설명 · 인재상)로 직무 질문 생성 — 모델이 문장을 직접 쓴다.

    3B 모델은 깨진 질문(외국 문자·영어 섞임, 서술문, 여러 질문이 한 줄로 붙음)을 낼 때가 있다
    → is_valid_question으로 거르고, 모자라면 한 번 더 생성한다. 그래도 모자라면 있는 만큼만 반환한다.
    """
    questions, seen = [], set()
    for attempt in range(QUESTION_GEN_ATTEMPTS):
        try:
            text = await llama_service.generate_text(_question_messages(info_text, count + 1), max_new_tokens=500)
        except Exception as e:
            logger.error(f"Llama 질문 생성 실패: {e}")
            break
        candidates = [q.strip() for q in _extract_questions(text)]
        valid = [q for q in candidates if is_valid_question(q) and not _AWKWARD_QUESTION.search(q.strip()) and q not in seen]
        logger.info(f"직무 질문 생성 {attempt + 1}회차: 후보 {len(candidates)}개 중 사용 가능 {len(valid)}개")
        for q in valid:
            seen.add(q)
            questions.append(q)
        if len(questions) >= count:
            break
    return questions[:count]


# ── 자기소개서 키워드 질문 ─────────────────────────────────────────────────────
# 10/6 시험(가상 자기소개서 3개): 모델에게 질문을 통째로 맡기면 자기소개서 키워드가 든 질문이 12개 중 2개.
# 키워드 추출은 잘하지만(경험 3~4개를 정확히 고름) 질문 문장을 쓰게 하면 답을 대신 쓰거나 지시문을 베꼈다.
# → 모델은 추출만 하고, 질문은 아래 틀에 키워드를 넣어 만든다 (깨진 문장이 나올 수 없음).
SELF_INTRO_MAX = 3000   # 화면(ResumeFormPage)의 자기소개서 최대 길이와 같게
_SELF_INTRO_LABEL = re.compile(r"^자기소개서\s*:\s*", re.MULTILINE)
_GENERIC_KEYWORDS = {"경험", "자기소개서", "지원", "지원 동기", "회사", "직무", "노력", "역량", "성장", "목표", "꿈", "저", "열정"}

# 같은 경험을 다른 각도로 — 역할 · 어려움 · 선택 이유 · 결과 근거 · 배운 점(직무 연결). 조사가 필요 없게 '…'에 대해 / '…' 경험 형태로 씀.
# 모두 is_valid_question을 통과해야 한다 (따옴표로 시작하면 거부되어 캐시에서 걸러짐)
_KEYWORD_TEMPLATES = [
    "자기소개서에서 '{kw}'에 대해 쓰셨는데, 그때 본인이 맡은 역할과 직접 한 행동을 구체적으로 말씀해 주세요.",
    "자기소개서에 쓰신 '{kw}' 경험에서 가장 어려웠던 점은 무엇이었고, 어떻게 해결하셨는지 말씀해 주세요.",
    "자기소개서의 '{kw}' 경험에서 그 방법을 선택한 이유는 무엇이었고, 함께 고려했던 다른 방법이 있었다면 말씀해 주세요.",
    "자기소개서에 쓰신 '{kw}' 경험의 결과를 어떻게 확인하셨는지 수치나 근거를 들어 말씀해 주세요.",
    "자기소개서의 '{kw}' 경험에서 배운 점을 {job} 업무에서 어떻게 활용하실 수 있을지 말씀해 주세요.",
]


def split_self_intro(resume_text: str) -> tuple:
    """화면이 보낸 지원 정보에서 '자기소개서: …'(맨 끝, 여러 줄)를 떼어 (직무 정보, 자기소개서)로 나눈다."""
    m = _SELF_INTRO_LABEL.search(resume_text or "")
    if not m:
        return (resume_text or "").strip(), ""
    return resume_text[:m.start()].strip(), resume_text[m.end():].strip()[:SELF_INTRO_MAX]


def _keyword_messages(intro: str) -> list:
    return [
        {"role": "system", "content": "당신은 채용 면접관입니다. 자기소개서에서 면접에서 파고들 핵심 경험을 뽑습니다."},
        {"role": "user", "content": (
            "아래 자기소개서에서 지원자가 직접 한 구체적인 경험을 정확히 5개 뽑으세요.\n"
            "지원 동기 · 포부 · 성격 설명은 빼고, 실제로 한 일(프로젝트 · 실습 · 활동 · 문제 해결 · 성과)만 고르세요.\n"
            "각 항목은 keyword(그 경험을 가리키는, 자기소개서에 실제로 쓰인 짧은 구절 그대로, 2~12자)와 summary(무슨 일을 했는지 한 문장)로 쓰고,\n"
            "순수 JSON 배열로만 출력하세요: [{\"keyword\": \"...\", \"summary\": \"...\"}]\n\n"
            f"자기소개서:\n{intro}"
        )},
    ]


_ASPIRATION = re.compile(r"싶습니다|싶어|지원했|지원하게|지원합니다|기여하|되겠습니다|입사|공감해|공감하여")
# 본인 경험이 아니라 지켜본 세상 이야기 — 키워드 바로 뒤가 '~가 커지면서', '~하는 것을 보고' 같으면 버린다
# (10/6 실제 연습면접: 지원 동기 "AI 서비스가 커지면서 … 보고" → "'AI 서비스' 경험의 결과를 어떻게 확인하셨는지")
_OBSERVED = re.compile(r"^.{0,4}?(커지|늘어나|늘면서|확대되|확산되|발전하|주목받|중요해지|떠오르)"
                       r"|^[^.?!\n]{0,30}?(것을|걸|모습을|뉴스를|기사를)\s*(보고|보며|보면서|접하)")


def _observed(text: str, kw: str) -> bool:
    i = text.find(kw)
    return i >= 0 and bool(_OBSERVED.search(text[i + len(kw):i + len(kw) + 40]))


def _token_in(token: str, text: str) -> bool:
    """단어가 원문에 있는지 — 두 글자 이상이면 앞 두 글자로도 인정 ('도입' ↔ '도입해', '올리기' ↔ '올리고')."""
    return token in text or (len(token) > 2 and token[:2] in text)


def _grounded(kw: str, intro: str) -> bool:
    """키워드가 자기소개서에 근거가 있는지. 모델은 '짧은 구절'을 원문에서 살짝 바꿔 쓰는 일이 많아('Redis 캐시 도입')
    글자 그대로 대신 단어 단위로 본다: 한 단어면 원문에 그대로 있어야 하고(지어낸 단어 방지),
    여러 단어면 첫 단어가 있고 단어의 60% 이상이 원문에 있어야 한다."""
    tokens = kw.split()
    if len(tokens) == 1:
        return kw in intro
    hits = [_token_in(t, intro) for t in tokens]
    return hits[0] and sum(hits) / len(hits) >= 0.6


def _context_of(text: str, kw: str, max_sentence: int = 160, after: int = 60) -> str:
    """포부 문장인지 볼 범위 — 키워드가 든 문장이 짧으면(자기소개서처럼 마침표가 있는 글) 그 문장 전체,
    길면 키워드 자리부터 뒤로 after자. (마침표가 없는 음성 인식 답변은 전체가 한 문장이라, 문장 단위로 보면
    끝의 '되고 싶습니다' 하나로 모든 키워드가 걸렸다)"""
    first = kw.split()[0] if kw.split() else kw
    i = text.find(kw)
    if i < 0:
        i = text.find(first)
    if i < 0 and len(first) > 2:
        i = text.find(first[:2])
    if i < 0:
        return ""
    if not re.search(r"[.!?\n]", text):            # 마침표가 없는 글(음성 인식 답변) → 키워드 뒤 범위만
        return text[i:i + len(kw) + after]
    starts = [m.end() for m in re.finditer(r"[.!?]\s+|\n+", text[:i])]
    start = starts[-1] if starts else 0
    m = re.search(r"[.!?](\s|$)|\n", text[i:])
    end = i + m.end() if m else len(text)
    return text[start:end] if end - start <= max_sentence else text[i:i + len(kw) + after]


def _parse_keywords(text: str, intro: str, limit: int = 5) -> list:
    """모델 출력에서 키워드만 꺼낸다 — 객체를 하나씩 읽어 배열이 잘려도 앞 항목은 살리고,
    자기소개서에 실제로 없는 단어 · 너무 일반적인 단어 · 겹치는 단어는 버린다."""
    out = []
    for m in re.finditer(r"\{[^{}]*\}", text or ""):
        try:
            item = json.loads(m.group(), strict=False)
        except Exception:
            continue
        kw = str(item.get("keyword", "")).strip().strip("'\"") if isinstance(item, dict) else ""
        if (2 <= len(kw) <= 20 and "\n" not in kw and "'" not in kw and _grounded(kw, intro)
                and not (" " not in kw and len(kw) <= 2 and not kw.isascii())   # '병실' · '실습' 같은 두 글자 한 단어는 너무 일반적
                and _is_clean_korean(kw, min_hangul_ratio=0.0, strict=True)   # 외국 문자 · 소문자 영어 → 질문 검사에서 걸림
                and kw not in _GENERIC_KEYWORDS and not any(kw in k or k in kw for k in out)
                and not _ASPIRATION.search(_context_of(intro, kw))   # 포부 · 지원 동기 문장의 단어는 경험이 아님
                and not _observed(intro, kw)):                       # 지켜본 일('…가 커지면서')도 경험이 아님
            out.append(kw)
        if len(out) >= limit:
            break
    return out


async def extract_self_intro_keywords(intro: str) -> list:
    """자기소개서에서 면접에서 파고들 경험 키워드 최대 5개 (탐욕적 생성 — 같은 글엔 같은 결과). 실패 시 빈 리스트."""
    if len(intro) < 50 or llama_service.model is None:
        return []
    try:
        text = (await llama_service.generate_batch([_keyword_messages(intro)], 400, None, greedy=True))[0]
    except Exception as e:
        logger.error(f"자기소개서 키워드 추출 실패: {e}")
        return []
    keywords = _parse_keywords(text, intro)
    logger.info(f"자기소개서 키워드 {len(keywords)}개: {keywords}")
    return keywords


def keyword_questions(keywords: list, resume_text: str, count: Optional[int] = None) -> list:
    """키워드 질문 count개 — 질문 i는 키워드 i % n에 틀 i % 5를 붙인다. 키워드가 적으면 같은 키워드를 다른 각도로
    한 번 더 묻는다(키워드당 최대 2번). 예: 키워드 2개 → 역할 · 어려움(첫 면접), 선택 이유 · 결과 근거(다음 면접)."""
    if not keywords:
        return []
    count = min(count if count is not None else len(keywords), 2 * len(keywords))
    m = re.search(r"^지원 직무\s*:\s*(.+)$", resume_text or "", re.MULTILINE)
    job = re.sub(r"\s*직무$", "", m.group(1).strip()[:30]) if m else ""
    return [_KEYWORD_TEMPLATES[i % len(_KEYWORD_TEMPLATES)].format(kw=keywords[i % len(keywords)], job=job or "지원하신")
            for i in range(count)]


# 직무 설명(화면의 '직무 수행 업무')에서 떼어 낸 업무 항목용 틀 — 모델이 쓴 직무 질문은 일반적이거나 문법이 어색할 때가 많았다
_DUTY_TEMPLATES = [
    "직무 설명에 있는 '{duty}' 업무와 관련해 해 본 경험이 있다면, 그때 본인이 한 일과 결과를 말씀해 주세요.",
    "입사 후 '{duty}' 업무를 맡는다면 가장 중요하게 챙길 점은 무엇이고, 그 이유는 무엇인지 말씀해 주세요.",
    "입사 후 '{duty}' 업무에서 예상하지 못한 어려움이 생긴다면 어떻게 대처하실지 순서대로 말씀해 주세요.",
]


def duty_questions(info_text: str, limit: int = 2) -> list:
    """직무 설명을 쉼표 · 가운뎃점 · '및' 등으로 나눠 짧은 업무 항목(4~20자)만 질문 틀에 넣는다.
    긴 문장으로 쓴 직무 설명은 항목이 안 나오므로 빈 리스트 → 호출부가 모델 생성으로 채운다."""
    # 여러 줄로 쓴 직무 설명은 다음 항목('인재상:' 등) 전까지 전부 — 예전엔 첫 줄만 읽어서, 첫 줄이 '[지원 직무 이해]' 같은
    # 제목이면 그 제목이 업무 이름으로 들어갔다 (10/6 실제 연습면접: "직무 설명에 있는 '[지원 직무 이해]' 업무와 관련해…")
    m = re.search(r"^직무 설명\s*:\s*(.+?)(?=^\s*(?:인재상|자기소개서)\s*:|\Z)", info_text or "", re.MULTILINE | re.DOTALL)
    if not m:
        return []
    body = re.sub(r"\[[^\]\n]*\]|【[^】\n]*】|<[^>\n]*>", " ", m.group(1))   # [제목] · 【제목】 · <제목> 같은 머리말
    duties = []
    for part in re.split(r"[,，·/;\n]|\s및\s|\s그리고\s", body):
        d = re.sub(r"^\s*(?:[-•*▪◦○●]|\d+[.)])\s*", "", part)   # 줄머리 기호 · 번호
        d = re.sub(r"\s*등$", "", d.strip(" .:")).strip()
        if 4 <= len(d) <= 20 and "'" not in d and _is_clean_korean(d, min_hangul_ratio=0.0, strict=True) and d not in duties:   # "운영" 같은 한 단어는 제외
            duties.append(d)
    return [_DUTY_TEMPLATES[i % len(_DUTY_TEMPLATES)].format(duty=d) for i, d in enumerate(duties[:limit])]


_AWKWARD_QUESTION = re.compile(r"^당신|습니다\s*\?$|는가\s*\?$")   # 모델이 쓴 질문 중 어색한 것 ('당신이 …', '…했습니다?', '…하는가?')


def _interleave(kw_qs: list, job_qs: list, count: int) -> list:
    """키워드 질문 2개 · 직무 질문 1개 순서로 섞는다 — 호출부가 면접마다 3개씩 차례로 꺼내 쓰므로
    면접 한 번에 자기소개서 질문 2개 + 직무 질문 1개가 되도록. 한쪽이 모자라면 다른 쪽으로 채운다."""
    kw, job, out = list(kw_qs), list(job_qs), []
    while len(out) < count and (kw or job):
        for src in (kw, kw, job):
            if src and len(out) < count:
                out.append(src.pop(0))
        if not kw and job:
            out += job[:count - len(out)]; job.clear()
        if not job and kw:
            out += kw[:count - len(out)]; kw.clear()
    return out


async def generate_questions_from_resume(resume_text: str, category: str, num_questions: int = 5) -> list:
    """지원 정보로 면접 질문 생성 — 고정 질문(자기소개·지원동기) 2개는 빼고 AI 질문 num_questions-2개를 반환.

    자기소개서 질문: 키워드 추출 → 질문 틀 (자기소개서가 있을 때)
    직무 질문: 직무 설명의 업무 항목 → 질문 틀, 항목이 모자라면 모델이 직접 쓴 질문
    둘을 섞어 면접마다 자기소개서 질문 2개 + 직무 질문 1개가 되게 한다.
    모자라면 있는 만큼만 반환하고 호출부(routers/interview.py)가 직무 기본 질문(question_bank)으로 채운다.
    """
    ai_num = max(0, num_questions - 2)
    if ai_num == 0 or (llama_service.model is None and llama_service.text_model is None):
        return []
    # 질문 어댑터가 있으면 자기소개서를 읽고 직접 쓴 질문을 먼저 — 검사에서 빠진 만큼만 아래 질문 틀 방식으로 채운다
    model_pool = await model_question_pool(resume_text) if llama_service.has_qgen_adapter else []
    # 하나쯤 빠진 건 그대로 쓴다 — 틀 하나를 채우려고 키워드 추출을 또 돌리면 면접 준비가 10초 가까이 늘었다 (면접마다 3개씩 꺼내 써서 5개도 충분)
    if len(model_pool) >= max(ai_num - 1, 1):
        return model_pool[:ai_num]
    info_text, intro = split_self_intro(resume_text)
    keywords = await extract_self_intro_keywords(intro) if intro else []
    # 면접마다 자기소개서 질문 2 : 직무 질문 1 → 질문 풀 6개 중 자기소개서 질문 4개
    kw_qs = keyword_questions(keywords, info_text, count=max(len(keywords), ai_num - ai_num // 3))
    need_job = max(ai_num - len(kw_qs), ai_num // 3 or 1)
    job_qs = duty_questions(info_text, limit=need_job)
    if len(job_qs) < need_job:
        job_qs += await _generate_job_questions(info_text, need_job - len(job_qs))
    template_pool = _interleave(kw_qs, job_qs, ai_num)
    return (model_pool + [q for q in template_pool if not any(_similar_question(q, m) for m in model_pool)])[:ai_num]


# ── 질문 전용 어댑터 입력 형식 ───────────────────────────────────────────────────
# 학습 데이터(training/build_qgen_dataset.py)와 서비스가 같은 형식을 쓴다 — 바꾸면 다시 학습해야 한다.
# 작성 기준: training/question_guide.md
QGEN_POOL_SIZE = 6   # 질문 풀 6개: 자기소개서 2 · 직무 1 · 자기소개서 2 · 직무 1 (면접마다 3개씩 꺼내 씀)
_QGEN_SYSTEM = "당신은 채용 면접관입니다. 지원자의 지원 정보와 자기소개서를 읽고, 자기소개서에 쓴 경험을 구체적으로 파고드는 면접 질문을 만듭니다."
_FU_SYSTEM = "당신은 채용 면접관입니다. 지원자의 답변을 듣고 바로 이어서 물을 꼬리 질문을 하나 만듭니다."


def qgen_messages(resume_text: str) -> list:
    """지원 정보(화면이 보내는 '지원 회사: …\\n…\\n자기소개서: …' 그대로) → 질문 6개 JSON 배열."""
    return [
        {"role": "system", "content": _QGEN_SYSTEM},
        {"role": "user", "content": (
            f"아래 지원 정보로 면접 질문 {QGEN_POOL_SIZE}개를 만드세요.\n"
            "순서: 자기소개서 질문, 자기소개서 질문, 직무 질문, 자기소개서 질문, 자기소개서 질문, 직무 질문 "
            "(자기소개서가 없으면 모두 직무 질문). 순수 JSON 배열로만 출력하세요.\n\n"
            f"{(resume_text or '').strip()[:SELF_INTRO_MAX + 600]}"
        )},
    ]


# 꼬리 질문 유형 (10/7 팀 블라인드 평가 때 정한 기준) — 답변을 보고 유형을 고른 뒤, 그 유형으로 묻는다
FU_TYPES = {
    "role": ("경험 진위 및 역할 검증형",
             "지원자가 말한 성과나 경험에서 본인이 구체적으로 맡은 역할과 실제 기여도를 확인합니다."),
    "why": ("판단 근거 및 원인 분석형",
            "그 방법을 선택한 이유나 문제의 원인을 어떻게 판단했는지 물어 논리적 사고력을 확인합니다."),
    "whatif": ("가정 및 바뀐 조건 대응형",
               "당시 전제나 조건을 바꿔, 상황이 달랐다면 어떻게 대처할지 물어 실무 적응력과 유연성을 확인합니다."),
    "strength": ("강점 및 약점 심화 탐색형",
                 "답변에서 말한 강점이 실제 직무에서 어떻게 쓰이는지, 약점이 업무에 지장을 주지 않는지 파고듭니다."),
}
_STRENGTH_TOPIC = re.compile(r"장점|단점|강점|약점|성격|성향|보완|부족한 점|편인가요|편이신가요|스타일|본인을 .{0,6}(단어|표현)|스스로를 어떤")
_STRENGTH_CLAIM = re.compile(r"제\s?(강점|장점|약점|단점)|저의\s?(강점|장점|약점|단점)|제 성격")
_HYPOTHETICAL = re.compile(r"만약|한다면|된다면|라면|다고 하면|상황에서|하시겠|대처|어떻게 하실")
_IF_ANY = re.compile(r"만약에?\s*(그런\s*)?(경험이\s*)?있\S*")   # '만약 있다면 말씀해 주세요'는 가정 질문이 아니다
_ASKS_REASON = re.compile(r"이유|왜")   # 질문이 이미 이유를 물었으면 '판단 근거'를 또 묻지 않는다
# 답변이 이미 이유를 말했어도 판단 근거형은 뒤로 — 10/10 팀 검토: 판단 근거형 16개 중 좋은 질문 5개, X의 대부분이 "이미 답변에 있음"
_GAVE_REASON = re.compile(r"왜냐하면|때문에|때문입니다|이유는|이유가|그래서")
# 가정사 · 사별처럼 민감한 이야기에는 꼬리 질문을 하지 않는다 (10/10 팀 검토 "가정사 관련 답변은 꼬리질문은 안하는게 좋음")
_SENSITIVE_TOPIC = re.compile(r"시어머니|시아버지|시댁|고부|이혼|사별|돌아가셨|돌아가신|세상을 떠|학대|투병|장례|유산했")
_PAST_EXPERIENCE = re.compile(r"했었|했던|당시|그때|였을 때|적이 있|경험이|했습니다|었습니다")
_DECISION = re.compile(r"방법|해결|선택|결정|판단|원인|바꿨|바꾸|개선|고민")
# 이미 나온 꼬리 질문이 어떤 유형이었는지 (면접 하나에 꼬리 질문이 둘이면 서로 다른 유형으로)
# (가정 → 강점 → 역할 → 근거 순으로 본다: '만약 … 이유는'은 가정 질문)
_FU_TYPE_MARKERS = {
    "whatif": re.compile(r"만약|달랐다면|바뀐다면|없었다면|줄었다면|늘었다면"),
    "strength": re.compile(r"강점|약점|장점|단점|보완"),
    "role": re.compile(r"역할|직접|주도|기여|맡아|맡으|맡았"),
    "why": re.compile(r"이유|근거|원인|판단하"),
}


def follow_up_type_of(text: str) -> Optional[str]:
    return next((t for t, rx in _FU_TYPE_MARKERS.items() if rx.search(text or "")), None)


def follow_up_types(question: str, answer: str, used: frozenset = frozenset()) -> list:
    """이 답변에 어울리는 꼬리 질문 유형 순서 — 앞 꼬리 질문이 쓴 유형은 맨 뒤로.
      강점·약점·성향 질문 → 강점 / 가정 질문(만약 · 상황) → 바뀐 조건 /
      지난 경험에서 방법을 고르거나 문제를 푼 이야기 → 판단 근거 / 그 밖(주장 · 의견 · 경험) → 역할
      (의견만 말한 답변엔 '실제로 해 본 경험과 본인 역할'을 물어 말의 진위를 확인)."""
    question, answer = question or "", answer or ""
    asks_reason = bool(_ASKS_REASON.search(question) or _GAVE_REASON.search(answer))
    order = []
    if _STRENGTH_TOPIC.search(question) or _STRENGTH_CLAIM.search(answer):
        order.append("strength")
    if _HYPOTHETICAL.search(_IF_ANY.sub("", question)):
        order.append("whatif")
    if _PAST_EXPERIENCE.search(answer) and _DECISION.search(answer) and not asks_reason:
        order.append("why")
    order += ["role", "whatif", "why"] if asks_reason else ["role", "why", "whatif"]
    order = list(dict.fromkeys(order))
    return [t for t in order if t not in used] + [t for t in order if t in used]


def followup_messages(question: str, answer: str, fu_type: str = "role") -> list:
    """방금 한 질문 · 답변 + 꼬리 질문 유형 → 꼬리 질문 한 문장."""
    name, desc = FU_TYPES[fu_type]
    return [
        {"role": "system", "content": _FU_SYSTEM},
        {"role": "user", "content": (
            f"면접 질문: {question}\n지원자 답변: {(answer or '').strip()[:1500]}\n\n"
            f"꼬리 질문 유형: {name} — {desc}\n"
            "답변에 나온 내용을 짚어, 이 유형의 꼬리 질문 한 문장만 출력하세요."
        )},
    ]


# 질문 틀 · 흔한 면접 표현 — 자기소개서와 겹쳐도 '근거'로 치지 않는다 (training/eval_qgen.py와 같은 기준)
_GENERIC_PHRASES = re.sub(r"\s+", "", "자기소개서 경험 말씀해 주세요 무엇이었나요 어떻게 하셨나요 구체적으로 본인이 직접 결과를 확인 "
                          "가장 어려웠던 이유는 무엇 그 방법을 선택한 다른 방법 배운 점 업무 입사 후 지원 회사 직무 설명 있다면 "
                          "하셨는데 하셨다고 했는데 생각하시나요 보시나요 하시겠어요 판단하셨나요")


def _squash_text(text: str) -> str:
    return re.sub(r"[\s'\"‘’“”.,?!·]", "", text or "")


def question_grounded(question: str, source: str, n: int = 4) -> bool:
    """질문에 원문(자기소개서 · 답변)의 고유한 말이 들어 있는지 — 띄어쓰기를 빼고 n글자 이상 겹치는 부분(흔한 표현 제외)."""
    q, t = _squash_text(question), _squash_text(source)
    return any(q[i:i + n] in t and q[i:i + n] not in _GENERIC_PHRASES for i in range(len(q) - n + 1))


def _similar_question(a: str, b: str, threshold: float = 0.8) -> bool:
    sa, sb = set(_squash_text(a)), set(_squash_text(b))
    return len(sa & sb) / max(1, len(sa | sb)) > threshold


# 고정 질문(자기소개 · 지원동기)과 겹치는 질문 — 10/7 시험: "HBM … 메모리 설계에 대한 관심이 생겼던 계기가 됐나요?"가
# 바로 앞의 "지원하게 된 동기가 무엇인가요?"와 같은 것을 물었다
_FIXED_OVERLAP = re.compile(r"지원\s?동기|지원하게 된|지원한 이유|관심을\s?(갖|가지)게 된|관심이 생|자기소개를")


def question_pool_tag() -> str:
    """질문 캐시에 붙이는 방식 표시 — 질문 어댑터를 켜고 끄거나 바꾸면 예전 방식으로 만든 캐시를 쓰지 않는다."""
    if llama_service.has_qgen_adapter:
        return os.path.basename(os.path.normpath(settings.LLAMA_QGEN_ADAPTER_PATH))
    return "template"


async def model_question_pool(resume_text: str) -> list:
    """질문 어댑터가 자기소개서를 읽고 직접 쓴 질문 풀 — 검사를 통과한 것만 순서대로.
    (자기소개서 자리 0 · 1 · 3 · 4번은 자기소개서 근거가 있어야 하고, 자기소개서가 없으면 '자기소개서'를 언급한 질문은 버린다)"""
    _, intro = split_self_intro(resume_text)
    try:
        text = (await llama_service.generate_batch([qgen_messages(resume_text)], 450, QGEN_ADAPTER, greedy=True))[0]
    except Exception as e:
        logger.error(f"질문 어댑터 생성 실패: {e}")
        return []
    out, dropped = [], 0
    for i, q in enumerate(q.strip() for q in _extract_questions(text)[:QGEN_POOL_SIZE]):
        ok = (is_valid_question(q) and not _AWKWARD_QUESTION.search(q) and not _FIXED_OVERLAP.search(q)
              and (question_grounded(q, intro) if intro and i in (0, 1, 3, 4) else not (not intro and "자기소개서" in q))
              and not any(_similar_question(q, o) for o in out))
        if ok:
            out.append(q)
        else:
            dropped += 1
    logger.info(f"질문 어댑터: 풀 {len(out)}개 사용, {dropped}개 검사 탈락")
    return out


def same_experience(follow_up: str, answer: str, other: str, n: int = 5) -> bool:
    """꼬리 질문이 답변에서 가져온 말(띄어쓰기 빼고 n글자, 흔한 표현 제외)이 다른 질문에도 있으면 같은 경험을 묻는 것으로 본다.
    (10/7 시험: 자기소개 꼬리 질문 "RISC-V 파이프라인 … 어떤 기준으로 경로를 나누셨는지"가 뒤 질문 Q3과 같은 경험 · 같은 각도.
    평가 데이터의 서로 다른 지원자 질문 10,800쌍에선 1쌍만 걸렸다)"""
    q, a, o = _squash_text(follow_up), _squash_text(answer), _squash_text(other)
    return any(q[i:i + n] in a and q[i:i + n] in o and q[i:i + n] not in _GENERIC_PHRASES for i in range(len(q) - n + 1))


async def model_follow_up(question: str, answer: str, existing_questions: list, fu_type: str) -> Optional[str]:
    """질문 어댑터가 정한 유형으로 직접 쓴 꼬리 질문. 검사에 떨어지거나, 다른 유형으로 썼거나,
    이 면접의 다른 질문과 거의 같거나 같은 경험을 물으면 None."""
    try:
        text = (await llama_service.generate_batch([followup_messages(question, answer, fu_type)], 120, QGEN_ADAPTER, greedy=True))[0]
    except Exception as e:
        logger.error(f"질문 어댑터 꼬리 질문 실패: {e}")
        return None
    q = (text.strip().splitlines() or [""])[0].strip().strip('"')
    others = [o for o in existing_questions if o and o != question]
    reason = ("검사" if not is_valid_question(q) or len(q) > 130 or _AWKWARD_QUESTION.search(q) else
              "유형" if follow_up_type_of(q) != fu_type else
              "겹침" if any(_similar_question(q, o) or same_experience(q, answer, o) for o in others) else None)
    if reason:
        logger.info(f"질문 어댑터 꼬리 질문 탈락 ({fu_type}, {reason}): {q[:60]!r}")
        return None
    return q


# ── 실시간 꼬리 질문 ──────────────────────────────────────────────────────────
# 답변을 듣고 바로 이어 묻는 질문. 유형(FU_TYPES — 역할 검증 · 판단 근거 · 바뀐 조건 · 강점과 약점)은 답변을 보고 규칙으로 고르고
# (follow_up_types), 질문 어댑터가 있으면 그 유형으로 직접 쓴다. 없거나 검사에 떨어지면 모델이 답변에서 뽑은 키워드를 유형별 틀에 넣는다.
FOLLOW_UP_MAX_PER_INTERVIEW = 2    # 면접 하나에 꼬리 질문 최대 개수 (기본 5개 → 최대 7개)
FOLLOW_UP_MIN_ANSWER = 40          # 이보다 짧은 답변은 파고들 내용이 없어 묻지 않는다

_FU_TEMPLATES = {
    "role": "방금 말씀하신 '{kw}'에서 본인이 직접 맡은 역할은 무엇이었고, 어디까지 주도하셨는지 말씀해 주세요.",
    "why": "방금 말씀하신 '{kw}'에서 그렇게 하기로 판단하신 근거는 무엇이었나요?",
    "whatif": "방금 말씀하신 '{kw}' 부분에서 만약 조건이 달라져 그대로 할 수 없게 된다면 어떻게 대처하시겠어요?",
    "strength": "방금 말씀하신 '{kw}' 부분이 실제 업무에서는 어떻게 드러날지, 강점이라면 어떻게 살리고 약점이라면 어떻게 보완하실지 말씀해 주세요.",
}


def _answer_keyword_messages(question: str, answer: str) -> list:
    return [
        {"role": "system", "content": "당신은 채용 면접관입니다. 지원자의 답변에서 꼬리 질문으로 더 파고들 부분을 고릅니다."},
        {"role": "user", "content": (
            f"면접 질문: {question}\n지원자 답변: {answer}\n\n"
            "이 답변에서 면접관이 더 자세히 물어볼 만한 구체적인 경험 · 행동 · 성과를 3개 뽑으세요.\n"
            "각 항목은 keyword(답변에 실제로 쓰인 짧은 구절 그대로, 2~12자)와 summary(한 문장)로 쓰고,\n"
            "순수 JSON 배열로만 출력하세요: [{\"keyword\": \"...\", \"summary\": \"...\"}]"
        )},
    ]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def _asked_keywords(questions: list) -> list:
    """질문 틀의 따옴표 안 키워드 ('…'), 띄어쓰기 없이 — '디지털 시스템 설계'와 '디지털시스템설계 수업'을 같은 경험으로 보려고."""
    return [k for k in (_squash(m) for q in questions for m in re.findall(r"'([^']+)'", q or "")) if len(k) >= 2]


# 지원 동기 답변은 경험보다 관심을 갖게 된 계기라, 경험 각도('결과를 어떻게 확인')로 물으면 어색했다
# (10/6 시험: "'메모리 접근' 경험의 결과를 어떻게 확인하셨는지") → 그 관심을 위해 실제로 해 본 일을 묻는다 (역할 검증형)
_FU_MOTIVE = "방금 '{kw}' 이야기를 하셨는데, 그 뒤로 이 분야를 위해 직접 공부하거나 준비한 것이 있다면 말씀해 주세요."   # 주제('메모리 접근') · 사건('서버 느려짐') 모두 어울리게
_MOTIVE_QUESTION = re.compile(r"지원하게 된 동기|지원 동기|지원한 이유")


def follow_up_question(keyword: str, avoid: set, types: list, motive: bool = False) -> Optional[str]:
    """유형 순서대로 틀에 키워드를 넣어 처음 쓸 수 있는 질문. 지원 동기 답변이면 동기 질문 하나만."""
    templates = [_FU_MOTIVE] if motive else [_FU_TEMPLATES[t] for t in types]
    for t in templates:
        q = t.format(kw=keyword)
        if q not in avoid and is_valid_question(q):
            return q
    return None


async def generate_follow_up(question: str, answer: str, existing_questions: list,
                             previous_follow_ups: list = ()) -> Optional[str]:
    """방금 답변으로 꼬리 질문 하나. 파고들 키워드가 없거나 실패하면 None (면접은 원래 순서대로 이어진다).

    유형은 답변을 보고 고르되, 이 면접의 앞 꼬리 질문이 쓴 유형은 피한다 (꼬리 질문이 둘이면 서로 다른 유형).
    틀 방식에선 면접의 다른 질문(뒤에 나올 자기소개서 질문 포함)이 이미 다루는 키워드도 쓰지 않는다
    — 10/6 실제 연습면접: 꼬리 질문 "'디지털 시스템 설계' 경험에서 가장 어려웠던 순간"과 뒤 질문
    "'타이밍 리포트' 경험에서 가장 어려웠던 점"이 같은 경험 · 같은 각도라 같은 답을 두 번 했다."""
    answer = (answer or "").strip()
    if len(answer) < FOLLOW_UP_MIN_ANSWER or llama_service.model is None:
        return None
    if _SENSITIVE_TOPIC.search(answer) or _SENSITIVE_TOPIC.search(question or ""):
        logger.info("꼬리 질문 없음 (민감한 주제)")
        return None
    used = frozenset(t for t in (follow_up_type_of(q) for q in previous_follow_ups) if t)
    types = follow_up_types(question, answer, used)
    # 질문 어댑터가 있으면 유형대로 직접 쓴 꼬리 질문을 먼저, 두 번 다 탈락하면 아래 키워드 + 질문 틀 방식
    if llama_service.has_qgen_adapter:
        for t in types[:2]:   # 탈락하면 다음 유형으로 한 번 더 (한 번에 약 2초)
            q = await model_follow_up(question, answer, existing_questions, t)
            if q:
                logger.info(f"꼬리 질문 유형 {t} (어댑터)")
                return q
    try:
        text = (await llama_service.generate_batch([_answer_keyword_messages(question, answer[:SELF_INTRO_MAX])], 250, None, greedy=True))[0]
    except Exception as e:
        logger.error(f"꼬리 질문 키워드 추출 실패: {e}")
        return None
    keywords = _parse_keywords(text, answer, limit=3)
    asked = _asked_keywords(existing_questions)
    fresh = [k for k in keywords if not any(_squash(k) in a or a in _squash(k) for a in asked)]
    avoid = set(existing_questions)
    motive = bool(_MOTIVE_QUESTION.search(question or ""))
    for kw in fresh:
        q = follow_up_question(kw, avoid, types, motive)
        if q:
            logger.info(f"꼬리 질문 키워드 {keywords} → '{kw}', 유형 {follow_up_type_of(q)}")
            return q
    logger.info(f"꼬리 질문 없음 (키워드 {keywords})")
    return None
