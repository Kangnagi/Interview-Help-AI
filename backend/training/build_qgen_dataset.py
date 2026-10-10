"""
질문 전용 어댑터 학습 데이터 만들기 (Windows backend 가상환경에서 실행 — 서비스와 같은 입력 형식을 쓰려고 llama_service를 불러온다).

입력 (data/, 모두 git 제외)
  qgen_intro_b*.jsonl : 가상 자기소개서 + 질문 6개 (Claude 작성, 기준 question_guide.md)
  qgen_fu2_b*.jsonl   : {idx, type, follow_up} — qgen_fu_pool.jsonl(바탕화면 실제 면접 답변)의 idx에 붙인 유형별 꼬리 질문
                        (유형 배정: assign_fu_types.py → qgen_fu2_assign.jsonl, 0~199번은 유형 2개씩)
출력
  qgen_train_msgs.jsonl : messages 형식 학습 데이터 (자기소개서 질문은 3배 — 꼬리 질문 600개와 비율을 맞춤)
  qgen_eval_prompts.jsonl : 평가용 입력 (qgen_eval_intro 30개 + 학습에 안 쓴 실제 답변 30개 × 유형 2개)

실행: cd backend && .venv\\Scripts\\python training\\build_qgen_dataset.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from services.llm.llama_service import (qgen_messages, followup_messages, follow_up_types, follow_up_type_of,  # noqa: E402
                                        is_valid_question, QGEN_POOL_SIZE)

DATA = os.path.join(HERE, "data")
INTRO_REPEAT = 3
FU_EVAL = range(400, 430)   # 꼬리 질문 평가용 — 학습 데이터(0~399)와 겹치지 않는 실제 답변


def resume_text(r: dict) -> str:
    """화면(PracticeInterviewPage)이 서버로 보내는 형식과 같게."""
    title = " ".join(x for x in (r.get("company"), r.get("job")) if x) + " 지원"
    lines = [
        f"제목: {title}",
        r.get("company") and f"지원 회사: {r['company']}",
        r.get("job") and f"지원 직무: {r['job']}",
        r.get("duty") and f"직무 설명: {r['duty']}",
        r.get("ideal") and f"인재상: {r['ideal']}",
        r.get("intro") and f"자기소개서: {r['intro']}",
    ]
    return "\n".join(x for x in lines if x)


def load(pattern: str) -> list:
    rows = []
    for p in sorted(glob.glob(os.path.join(DATA, pattern))):
        rows += [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    return rows


def main():
    intros = load("qgen_intro_b*.jsonl")
    fus = load("qgen_fu2_b*.jsonl")
    pool = {r["idx"]: r for r in load("qgen_fu_pool.jsonl")}

    train = []
    for r in intros:
        qs = r["questions"]
        assert len(qs) == QGEN_POOL_SIZE and all(is_valid_question(q) for q in qs), r["id"]
        msgs = qgen_messages(resume_text(r)) + [{"role": "assistant", "content": json.dumps(qs, ensure_ascii=False)}]
        train += [{"messages": msgs, "task": "qgen", "id": r["id"]}] * INTRO_REPEAT
    for r in fus:
        p = pool[r["idx"]]
        assert r["idx"] not in FU_EVAL and is_valid_question(r["follow_up"]), r["idx"]
        assert follow_up_type_of(r["follow_up"]) == r["type"], (r["idx"], r["type"])   # 서버가 유형을 알아볼 수 있게
        msgs = followup_messages(p["question"], p["answer"], r["type"]) + [{"role": "assistant", "content": r["follow_up"]}]
        train.append({"messages": msgs, "task": "followup", "id": f"fu{r['idx']}-{r['type']}"})

    with open(os.path.join(DATA, "qgen_train_msgs.jsonl"), "w", encoding="utf-8") as f:
        for row in train:
            f.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")

    evals = [{"task": "qgen", "id": r["id"], "resume_text": resume_text(r)} for r in load("qgen_eval_intro.jsonl")]
    # 꼬리 질문은 답변마다 1순위 · 2순위 유형 두 번 (두 번째 꼬리 질문은 다른 유형이라, 2순위도 따르는지 본다)
    evals += [{"task": "followup", "id": f"fu{i}-{t}", "question": pool[i]["question"], "answer": pool[i]["answer"], "fu_type": t}
              for i in FU_EVAL for t in follow_up_types(pool[i]["question"], pool[i]["answer"])[:2]]
    with open(os.path.join(DATA, "qgen_eval_prompts.jsonl"), "w", encoding="utf-8") as f:
        for row in evals:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # 길이 확인 (학습 max_seq_length를 넘으면 뒤가 잘려 정답이 학습되지 않는다)
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("Bllossom/llama-3.2-Korean-Bllossom-3B")
        lens = sorted(len(tok(tok.apply_chat_template(r["messages"], tokenize=False)).input_ids) for r in train)
        print(f"토큰 길이: 중앙 {lens[len(lens) // 2]}, 최대 {lens[-1]}")
    except Exception as e:
        print(f"토큰 길이 확인 건너뜀: {e}")
    print(f"학습 {len(train)}줄 (자기소개서 질문 {len(intros)}×{INTRO_REPEAT}, 꼬리 질문 {len(fus)}) | 평가 입력 {len(evals)}개")


if __name__ == "__main__":
    main()
