"""v2.1 재채점 점검: 유형별 v2 총점 vs 체크리스트 vs 최종 점수, 점수 쏠림 정도."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

rows = [json.loads(l) for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
names = ["매우 부실", "부족", "보통", "좋음", "매우 우수", "경험 없음·모름", "좋은 말 나열형"]
by = defaultdict(lambda: {"h": [], "c": [], "f": []})
for r in rows:
    m = r["meta"]
    d = by[m["target_level"]]
    d["h"].append(m["holistic"])
    d["c"].append(10 * sum(m["checklist"]) if m["checklist"] else None)
    d["f"].append(json.loads(r["messages"][2]["content"])["score"])

avg = lambda xs: sum(x for x in xs if x is not None) / max(1, sum(x is not None for x in xs))
print(f"총 {len(rows)}개 (체크리스트 실패 {sum(r['meta']['checklist'] is None for r in rows)}개)")
print(f"{'유형':<12} {'v2총점':>6} {'체크':>6} {'최종':>6}  최종 범위")
for lvl in sorted(by):
    d = by[lvl]
    print(f"{names[lvl]:<12} {avg(d['h']):6.1f} {avg(d['c']):6.1f} {avg(d['f']):6.1f}  {min(d['f'])}~{max(d['f'])}")
finals = [json.loads(r["messages"][2]["content"])["score"] for r in rows]
top = Counter(finals).most_common(6)
print(f"서로 다른 점수 {len(set(finals))}종, 가장 흔한 점수: " + ", ".join(f"{s}점×{c}" for s, c in top))
old_top = Counter(r["meta"]["holistic"] for r in rows).most_common(3)
print("(v2 총점의 가장 흔한 점수: " + ", ".join(f"{s}점×{c}" for s, c in old_top) + ")")
