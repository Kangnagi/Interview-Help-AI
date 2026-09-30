"""
v2.1: 선생님 데이터 v2의 점수 라벨만 다시 매긴다 (답변·피드백·팁은 그대로 재사용).

v2는 선생님이 총점을 매길 때 구간 경계값 근처(47점 35%, 74점 24%)만 반복해서 써서,
학생 모델이 사실상 10/47/74 세 단계로만 채점하게 됐다. 그래서 같은 선생님에게
"있냐 없냐"를 묻는 예/아니오 체크리스트 10개를 따로 매기게 하고,
최종 점수 = v2 총점 + 0.3 x (체크리스트 점수 - 40) 로 같은 총점 안에서 순위를 갈라 점수를 고르게 퍼뜨린다.
(총점은 사람 검토에 맞춘 구간 기준을 담고 있어 기준으로 두고, 체크리스트는 보정값으로만 쓴다.
 단순 평균은 시험해 보니 체크리스트가 중간 수준 답변에 낮게 나와 전체가 10~15점 깎였다.)

meta에 holistic(v2 총점)·checklist(10개 항목 0/1)를 남겨 검증에 쓴다. 중단 후 재실행하면 이어서 한다.

실행 (WSL, llama-finetune venv):
    python relabel_checklist.py
"""
import argparse
import json
import re
from pathlib import Path

import torch

from generate_teacher_scores import generate_batch, load_teacher

DATA_DIR = Path(__file__).resolve().parent / "data"
SRC_PATH = DATA_DIR / "score_teacher_qwen_v2.jsonl"
OUT_PATH = DATA_DIR / "score_teacher_qwen_v21.jsonl"
CHECKLIST_WEIGHT = 0.3   # 0.3/0.4를 시험 70개로 비교 — 0.3이 품질 단계별 평균 16/34/53/68/86으로 가장 고름

CHECKLIST = [
    "질문이 요구한 내용에 직접 답했다",
    "실제로 겪은 구체적인 상황·프로젝트(경험형) 또는 구체적인 방법·구성(가정·설계·지식형)이 제시되어 있다",
    "지원자가 한 행동이나 제안하는 방법의 단계가 구체적으로 설명되어 있다",
    "그 행동·선택의 이유나 근거가 설명되어 있다",
    "결과·성과(경험형) 또는 기대 효과(가정·설계·지식형)가 제시되어 있다",
    "수치·지표가 있거나(경험형), 트레이드오프·위험 요소를 고려했다(가정·설계·지식형)",
    "직무 역량과 명확하게 연결된다",
    "내용이 논리적인 순서로 구조화되어 있다",
    "추상적 표현·용어 나열·포부에 그치지 않고 내용이 실질적이다",
    "면접 답변으로 충분한 분량과 완결성을 갖췄다",
]
CHECKLIST_PROMPT = (
    "당신은 10년 차 전문 인사담당자입니다. 아래 면접 답변이 각 항목을 충족하는지 엄격하게 판정하세요.\n"
    "답변에서 확실하게 확인되는 경우에만 1, 애매하거나 없으면 0입니다. 말투(구어체·음성 인식 오타)는 무시하고 내용만 보세요.\n\n"
    + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(CHECKLIST))
    + "\n\n반드시 10개의 0 또는 1로 된 JSON 배열로만 응답하세요 (설명 금지). 예: [1,0,1,1,0,0,1,1,0,1]"
)


def parse_checklist(text: str):
    m = re.search(r"\[[\s\d,]+\]", text)
    if not m:
        return None
    vals = json.loads(m.group(0))
    return vals if len(vals) == len(CHECKLIST) and all(v in (0, 1) for v in vals) else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--limit", type=int, default=None, help="시험용: 앞에서부터 N개까지만")
    args = parser.parse_args()

    rows = [json.loads(l) for l in SRC_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    done = sum(1 for l in OUT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()) if OUT_PATH.exists() else 0
    print(f"재채점 대상 {len(rows)}개 (이미 완료 {done}개)", flush=True)
    if done >= len(rows):
        print(f"RELABEL_DONE {done}개 → {OUT_PATH}", flush=True)
        return

    model, tokenizer = load_teacher()
    print("선생님 모델 로딩 완료", flush=True)

    failed = 0
    for i in range(done, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        convs = [[{"role": "system", "content": CHECKLIST_PROMPT}, {"role": "user", "content": r["messages"][1]["content"]}]
                 for r in chunk]
        outs = generate_batch(model, tokenizer, convs, 40, 0)
        with open(OUT_PATH, "a", encoding="utf-8") as f:
            for r, text in zip(chunk, outs):
                label = json.loads(r["messages"][2]["content"])
                checks = parse_checklist(text)
                holistic = label["score"]
                if checks is None:
                    failed += 1   # 순서 유지를 위해 줄은 남기고 v2 총점을 그대로 쓴다
                    new_score = holistic
                else:
                    new_score = max(0, min(100, round(holistic + CHECKLIST_WEIGHT * (10 * sum(checks) - 40))))
                label["score"] = new_score
                r["messages"][2]["content"] = json.dumps(label, ensure_ascii=False)
                r["meta"].update({"holistic": holistic, "checklist": checks})
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"진행 {min(i + args.batch, len(rows))}/{len(rows)}, 체크리스트 파싱 실패 누적 {failed}", flush=True)

    print(f"RELABEL_DONE {len(rows)}개 (파싱 실패 {failed}) → {OUT_PATH}", flush=True)


if __name__ == "__main__":
    torch.manual_seed(0)
    main()
