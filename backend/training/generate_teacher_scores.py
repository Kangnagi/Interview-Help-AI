"""
로컬 선생님 모델(Qwen2.5-14B-Instruct)로 점수 라벨이 달린 학습 데이터를 만든다 — Gemini 미사용.

1) 직무 x 질문마다, 유형이 다른 답변 7개를 생성 (샘플링으로 라운드마다 다른 답변)
2) 각 답변을 "의도한 유형을 모르는" 별도 프롬프트로 채점 → 이 점수가 3B Llama의 학습 라벨이 됨

v2 (실제 답변 사람 검토 반영):
  - 질문 8개(경험형만) → 공통 8개 + 직무별 4개(기술·가정·설계·상황형)
    : 실제 서비스 질문은 "~을 구축한다면 어떻게 구성하시겠습니까?" 같은 설계형이 많은데,
      v1은 경험형만 배워 설계형 질문에도 STAR·수치를 요구하는 피드백이 나왔다.
  - 답변 유형 5종 → 7종: "경험 없음·모름" 솔직형, "좋은 말·기술 용어 나열형" 추가
    : 사례 없이 경력·용어만 나열한 답변에 65~85점을 주던 문제 (검토에서 '너무 높음')
  - 라운드 0은 글로 쓴 답변, 라운드 1은 음성 인식(STT) 결과 말투 — 품질과 말투가 섞이지 않게 라운드로 분리
  - 채점: 사람 검토에 맞춘 구간 기준(나열형은 50점 이하, 경험 없음은 11~30점 등) + 5의 배수만 쓰지 않기
  - 피드백 규칙: 답변에 있는 내용을 없다고 하지 않기, 설계·지식형엔 과거 수치 요구하지 않기

meta.target_level(0=매우 부실 ~ 4=매우 우수, 5=모름, 6=나열형)을 함께 저장해 검증에 쓴다.
중단 후 재실행하면 이미 만든 (라운드, 직무, 질문)은 건너뛴다.

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
OUT_PATH = Path(__file__).resolve().parent / "data" / "score_teacher_qwen_v2.jsonl"

COMMON_QUESTIONS = [
    "간단한 자기소개 부탁드립니다.",
    "해당 직무에 지원하게 된 동기가 무엇인가요?",
    "가장 어려웠던 문제를 해결한 경험을 말해주세요.",
    "팀원과 갈등이 있었을 때 어떻게 해결했나요?",
    "본인의 가장 큰 강점과 약점은 무엇인가요?",
    "실패했던 경험과 그로부터 배운 점을 말해주세요.",
    "입사 후 5년 뒤 어떤 모습이 되고 싶나요?",
    "이 직무에서 가장 중요한 역량은 무엇이라고 생각하나요?",
]
ROLE_QUESTIONS = {
    "백엔드 개발자": [
        "대용량 트래픽이 몰릴 때 서버 장애를 막기 위해 어떤 설계를 고려하시겠습니까?",
        "데이터베이스 조회 성능이 느려졌을 때 어떤 순서로 원인을 찾고 개선하시겠습니까?",
        "Kafka 같은 메시지 큐를 사용해 본 경험이 있다면, 어떤 상황에서 왜 선택했는지 설명해주세요.",
        "REST API를 설계할 때 중요하게 생각하는 원칙은 무엇인가요?",
    ],
    "프론트엔드 개발자": [
        "웹 페이지 초기 로딩 속도가 느릴 때 어떤 방법으로 개선하시겠습니까?",
        "React에서 상태 관리를 어떻게 설계하는지, 사용해 본 방식과 선택 이유를 말씀해주세요.",
        "다양한 브라우저와 기기에서 동일한 사용자 경험을 보장하기 위해 어떤 노력을 하시나요?",
        "디자이너나 백엔드 개발자와 화면 명세가 어긋났을 때 어떻게 조율하셨나요?",
    ],
    "데이터 분석가": [
        "서비스의 실시간 데이터 분석 파이프라인을 구축한다면 수집부터 활용까지 어떻게 구성하시겠습니까?",
        "A/B 테스트 결과가 통계적으로 유의하지 않게 나왔을 때 어떻게 해석하고 다음 단계를 정하시겠습니까?",
        "결측치나 이상치가 많은 데이터를 받았을 때 어떻게 처리하시나요?",
        "분석 결과를 비전공자인 경영진에게 설명했던 경험이 있다면 말씀해주세요.",
    ],
    "마케팅": [
        "신규 서비스 출시 캠페인을 한정된 예산으로 기획한다면 어떻게 하시겠습니까?",
        "마케팅 성과를 측정할 때 어떤 지표를 가장 중요하게 보시나요?",
        "광고 효율이 갑자기 떨어졌을 때 원인을 어떻게 찾으시겠습니까?",
        "타깃 고객을 정의하고 메시지를 만들었던 경험을 말씀해주세요.",
    ],
    "영업": [
        "경쟁사 제품을 쓰고 있는 고객사를 처음 만난다면 어떻게 설득하시겠습니까?",
        "월 목표 실적을 달성하기 어려운 상황이라면 어떻게 대응하시겠습니까?",
        "고객이 무리한 가격 인하나 일정 단축을 요구했을 때 어떻게 대응하셨나요?",
        "장기 고객과의 관계를 유지하기 위해 어떤 노력을 하시나요?",
    ],
    "인사(HR)": [
        "신입사원의 조기 퇴사율이 높다면 원인을 어떻게 분석하고 개선하시겠습니까?",
        "채용 공고를 냈는데 적합한 지원자가 적다면 어떻게 하시겠습니까?",
        "공정한 평가 제도를 만들기 위해 가장 중요하다고 생각하는 것은 무엇인가요?",
        "구성원 간 갈등을 중재했던 경험을 말씀해주세요.",
    ],
    "UX/UI 디자이너": [
        "사용자 이탈률이 높은 화면을 개선한다면 어떤 과정으로 진행하시겠습니까?",
        "사용자 리서치 결과와 이해관계자의 요구가 충돌하면 어떻게 결정하시나요?",
        "디자인 시스템을 구축하거나 운영해 본 경험이 있다면 말씀해주세요.",
        "접근성을 고려한 디자인을 위해 어떤 점을 신경 쓰시나요?",
    ],
    "서비스 기획자": [
        "신규 기능의 우선순위를 정할 때 어떤 기준을 사용하시나요?",
        "출시한 기능의 사용률이 예상보다 낮다면 어떻게 대응하시겠습니까?",
        "개발 일정이 부족할 때 기획 범위를 어떻게 조정하시겠습니까?",
        "데이터를 근거로 서비스 개선을 제안했던 경험을 말씀해주세요.",
    ],
}
ROLES = list(ROLE_QUESTIONS)

ANSWER_TYPES = [
    "매우 부실 (1문장): 성의 없거나 질문과 거의 무관",
    "부족 (2~3문장): 추상적이고 근거·경험 없이 일반론만 나열",
    "보통 (3~4문장): 질문에 맞는 내용이지만 구체적인 사례·방법·근거가 부족",
    "좋음 (4~6문장): 구체적인 경험이나 방법이 있고 구조가 있으나 결과나 직무 연결이 약간 아쉬움",
    "매우 우수 (5~7문장): 질문 유형에 맞게 완성도 높음 — 경험형은 상황·행동·결과(수치 포함), "
    "가정·설계·지식형은 단계별 방법과 선택 근거·트레이드오프, 그리고 직무와의 연결",
    "경험 없음·모름 (1~2문장): 해당 경험이나 지식이 없다고 솔직하게 말함 (관련 학습 의지를 한마디 덧붙일 수도 있음)",
    "좋은 말 나열형 (3~5문장): 기술 용어·경력 연차·포부·장점을 그럴듯하게 많이 나열함. 단, 프로젝트명·구체적 상황·"
    "수치·실제로 한 행동이나 방법은 절대 넣지 말 것 (겉보기엔 화려하지만 내용은 비어 있는 답변)",
]
STYLES = [
    "글로 정리해 쓴 자연스러운 문장으로 작성하세요.",
    "음성 인식(STT) 결과처럼 쓰세요: 쉼표·마침표 없이 이어 붙이고, '어', '그' 같은 말버릇과 "
    "소리 나는 대로 잘못 인식된 단어(오타) 1~2개를 섞으세요.",
]

# 백엔드 llama_service가 추론 시 보내는 시스템 프롬프트와 글자 하나까지 같아야 한다 (학습 데이터에 들어감).
SCORING_SYSTEM_PROMPT = (
    "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
    "지원자의 면접 질문과 답변을 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지).\n"
    "feedback의 각 항목은 1~2문장으로 간결하게 작성하세요.\n"
    '{"score":0~100,"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안",'
    '"tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}'
)

# 선생님 전용 채점 지시 (학습 데이터에는 넣지 않음 — 학생은 위 시스템 프롬프트만 보고 이 기준을 체화)
# 구간 기준은 실제 답변 사람 검토("너무 높음/낮음")에 맞춰 잡았다. (항목별 0~25 합산 방식은 시험해 보니
# 부실한 답변에도 항목마다 기본점이 붙어 오히려 후해져서 총점 방식으로 되돌림)
TEACHER_SCORING_PROMPT = (
    "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다. 지원자의 면접 답변을 엄격하게 채점하세요.\n\n"
    "먼저 질문 유형을 판단하세요: 경험형(과거 경험을 묻는 질문) / 가정·설계·지식형(어떻게 하시겠습니까, 무엇이 중요한가).\n\n"
    "채점 기준 (0~100점, 아래 구간 안에서 세밀하게 정수로 — 5의 배수만 쓰지 마세요):\n"
    "- 0~10: 무의미한 답변, 질문과 무관한 답변, '모르겠습니다'만 있는 답변\n"
    "- 11~30: 경험·지식이 없다고 솔직히 말한 답변(관련 학습 계획을 덧붙여도 30점 이하), 이름만 말하는 등 한 문장 수준의 성의 없는 답변\n"
    "- 31~50: 질문과 관련은 있지만 일반론·포부뿐인 답변. 경력·기술 용어·좋은 말을 많이 나열해도 "
    "실제 사례나 구체적인 방법·근거가 없으면 아무리 그럴듯해도 50점을 넘기지 마세요.\n"
    "- 51~65: 사례나 방법을 언급하지만 구체성이 부족하거나 결과·근거가 약한 답변\n"
    "- 66~80: 경험형은 구체적인 상황·행동·결과가 있는 답변(수치가 없어도 이 구간 가능), "
    "가정·설계·지식형은 단계별 방법과 선택 근거가 있는 답변\n"
    "- 81~100: 위 조건에 더해 수치 결과나 트레이드오프 분석, 직무와의 연결까지 탁월한 답변\n\n"
    "주의:\n"
    "- 가정·설계·지식형 질문에는 과거 경험의 수치 성과를 요구하지 마세요.\n"
    "- 말투(구어체, 문장부호 없음, 음성 인식 오타)로 감점하지 말고 내용만 보세요.\n\n"
    "feedback 작성 규칙:\n"
    "- 형식: \"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안\" 세 줄, 각 1~2문장.\n"
    "- 답변에 실제로 나온 내용(기술명, 사례, 표현)을 근거로 쓰고, 답변에 이미 있는 내용을 없다고 하지 마세요.\n"
    "- 경험이 없다고 답한 경우: 솔직함은 인정하고, 관련 학습·유사 경험·접근 방법을 말하는 법을 제안하세요.\n"
    "- 질문 유형에 맞는 조언을 하세요 (설계형에 STAR를 강요하지 않기).\n\n"
    "반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지):\n"
    '{"score":0~100,"feedback":"1. ...\\n2. ...\\n3. ...","tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}'
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


def answer_gen_conversation(role, question, round_idx):
    types = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(ANSWER_TYPES))
    n = len(ANSWER_TYPES)
    fmt = "\n".join(f"[{i + 1}] {i + 1}번째 답변" for i in range(n))
    return [{"role": "user", "content": (
        f"'{role}' 직무에 지원한 서로 다른 지원자 {n}명이 면접에서 아래 질문에 답한 내용을 만들어주세요.\n"
        f"질문: {question}\n\n"
        f"각 답변의 유형은 아래 순서를 정확히 따르세요:\n{types}\n\n"
        f"실제 면접 발화처럼 한국어로 작성하되, {STYLES[round_idx % len(STYLES)]}\n"
        "이름·회사명은 가상의 것을 쓰세요.\n"
        "각 답변은 줄바꿈 없이 한 줄로 쓰고, 아래 형식으로만 응답하세요 (다른 설명 금지):\n"
        f"{fmt}"
    )}]


def parse_answers(text: str) -> list:
    """'[n] 답변' 줄 형식 파싱 — JSON 배열보다 따옴표·줄바꿈에 덜 민감하다."""
    n = len(ANSWER_TYPES)
    found = {}
    for m in re.finditer(r"^\s*\[(\d)\]\s*(.+?)\s*$", text, re.MULTILINE):
        found.setdefault(int(m.group(1)), m.group(2))
    answers = [found[i] for i in range(1, n + 1)] if all(i in found for i in range(1, n + 1)) else []
    # 선생님이 형식 예시("[1] 1번째 답변")를 그대로 따라 쓴 경우 — v2에서 1개 조합(7줄)이 이렇게 섞였다
    if any(re.fullmatch(r"\d+번째 답변", a) for a in answers):
        return []
    return answers


def scoring_conversation(question, answer):
    return [
        {"role": "system", "content": TEACHER_SCORING_PROMPT},
        {"role": "user", "content": f"면접 질문: {question}\n지원자 답변: {answer}"},
    ]


def all_cases(rounds):
    return [(rd, role, q) for rd in range(rounds) for role in ROLES
            for q in COMMON_QUESTIONS + ROLE_QUESTIONS[role]]


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
    parser.add_argument("--trial", action="store_true",
                        help="시험용: 공통 경험형(글) 1개 + 직무별 설계형(STT 말투) 1개만 생성")
    parser.add_argument("--gen_batch", type=int, default=8)
    parser.add_argument("--score_batch", type=int, default=10)
    args = parser.parse_args()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    done = load_done()
    cases = [c for c in all_cases(args.rounds) if c not in done]
    if args.trial:
        cases = [(0, ROLES[0], COMMON_QUESTIONS[0]), (1, ROLES[2], ROLE_QUESTIONS[ROLES[2]][0])]
    if args.limit:
        cases = cases[: args.limit]
    print(f"처리할 조합 {len(cases)}개 (이미 완료 {len(done)}개)", flush=True)
    if not cases:
        print(f"GENERATION_DONE 0개 → {OUT_PATH}", flush=True)
        return

    model, tokenizer = load_teacher()
    print("선생님 모델 로딩 완료", flush=True)

    saved = 0
    for i in range(0, len(cases), args.gen_batch):
        chunk = cases[i:i + args.gen_batch]
        raw = generate_batch(model, tokenizer, [answer_gen_conversation(r, q, rd) for rd, r, q in chunk], 2000, 0.8)

        items = []  # (case, answer_type, answer)
        for case, text in zip(chunk, raw):
            answers = parse_answers(text)
            if answers and not any("�" in a for a in answers):
                items += [(case, t, a) for t, a in enumerate(answers)]
            else:
                print(f"[건너뜀] 답변 형식 오류: {case[1]} / {case[2][:12]} — {text[:80]!r}", flush=True)

        rows = []
        for j in range(0, len(items), args.score_batch):
            batch = items[j:j + args.score_batch]
            outs = generate_batch(model, tokenizer, [scoring_conversation(c[2], a) for c, _, a in batch], 600, 0)
            for (case, t, answer), text in zip(batch, outs):
                try:
                    r = parse_json(text)
                    score = int(r["score"])
                    if not (0 <= score <= 100 and r.get("feedback") and r.get("tip")):
                        raise ValueError
                    if not isinstance(r["feedback"], str) or "�" in r["feedback"] + r["tip"]:
                        raise ValueError  # 깨진 글자·잘못된 형식은 학습에 넣지 않음
                    rows.append((case, t, answer, {"score": score, "feedback": r["feedback"], "tip": r["tip"]}))
                except Exception:
                    print(f"[건너뜀] 채점 파싱 실패: {case[1]} / {case[2][:12]} / 유형 {t}", flush=True)

        with open(OUT_PATH, "a", encoding="utf-8") as f:
            for (rd, role, question), t, answer, label in rows:
                f.write(json.dumps({
                    "messages": [
                        {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                        {"role": "user", "content": f"면접 질문: {question}\n지원자 답변: {answer}"},
                        {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
                    ],
                    "meta": {"round": rd, "role": role, "question": question, "target_level": t},
                }, ensure_ascii=False) + "\n")
        saved += len(rows)
        print(f"진행 {min(i + args.gen_batch, len(cases))}/{len(cases)} 조합, 누적 {saved}개 저장", flush=True)

    print(f"GENERATION_DONE {saved}개 → {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
