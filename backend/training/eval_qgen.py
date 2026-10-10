"""
질문 전용 어댑터 평가 — 같은 평가 입력으로 지금 방식(키워드 + 질문 틀)과 어댑터가 직접 쓴 질문을 비교한다.

  cd backend && .venv\\Scripts\\python training\\eval_qgen.py --adapter ai_models/bllossom-qgen-q1
입력: training/data/qgen_eval_prompts.jsonl (build_qgen_dataset.py, 학습에 쓰지 않은 자기소개서 30 + 실제 답변 30 × 유형 2개)
출력: training/data/qgen_eval_<어댑터 이름>.jsonl (질문 원문 — 팀 블라인드 비교용), 화면에 자동 지표

자동 지표 (사람 평가 전 1차 거르기용)
  - 쓸 수 있는 질문: 서버 질문 검사(is_valid_question) 통과
  - 자기소개서 근거: 질문에 자기소개서의 고유한 말(띄어쓰기 빼고 4글자 이상 겹침, 흔한 말 제외)이 들어 있음
  - 중복: 한 풀 안에서 거의 같은 질문
  - 유형 일치 (꼬리 질문): 요청한 유형으로 썼는지 (서버의 유형 판별 follow_up_type_of 기준)
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.stdout.reconfigure(encoding="utf-8")
from services.llm import llama_service as L  # noqa: E402

QGEN = "qgen"
def _squash(s: str) -> str:
    return L._squash_text(s)


def grounded(question: str, intro: str) -> bool:
    return L.question_grounded(question, intro)   # 서버의 검사와 같은 기준


def near_dup(qs: list) -> int:
    seen, dup = [], 0
    for q in qs:
        s = _squash(q)
        if any(len(set(s) & set(o)) / max(1, len(set(s) | set(o))) > 0.8 for o in seen):
            dup += 1
        seen.append(s)
    return dup


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True)
    args = ap.parse_args()
    name = os.path.basename(os.path.normpath(args.adapter))
    rows = [json.loads(l) for l in open(os.path.join(HERE, "data", "qgen_eval_prompts.jsonl"), encoding="utf-8")]

    await L.llama_service.load_model()
    L.llama_service.model.load_adapter(args.adapter, adapter_name=QGEN)

    out, stat = [], {k: {"n": 0, "valid": 0, "grounded": 0, "dup": 0, "type": 0, "sec": 0.0} for k in
                     ("qgen_template", "qgen_model", "fu_template", "fu_model")}
    for r in rows:
        if r["task"] == "qgen":
            info, intro = L.split_self_intro(r["resume_text"])
            t0 = time.time(); base = await L.generate_questions_from_resume(r["resume_text"], "general", num_questions=8); tb = time.time() - t0
            t0 = time.time()
            text = (await L.llama_service.generate_batch([L.qgen_messages(r["resume_text"])], 700, QGEN, greedy=True))[0]
            tm = time.time() - t0
            model = [q.strip() for q in L._extract_questions(text)]
            for key, qs, sec in (("qgen_template", base, tb), ("qgen_model", model, tm)):
                st = stat[key]; st["sec"] += sec
                st["n"] += len(qs); st["valid"] += sum(L.is_valid_question(q) for q in qs)
                st["grounded"] += sum(grounded(q, intro) for q in qs) if intro else 0
                st["dup"] += near_dup(qs)
            out.append({**r, "template": base, "model": model, "model_raw": text})
        else:
            t0 = time.time(); base = await L.generate_follow_up(r["question"], r["answer"], [r["question"]]); tb = time.time() - t0
            t0 = time.time()
            text = (await L.llama_service.generate_batch([L.followup_messages(r["question"], r["answer"], r["fu_type"])], 120, QGEN, greedy=True))[0]
            tm = time.time() - t0
            model = text.strip().splitlines()[0].strip() if text.strip() else ""
            for key, q, sec in (("fu_template", base, tb), ("fu_model", model, tm)):
                st = stat[key]; st["sec"] += sec; st["n"] += 1
                st["valid"] += bool(q) and L.is_valid_question(q)
                st["grounded"] += bool(q) and grounded(q, r["answer"])
                st["type"] += bool(q) and L.follow_up_type_of(q) == r["fu_type"]
            out.append({**r, "template": base, "model": model, "model_raw": text})

    path = os.path.join(HERE, "data", f"qgen_eval_{name}.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_intro = sum(1 for r in rows if r["task"] == "qgen")
    print(f"===== {name} (자기소개서 {n_intro}개 · 실제 답변 {len(rows) - n_intro}개)")
    for key, st in stat.items():
        n = max(1, st["n"]); cnt = n_intro if key.startswith("qgen") else len(rows) - n_intro
        print(f"{key:14s} 질문 {st['n']:3d}개 | 쓸 수 있음 {st['valid'] / n:5.0%} | 근거 있음 {st['grounded'] / n:5.0%}"
              f" | 중복 {st['dup']}" + (f" | 유형 일치 {st['type'] / n:5.0%}" if key.startswith("fu") else "")
              + f" | 평균 {st['sec'] / max(1, cnt):.1f}초")
    print(f"결과 원문: {path}")


if __name__ == "__main__":
    asyncio.run(main())
