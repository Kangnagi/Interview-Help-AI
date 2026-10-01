"""
바탕화면 llama-finetune 학습 데이터(실제 면접 답변, 약 68,000개)에서 채점할 답변을 무작위로 뽑는다.

원본은 "질문+답변 → 요약·피드백" 형식이라 점수가 없다. 여기서 뽑은 답변을 선생님 모델이 채점하면
(score_real_pool.py) 합성이 아닌 실제 답변 분포의 채점 데이터가 된다.
원문의 재배포 조건을 확인하지 않았으므로 결과 파일은 저장소에 올리지 않는다 (.gitignore).

실행 (WSL):
    python build_real_pool.py --src /mnt/c/Users/Owner/Desktop/llama-finetune/llama-finetune/training
"""
import argparse
import json
import random
import re
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent / "data" / "real_pool.jsonl"
USER_RE = re.compile(r"질문:\s*(.+?)\n답변:\s*(.+?)\n\n위 지원자의 답변을 요약하고 평가해주세요\.?\s*$", re.S)


def load(path: Path, source: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = USER_RE.match(json.loads(line)["messages"][1]["content"])
            if m:
                q, a = m.group(1).strip(), m.group(2).strip()
                if 30 <= len(a) <= 1500 and len(q) >= 5:
                    rows.append({"question": q, "answer": a, "source": source})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--new", type=int, default=1900)
    parser.add_argument("--experienced", type=int, default=500)
    args = parser.parse_args()

    rng = random.Random(42)
    pool = []
    for fname, source, n in [("train_New.jsonl", "new", args.new), ("train_Experienced.jsonl", "experienced", args.experienced)]:
        rows = load(Path(args.src) / fname, source)
        seen, uniq = set(), []
        for r in rows:
            if r["answer"] not in seen:
                seen.add(r["answer"])
                uniq.append(r)
        pool += rng.sample(uniq, min(n, len(uniq)))
    rng.shuffle(pool)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for i, r in enumerate(pool):
            f.write(json.dumps({"idx": i, **r}, ensure_ascii=False) + "\n")
    print(f"채점 대상 {len(pool)}개 → {OUT_PATH}")


if __name__ == "__main__":
    main()
