"""
선생님 데이터를 학습/평가로 분리한다.

같은 (라운드, 직무, 질문) 조합의 답변 5개는 서로 비슷하므로 조합 단위로 통째로 평가셋에 넣어,
평가 답변과 거의 같은 답변이 학습에 섞이지 않게 한다. 학습 파일에서는 meta를 빼고,
평가 파일에는 레벨별 분석을 위해 meta를 남긴다.

실행:
    python split_teacher_dataset.py data/score_teacher_qwen.jsonl 12
"""
import json
import random
import sys
from pathlib import Path

src = Path(sys.argv[1])
eval_groups = int(sys.argv[2]) if len(sys.argv) > 2 else 12

rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
groups = sorted({(r["meta"]["round"], r["meta"]["role"], r["meta"]["question"]) for r in rows})
random.Random(42).shuffle(groups)
held_out = set(groups[:eval_groups])

train, evals = [], []
for r in rows:
    m = r["meta"]
    if (m["round"], m["role"], m["question"]) in held_out:
        evals.append(r)
    else:
        train.append({"messages": r["messages"]})

(src.parent / "teacher_train.jsonl").write_text(
    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in train), encoding="utf-8")
(src.parent / "teacher_eval.jsonl").write_text(
    "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in evals), encoding="utf-8")
print(f"train {len(train)}개 / eval {len(evals)}개 (평가 조합 {eval_groups}개)")
