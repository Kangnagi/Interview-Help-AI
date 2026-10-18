"""q3 꼬리 질문 작성용 — qgen_exp_pool.jsonl의 [시작, 끝) 구간을 읽기 좋게 출력 (작성자 확인용)."""
import json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
DATA = os.path.join(os.path.dirname(__file__), "data")
a, b = int(sys.argv[1]), int(sys.argv[2])
for l in open(os.path.join(DATA, "qgen_exp_pool.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if a <= r["idx"] < b:
        print(f"#{r['idx']} [{r['type']}] Q: {r['question']}\nA: {r["answer"][:460]}\n")
