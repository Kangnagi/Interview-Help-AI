"""
실제 면접 답변(real_pool.jsonl)을 선생님 모델(Qwen2.5-14B)로 채점해 학습 데이터로 만든다 — Gemini 미사용.

v2.1과 같은 방식: ① 사람 검토에 맞춘 구간 기준으로 총점·피드백·팁 ② 예/아니오 체크리스트 10개
→ 최종 점수 = 총점 + 0.3 x (체크리스트 - 40). 학습 데이터 형식·시스템 프롬프트는 v2.1과 동일.
중단 후 재실행하면 이어서 한다. 채점 실패한 답변은 meta.failed=true로 남기고 학습에서 뺀다.

실행 (WSL, llama-finetune venv):
    python score_real_pool.py
"""
import argparse
import json
from pathlib import Path

from generate_teacher_scores import (
    SCORING_SYSTEM_PROMPT, TEACHER_SCORING_PROMPT, generate_batch, load_teacher, parse_json,
)
from relabel_checklist import CHECKLIST_PROMPT, CHECKLIST_WEIGHT, parse_checklist

DATA_DIR = Path(__file__).resolve().parent / "data"
SRC_PATH = DATA_DIR / "real_pool.jsonl"
OUT_PATH = DATA_DIR / "score_teacher_real.jsonl"


def user_content(r: dict) -> str:
    return f"면접 질문: {r['question']}\n지원자 답변: {r['answer']}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows = [json.loads(l) for l in SRC_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    done = sum(1 for l in OUT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()) if OUT_PATH.exists() else 0
    print(f"채점 대상 {len(rows)}개 (이미 완료 {done}개)", flush=True)
    if done >= len(rows):
        print(f"REAL_SCORING_DONE {done}개 → {OUT_PATH}", flush=True)
        return

    model, tokenizer = load_teacher()
    print("선생님 모델 로딩 완료", flush=True)

    failed = 0
    for i in range(done, len(rows), args.batch):
        chunk = rows[i:i + args.batch]
        holistic_outs = generate_batch(model, tokenizer, [
            [{"role": "system", "content": TEACHER_SCORING_PROMPT}, {"role": "user", "content": user_content(r)}]
            for r in chunk], 600, 0)
        check_outs = generate_batch(model, tokenizer, [
            [{"role": "system", "content": CHECKLIST_PROMPT}, {"role": "user", "content": user_content(r)}]
            for r in chunk], 40, 0)

        with open(OUT_PATH, "a", encoding="utf-8") as f:
            for r, h_text, c_text in zip(chunk, holistic_outs, check_outs):
                meta = {"idx": r["idx"], "source": r["source"]}
                try:
                    h = parse_json(h_text)
                    holistic = int(h["score"])
                    if not (0 <= holistic <= 100 and isinstance(h.get("feedback"), str) and h["feedback"].strip()
                            and h.get("tip")) or "�" in h["feedback"] + h["tip"]:
                        raise ValueError
                    checks = parse_checklist(c_text)
                    score = holistic if checks is None else \
                        max(0, min(100, round(holistic + CHECKLIST_WEIGHT * (10 * sum(checks) - 40))))
                    label = {"score": score, "feedback": h["feedback"], "tip": h["tip"]}
                    meta.update({"holistic": holistic, "checklist": checks})
                except Exception:
                    failed += 1
                    label, meta["failed"] = {"score": None, "feedback": "", "tip": ""}, True
                f.write(json.dumps({
                    "messages": [
                        {"role": "system", "content": SCORING_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content(r)},
                        {"role": "assistant", "content": json.dumps(label, ensure_ascii=False)},
                    ],
                    "meta": meta,
                }, ensure_ascii=False) + "\n")
        print(f"진행 {min(i + args.batch, len(rows))}/{len(rows)}, 실패 누적 {failed}", flush=True)

    print(f"REAL_SCORING_DONE {len(rows)}개 (실패 {failed}) → {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
