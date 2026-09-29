"""
로컬 선생님 모델(Qwen2.5-14B-Instruct)로 점수 라벨이 달린 학습 데이터를 만든다 — Gemini 미사용.

1) 직무 x 질문마다, 품질이 다른 답변 5개를 생성 (샘플링으로 라운드마다 다른 답변)
2) 각 답변을 "의도한 품질을 모르는" 별도 프롬프트로 채점 → 이 점수가 3B Llama의 학습 라벨이 됨

meta.target_level(0=매우 부실 ~ 4=매우 우수)을 함께 저장해, 선생님의 채점이 의도한 품질 순서를
따르는지 검증할 수 있게 한다. 중단 후 재실행하면 이미 만든 (라운드, 직무, 질문)은 건너뛴다.

실행 (WSL, llama-finetune venv):
    python generate_teacher_scores.py --rounds 2
"""
import argparse
import json
import re
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

TEACHER = "Qwen/Qwen2.5-14B-Instruct"
OUT_PATH = Path(__file__).resolve().parent / "data" / "score_teacher_qwen.jsonl"

ROLES = ["백엔드 개발자", "프론트엔드 개발자", "데이터 분석가", "마케팅", "영업", "인사(HR)", "UX/UI 디자이너", "서비스 기획자"]
QUESTIONS = [
    "간단한 자기소개 부탁드립니다.",
    "해당 직무에 지원하게 된 동기가 무엇인가요?",
    "가장 어려웠던 문제를 해결한 경험을 말해주세요.",
    "팀원과 갈등이 있었을 때 어떻게 해결했나요?",
    "본인의 가장 큰 강점과 약점은 무엇인가요?",
    "실패했던 경험과 그로부터 배운 점을 말해주세요.",
    "입사 후 5년 뒤 어떤 모습이 되고 싶나요?",
    "이 직무에서 가장 중요한 역량은 무엇이라고 생각하나요?",
]
QUALITY_LEVELS = [
    "매우 부실 (1문장): 성의 없거나 질문과 거의 무관",
    "부족 (2~3문장): 추상적이고 근거·경험 없이 일반론만 나열",
    "보통 (3~4문장): 질문에 맞는 내용이지만 구체적인 사례나 수치가 부족",
    "좋음 (4~6문장): 구체적인 경험이 있고 구조가 있으나 직무 연계나 결과가 약간 아쉬움",
    "매우 우수 (5~7문장): STAR 구조, 구체적 수치·결과, 직무와의 연결까지 완벽",
]

# 백엔드 llama_service가 추론 시 보내는 시스템 프롬프트와 글자 하나까지 같아야 한다.
SCORING_SYSTEM_PROMPT = (
    "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
    "지원자의 면접 질문과 답변을 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지).\n"
    "feedback의 각 항목은 1~2문장으로 간결하게 작성하세요.\n"
    '{"score":0~100,"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안",'
    '"tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}'
)

# 채점 기준을 명시해 선생님의 점수가 0~100 전 구간을 쓰도록 유도 (학습 데이터에는 넣지 않음 —
# 학생은 위 시스템 프롬프트만 보고 이 기준을 체화하도록 학습된다).
SCORING_RUBRIC = (
    "채점 기준: 0~20 무성의·무관, 21~40 추상적 일반론, 41~60 관련은 있으나 구체성 부족, "
    "61~80 구체적 경험과 구조가 있음, 81~100 STAR 구조·수치 결과·직무 연결까지 탁월. "
    "답변의 실제 내용만 보고 엄격하게 채점하세요."
)


def parse_json(text: str):
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        text = m.group(1).strip() if m else re.sub(r"```(?:json)?", "", text).strip()
    for s, e in [("[", "]"), ("{", "}")]:
        si, ei = text.find(s), text.rfind(e)
        if si != -1 and ei > si:
            try:
                return json.loads(text[si:ei + 1])
            except json.JSONDecodeError:
                continue
    return json.loads(text)


def load_teacher():
    tokenizer = AutoTokenizer.from_pretrained(TEACHER, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(
        TEACHER,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        ),
        device_map={"": 0},
    )
    model.eval()
    return model, tokenizer


def generate_batch(model, tokenizer, conversations, max_new_tokens, temperature):
    prompts = [tokenizer.apply_chat_template(c, tokenize=False, add_generation_prompt=True) for c in conversations]
    enc = tokenizer(prompts, return_tensors="pt", padding=True).to(model.device)
    with torch.no_grad():
        out = model.generate(
            **enc, max_new_tokens=max_new_tokens,
            do_sample=temperature > 0, temperature=temperature if temperature > 0 else None,
            top_p=0.95 if temperature > 0 else None,
            pad_token_id=tokenizer.pad_token_id,
        )
    return [tokenizer.decode(o[enc["input_ids"].shape[-1]:], skip_special_tokens=True) for o in out]


def answer_gen_conversation(role, question):
    levels = "\n".join(f"{i + 1}. {lvl}" for i, lvl in enumerate(QUALITY_LEVELS))
    return [{"role": "user", "content": (
        f"'{role}' 직무에 지원한 서로 다른 지원자 5명이 면접에서 아래 질문에 답한 내용을 만들어주세요.\n"
        f"질문: {question}\n\n"
        f"각 답변의 품질은 아래 순서를 정확히 따르세요:\n{levels}\n\n"
        "실제 면접 발화처럼 자연스러운 한국어 구어체로 작성하세요. 이름·회사명은 가상의 것을 쓰세요.\n"
        "각 답변은 줄바꿈 없이 한 줄로 쓰고, 아래 형식으로만 응답하세요 (다른 설명 금지):\n"
        "[1] 첫 번째 답변\n[2] 두 번째 답변\n[3] 세 번째 답변\n[4] 네 번째 답변\n[5] 다섯 번째 답변"
    )}]


def parse_answers(text: str) -> list:
    """'[n] 답변' 줄 형식 파싱 — JSON 배열보다 따옴표·줄바꿈에 덜 민감하다."""
    found = {}
    for m in re.finditer(r"^\s*\[(\d)\]\s*(.+?)\s*$", text, re.MULTILINE):
        found.setdefault(int(m.group(1)), m.group(2))
    return [found[i] for i in range(1, 6)] if all(i in found for i in range(1, 6)) else []


def scoring_conversation(question, answer):
    return [
        {"role": "system", "content": SCORING_SYSTEM_PROMPT + "\n" + SCORING_RUBRIC},
        {"role": "user", "content": f"면접 질문: {question}\n지원자 답변: {answer}"},
    ]


def load_done():
    done = set()
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                m = json.loads(line)["meta"]
                done.add((m["round"], m["role"], m["question"]))
    return done


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--gen_batch", type=int, default=8)
    parser.add_argument("--score_batch", type=int, default=10)
    args = parser.parse_args()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    done = load_done()
    cases = [(rd, r, q) for rd in range(args.rounds) for r in ROLES for q in QUESTIONS if (rd, r, q) not in done]
    if args.limit:
        cases = cases[: args.limit]
    print(f"처리할 조합 {len(cases)}개 (이미 완료 {len(done)}개)", flush=True)
    if not cases:
        return

    model, tokenizer = load_teacher()
    print("선생님 모델 로딩 완료", flush=True)

    saved = 0
    for i in range(0, len(cases), args.gen_batch):
        chunk = cases[i:i + args.gen_batch]
        raw = generate_batch(model, tokenizer, [answer_gen_conversation(r, q) for _, r, q in chunk], 1500, 0.8)

        items = []  # (case, target_level, answer)
        for case, text in zip(chunk, raw):
            answers = parse_answers(text)
            if answers and not any("�" in a for a in answers):
                items += [(case, lvl, a) for lvl, a in enumerate(answers)]
            else:
                print(f"[건너뜀] 답변 형식 오류: {case[1]} / {case[2][:12]} — {text[:80]!r}", flush=True)

        rows = []
        for j in range(0, len(items), args.score_batch):
            batch = items[j:j + args.score_batch]
            outs = generate_batch(model, tokenizer, [scoring_conversation(c[2], a) for c, _, a in batch], 500, 0)
            for (case, lvl, answer), text in zip(batch, outs):
                try:
                    r = parse_json(text)
                    score = int(r["score"])
                    if not (0 <= score <= 100 and r.get("feedback") and r.get("tip")):
                        raise ValueError
                    if "�" in r["feedback"] + r["tip"]:  # 깨진 글자가 섞인 출력은 학습에 넣지 않음
                        raise ValueError
                    rows.append((case, lvl, answer, {"score": score, "feedback": r["feedback"], "tip": r["tip"]}))
                except Exception:
                    print(f"[건너뜀] 채점 파싱 실패: {case[1]} / {case[2][:12]} / 레벨 {lvl}", flush=True)

        with open(OUT_PATH, "a", encoding="utf-8") as f:
            for (rd, role, question), lvl, answer, label in rows:
                f.write(json.dumps({
                    "messages": [
                        {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                        {"role": "user", "content": f"면접 질문: {question}\n지원자 답변: {answer}"},
                        {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
                    ],
                    "meta": {"round": rd, "role": role, "question": question, "target_level": lvl},
                }, ensure_ascii=False) + "\n")
        saved += len(rows)
        print(f"진행 {min(i + args.gen_batch, len(cases))}/{len(cases)} 조합, 누적 {saved}개 저장", flush=True)

    print(f"GENERATION_DONE {saved}개 → {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
