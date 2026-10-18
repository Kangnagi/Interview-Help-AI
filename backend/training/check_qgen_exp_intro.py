"""
질문 모델 q3 데이터 검사 — Claude가 쓴 경력자 자기소개서 질문 배치 (data/qgen_exp_intro_b*.jsonl).

  python training/check_qgen_exp_intro.py training/data/qgen_exp_intro_b01.jsonl [...]
  python training/check_qgen_exp_intro.py --show <직군> <개수> <시드>   # 직군 실제 질문 보기 (작성 재료)

한 줄 = {id, occupation, company, job, duty, ideal, intro, questions[6], refs[]}
  refs: 직무 질문(3 · 6번째)을 쓸 때 응용한 실제 면접 질문 (data/qgen_realq_pool.jsonl) — 팀 검토용, 학습엔 안 씀
서비스(model_question_pool)가 모델 출력을 거르는 검사와 같은 것 + 작성 기준(question_guide.md)의 길이 · 겹침.
"""
import json
import logging
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)
from services.llm.llama_service import (is_valid_question, question_grounded, _similar_question,  # noqa: E402
                                        _AWKWARD_QUESTION, _FIXED_OVERLAP, QGEN_POOL_SIZE)

DATA = os.path.join(os.path.dirname(__file__), "data")
sys.stdout.reconfigure(encoding="utf-8")
OCCS = {"ARD", "BM", "ICT", "MM", "PS", "RND", "SM"}

if sys.argv[1] == "--show":
    occ, k, seed = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    pool = [json.loads(l) for l in open(os.path.join(DATA, "qgen_realq_pool.jsonl"), encoding="utf-8")]
    rnd = random.Random(seed)
    for r in rnd.sample([r for r in pool if r["occupation"] == occ], k):
        print(f"[{r['intent']}] {r['question']}")
    sys.exit()

bad = n = 0
ids = set()
for path in sys.argv[1:]:
    for line_no, line in enumerate(open(path, encoding="utf-8"), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        probs = []
        if r["id"] in ids:
            probs.append("id 중복")
        ids.add(r["id"])
        if r.get("occupation") not in OCCS:
            probs.append("직군")
        if not r.get("job") or not r.get("duty"):
            probs.append("직무 · 직무 설명 없음")
        qs, intro = r.get("questions", []), r.get("intro", "")
        if len(qs) != QGEN_POOL_SIZE:
            probs.append(f"질문 {len(qs)}개")
        if intro and not 200 <= len(intro) <= 900:
            probs.append(f"자기소개서 길이 {len(intro)}")
        if not r.get("refs"):
            probs.append("refs 없음")
        for i, q in enumerate(qs):
            tag = f"Q{i + 1}"
            if not is_valid_question(q) or not 35 <= len(q) <= 130:
                probs.append(f"{tag} 형식/길이 {len(q)}")
            if _AWKWARD_QUESTION.search(q) or _FIXED_OVERLAP.search(q):
                probs.append(f"{tag} 어색 · 고정 질문과 겹침")
            if intro and i in (0, 1, 3, 4) and not question_grounded(q, intro):
                probs.append(f"{tag} 자기소개서 근거 없음")
            if not intro and "자기소개서" in q:
                probs.append(f"{tag} 자기소개서 없는데 언급")
            if any(_similar_question(q, o) for o in qs[:i]):
                probs.append(f"{tag} 앞 질문과 비슷")
        if probs:
            bad += 1
            print(f"{os.path.basename(path)}:{line_no} {r['id']}: {', '.join(probs)}")
print(f"검사 {n}개, 문제 {bad}개")
