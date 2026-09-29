"""선생님 데이터 점검: 의도한 품질 단계(target_level)별 점수가 순서대로 올라가는지 확인."""
import json
import sys
from collections import defaultdict
from pathlib import Path

path = Path(sys.argv[1])
show = "--show" in sys.argv
by_level = defaultdict(list)
rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

for r in rows:
    label = json.loads(r["messages"][2]["content"])
    lvl = r["meta"]["target_level"]
    by_level[lvl].append(label["score"])
    if show:
        answer = r["messages"][1]["content"].split("지원자 답변: ", 1)[1]
        print(f"[레벨 {lvl} → {label['score']}점] {answer[:90]}")
        print(f"   피드백: {label['feedback'][:120]!r}")
        print(f"   팁: {label['tip'][:80]}")

names = ["매우 부실", "부족", "보통", "좋음", "매우 우수"]
print(f"\n총 {len(rows)}개")
for lvl in sorted(by_level):
    s = by_level[lvl]
    print(f"레벨 {lvl} ({names[lvl]}): 평균 {sum(s) / len(s):5.1f}점, 범위 {min(s)}~{max(s)}, {len(s)}개")
