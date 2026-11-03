"""학습/평가 데이터 분리 — 평가셋은 학습에 쓰지 않고, 학습 후 Gemini 점수와 비교하는 데만 쓴다."""
import json
import random
import sys
from pathlib import Path

src = Path(sys.argv[1])
eval_count = int(sys.argv[2]) if len(sys.argv) > 2 else 10

lines = src.read_text(encoding="utf-8").strip().splitlines()
random.Random(42).shuffle(lines)

eval_lines, train_lines = lines[:eval_count], lines[eval_count:]
(src.parent / "score_train.jsonl").write_text("\n".join(train_lines) + "\n", encoding="utf-8")
(src.parent / "score_eval.jsonl").write_text("\n".join(eval_lines) + "\n", encoding="utf-8")
print(f"train {len(train_lines)}개 / eval {len(eval_lines)}개")
