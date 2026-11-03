"""
질문 모델 q3용 참고 자료 — AI Hub '채용면접 인터뷰 데이터' 경력자 라벨링 JSON의 실제 면접관 질문을 직군별로 모은다.

  python training/build_qgen_realq_pool.py "<…/02.라벨링데이터/TL_01.Management_Female_Experienced>"

q3는 꼬리 질문을 학습하지 않고 질문 생성만 배운다 (10/13 결정 — 실제 면접은 꼬리 질문보다 자기소개서 질문이 많다).
이 실제 질문은 모델에 그대로 넣지 않는다 — 서비스 입력(지원 정보 + 자기소개서)에는 이런 질문이 없으므로,
Claude가 직무 질문을 쓸 때 "실제 면접관이 이 직군에 묻는 것"을 지원자 자기소개서 · 직무에 맞게 응용하는 재료로만 쓴다.

- 면접관 말의 추임새('어', '음', '아' …)만 지우고, 비슷한 질문은 한 번만
- 지원 동기 · 자기소개(서비스의 고정 질문)와 겹치는 질문은 뺀다
출력: data/qgen_realq_pool.jsonl {occupation, intent, question}  (data/qgen_* 는 git 제외)
"""
import collections
import glob
import json
import os
import re
import sys

DATA = os.path.join(os.path.dirname(__file__), "data")
sys.stdout.reconfigure(encoding="utf-8")
FILLER = re.compile(r"(?:(?<=\s)|^)(?:어|음|아|으|그|저기|네|자)(?=\s)")
FIXED = re.compile(r"지원\s?동기|지원한 이유|지원하신 이유|지원하게 된|지원해 주신|자기소개|관심을 가지게|관심을 갖게")


def clean(q: str) -> str:
    q = re.sub(r"\s+", " ", FILLER.sub("", re.sub(r"\s+", " ", q))).strip()
    return q


def key(q: str) -> str:
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", q)[:24]


rows, seen = [], set()
for f in sorted(glob.glob(os.path.join(sys.argv[1], "**", "*.json"), recursive=True)):
    try:
        d = json.load(open(f, encoding="utf-8"))["dataSet"]
    except Exception:
        continue
    q = clean(d["question"]["raw"]["text"])
    if len(q) < 15 or FIXED.search(q) or key(q) in seen:
        continue
    seen.add(key(q))
    intent = next((it.get("category") for it in d["answer"].get("intent", []) if it.get("category")), "etc")
    rows.append({"occupation": d["info"]["occupation"], "intent": intent, "question": q})

with open(os.path.join(DATA, "qgen_realq_pool.jsonl"), "w", encoding="utf-8") as out:
    for r in rows:
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
print("실제 질문", len(rows), "| 직군", dict(collections.Counter(r["occupation"] for r in rows)),
      "| 의도", dict(collections.Counter(r["intent"] for r in rows)))
