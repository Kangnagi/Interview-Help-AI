"""선생님 데이터 점검: 의도한 답변 유형(target_level)별 점수 분포 확인. --show 로 개별 예시 출력."""
import json
import sys
from collections import Counter, defaultdict
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
        question = r["messages"][1]["content"].split("\n", 1)[0]
        print(f"[유형 {lvl} → {label['score']}점 {r['meta'].get('sub_scores', '')}] {question[:40]}")
        print(f"   답변: {answer[:120]}")
        print(f"   피드백: {label['feedback'][:200]!r}")
        print(f"   팁: {label['tip'][:80]}")

names = ["매우 부실", "부족", "보통", "좋음", "매우 우수", "경험 없음·모름", "좋은 말 나열형"]
print(f"\n총 {len(rows)}개")
for lvl in sorted(by_level):
    s = by_level[lvl]
    print(f"유형 {lvl} ({names[lvl]}): 평균 {sum(s) / len(s):5.1f}점, 범위 {min(s)}~{max(s)}, {len(s)}개")
top = Counter(s for v in by_level.values() for s in v).most_common(8)
print("가장 흔한 점수:", ", ".join(f"{s}점×{c}" for s, c in top))
