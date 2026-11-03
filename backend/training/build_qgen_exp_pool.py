"""
질문 모델 q3용 꼬리 질문 재료 — AI Hub '채용면접 인터뷰 데이터' 경력자 라벨링 JSON에서 질문 · 답변 2,000개를 고른다.

  python training/build_qgen_exp_pool.py "<…/02.라벨링데이터/TL_01.Management_Female_Experienced>" [개수=2000]

- 직군(occupation) 7개에서 같은 수씩 (모자란 직군 몫은 다른 직군에서 채움)
- 답변 150자 이상(꼬리 질문으로 짚을 내용이 있어야), 비슷한 질문은 한 번만
- 질문은 면접관 말의 추임새('어', '음', '아')만 지운다 — 서비스의 질문은 글로 쓴 문장이라
  답변은 그대로 둔다 — 서비스의 답변도 음성 인식 결과(추임새 · 띄어쓰기 오류 포함)라 같은 모양이 학습에 맞다
- 유형: 서비스와 같은 규칙(llama_service.follow_up_types)의 1~3순위 중 목표 비율보다 적게 나온 쪽 (강점형은 1순위일 때만)

출력: data/qgen_exp_pool.jsonl {idx, src, occupation, question, answer, type}  (data/qgen_* 는 git 제외)
이 유형대로 쓴 꼬리 질문은 data/qgen_exp_b*.jsonl {idx, type, follow_up}.
"""
import collections
import glob
import json
import logging
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)
from services.llm.llama_service import follow_up_types  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
SRC, N = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2000
TARGET = {"role": 0.35, "why": 0.30, "whatif": 0.20, "strength": 0.15}   # q2 실제 서비스 분포에 가깝게
FILLER = re.compile(r"(?:(?<=\s)|^)(?:어|음|아|으|그|저기)(?=\s)")


def clean_question(q: str) -> str:
    q = FILLER.sub("", q)
    q = re.sub(r"\s+", " ", q).strip()
    if q and not re.search(r"[.?!]$", q):
        q += "?" if re.search(r"(나요|까요|가요|니까|ㅂ니까|어요|세요|겠어요|십니까|있나요|인가요|습니까)$", q) else "."
    return q


def key(q: str) -> str:
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", q)[:30]


rows = []
for f in sorted(glob.glob(os.path.join(SRC, "**", "*.json"), recursive=True)):
    try:
        d = json.load(open(f, encoding="utf-8"))["dataSet"]
    except Exception:
        continue
    q, a = d["question"]["raw"]["text"].strip(), re.sub(r"\s+", " ", d["answer"]["raw"]["text"]).strip()
    if len(a) < 150 or len(q) < 10:
        continue
    rows.append({"src": os.path.basename(f), "occupation": d["info"]["occupation"], "question": clean_question(q), "answer": a})

random.seed(1013)
random.shuffle(rows)
by_occ = collections.defaultdict(list)
for r in rows:
    by_occ[r["occupation"]].append(r)
share = N // len(by_occ)
picked, seen = [], set()
for occ, items in sorted(by_occ.items(), key=lambda x: len(x[1])):            # 적은 직군부터
    left = len(by_occ) - len({p["occupation"] for p in picked})
    want = min(len(items), (N - len(picked)) // max(left, 1))
    n = 0
    for r in items:
        k = key(r["question"])
        if k in seen:
            continue
        seen.add(k)
        picked.append(r)
        n += 1
        if n >= want:
            break

count = collections.Counter()
with open(os.path.join(DATA, "qgen_exp_pool.jsonl"), "w", encoding="utf-8") as out:
    for i, r in enumerate(picked):
        order = follow_up_types(r["question"], r["answer"])
        # 1~3순위 중 목표 비율 대비 덜 나온 유형 — 강점형은 규칙이 1순위로 고른 답변(장단점 · 성향)에만 (억지 강점 질문 방지)
        cands = [t for t in order[:3] if t != "strength" or t == order[0]]
        t = min(cands, key=lambda t: (count[t] / max(1, i) - TARGET[t], order.index(t)))
        count[t] += 1
        out.write(json.dumps({"idx": i, **r, "type": t}, ensure_ascii=False) + "\n")
print("고른 수", len(picked), "| 직군", dict(collections.Counter(p["occupation"] for p in picked)), "| 유형", dict(count))
