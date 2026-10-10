"""
꼬리 질문 학습 데이터 준비 — qgen_fu_pool.jsonl(실제 답변)의 0~399번에 꼬리 질문 유형을 붙인다.
  1순위 유형: 서비스와 같은 규칙(llama_service.follow_up_types)
  0~199번은 2순위 유형도 하나 더 (면접의 두 번째 꼬리 질문은 다른 유형이라, 다른 유형도 따를 줄 알아야 한다)
  — 2·3순위 중 지금까지 적게 나온 유형을 골라 유형 수를 맞춘다.
출력: data/qgen_fu2_assign.jsonl {idx, types}. 이 유형대로 쓴 꼬리 질문은 data/qgen_fu2_b*.jsonl {idx, type, follow_up}.
"""
import collections
import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)
from services.llm.llama_service import follow_up_types  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
pool = [json.loads(l) for l in open(os.path.join(DATA, "qgen_fu_pool.jsonl"), encoding="utf-8")][:400]
orders = [follow_up_types(p["question"], p["answer"]) for p in pool]
count = collections.Counter(o[0] for o in orders)
with open(os.path.join(DATA, "qgen_fu2_assign.jsonl"), "w", encoding="utf-8") as out:
    for p, o in zip(pool, orders):
        types = [o[0]]
        if p["idx"] < 200:
            second = min(o[1:3], key=lambda t: (count[t], o.index(t)))
            types.append(second)
            count[second] += 1
        out.write(json.dumps({"idx": p["idx"], "types": types}, ensure_ascii=False) + "\n")
print(dict(count), sum(count.values()))
