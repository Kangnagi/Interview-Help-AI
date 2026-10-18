"""q3 꼬리 질문 검사 — data/qgen_exp_b*.jsonl을 서비스와 같은 규칙으로 확인 (유형 표시어 · 질문 형태 · 길이 · 민감 주제 · 원문 근거)."""
import glob, json, logging, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)
sys.stdout.reconfigure(encoding="utf-8")
from services.llm.llama_service import follow_up_type_of, is_valid_question, _SENSITIVE_TOPIC  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")
pool = {r["idx"]: r for r in map(json.loads, open(os.path.join(DATA, "qgen_exp_pool.jsonl"), encoding="utf-8"))}
files = sys.argv[1:] or sorted(glob.glob(os.path.join(DATA, "qgen_exp_b*.jsonl")))
bad = n = 0
for f in files:
    for line in open(f, encoding="utf-8"):
        r = json.loads(line); n += 1
        p = pool[r["idx"]]; q = r["follow_up"]
        errs = []
        if r["type"] != p["type"]: errs.append(f"유형 배정 다름({p['type']})")
        if follow_up_type_of(q) != r["type"]: errs.append(f"표시어 판별={follow_up_type_of(q)}")
        if not is_valid_question(q): errs.append("질문 형태")
        if not 25 <= len(q) <= 130: errs.append(f"길이 {len(q)}")
        if _SENSITIVE_TOPIC.search(p["question"] + " " + p["answer"]): errs.append("민감 주제(서비스는 꼬리 질문 안 함)")
        if re.search(r"(^|\s)(어|음|아)\s", q): errs.append("추임새")
        words = [w for w in re.findall(r"[가-힣]{2,}", q)]
        if not any(w[:2] in p["answer"] for w in words): errs.append("답변 근거 없음")
        if errs:
            bad += 1; print(f"#{r['idx']} [{r['type']}] {' · '.join(errs)} | {q}")
print(f"검사 {n}개, 문제 {bad}개")
