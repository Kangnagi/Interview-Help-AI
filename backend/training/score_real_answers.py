"""
DB의 실제 사용자 답변을 현재 서비스와 똑같은 경로(llama_service.score_answers)로 채점해 검증용 파일을 만든다.
DB는 읽기 전용으로 열고, 결과는 개인정보라 .gitignore 된 data/ 아래에만 저장한다.

- data/real_answers_scored.jsonl : 전체 결과 (문서·통계 생성용)
- data/real_answers_scored.csv   : 엑셀에서 바로 여는 검토표 (UTF-8 BOM)

실행:
    cd backend
    .venv\\Scripts\\python.exe training\\score_real_answers.py          (.env의 어댑터로 채점)
    다른 어댑터로 채점: 환경변수 LLAMA_SCORE_ADAPTER_PATH 지정 + 접미사 인자 (예: _v2)
"""
import asyncio
import csv
import json
import sqlite3
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from services.llm.llama_service import llama_service, score_answers  # noqa: E402

DB_PATH = BACKEND / "interview.db"
OUT_DIR = Path(__file__).resolve().parent / "data"
PLACEHOLDER = "답변이 저장되었습니다"   # Gemini 한도 초과 시 저장된 임시 피드백


def load_rows():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT q.id, q.interview_id, q.question_text, q.answer_text, q.ai_score, q.ai_feedback
        FROM interview_questions q
        WHERE q.answer_text IS NOT NULL AND trim(q.answer_text) != ''
        ORDER BY q.interview_id, q."order"
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def main():
    # 결과 파일 이름 접미사 (예: _v2) — 다른 어댑터로 채점한 결과를 나란히 비교할 때 사용
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    rows = load_rows()
    print(f"채점 대상 {len(rows)}개", flush=True)
    await llama_service.load_model()
    if not llama_service.has_score_adapter:
        raise SystemExit("채점 어댑터가 로드되지 않았습니다.")

    t = time.time()
    results = await score_answers([{"question": r["question_text"], "answer": r["answer_text"]} for r in rows])
    elapsed = time.time() - t
    print(f"채점 완료 {elapsed:.1f}s (답변당 {elapsed / len(rows):.2f}s)", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for r, res in zip(rows, results):
        fb = r["ai_feedback"] or ""
        out.append({
            "id": r["id"], "interview_id": r["interview_id"],
            "question": r["question_text"], "answer": r["answer_text"],
            "old_score": r["ai_score"],
            "old_is_placeholder": (PLACEHOLDER in fb) or len(fb) < 15,
            "old_feedback": fb,
            "new_score": res["score"], "new_feedback": res["feedback"], "new_tip": res["tip"],
        })

    with open(OUT_DIR / f"real_answers_scored{suffix}.jsonl", "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    with open(OUT_DIR / f"real_answers_scored{suffix}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["번호", "질문", "답변", "답변 길이", "기존 점수", "기존 점수 종류", "새 점수",
                    "새 피드백", "새 팁", "검토(적절/너무 높음/너무 낮음)", "메모"])
        for i, o in enumerate(out, 1):
            w.writerow([i, o["question"], o["answer"], len(o["answer"]), o["old_score"],
                        "임시값(한도 초과)" if o["old_is_placeholder"] else "Gemini 채점",
                        o["new_score"], o["new_feedback"], o["new_tip"], "", ""])

    # 요약 통계
    news = [o["new_score"] for o in out]
    print(f"새 점수 분포: 평균 {sum(news) / len(news):.1f}, 범위 {min(news)}~{max(news)}")
    buckets = {"0~29": 0, "30~49": 0, "50~69": 0, "70~84": 0, "85~100": 0}
    for s in news:
        k = "0~29" if s < 30 else "30~49" if s < 50 else "50~69" if s < 70 else "70~84" if s < 85 else "85~100"
        buckets[k] += 1
    print("구간별:", buckets)
    real = [o for o in out if not o["old_is_placeholder"] and o["old_score"] is not None]
    if real:
        diffs = [abs(o["new_score"] - o["old_score"]) for o in real]
        print(f"Gemini가 실제로 채점한 {len(real)}개와 비교: 평균 차이 {sum(diffs) / len(diffs):.1f}점, "
              f"10점 이내 {sum(d <= 10 for d in diffs)}개")
    print(f"저장: {OUT_DIR / f'real_answers_scored{suffix}.csv'}")


if __name__ == "__main__":
    asyncio.run(main())
