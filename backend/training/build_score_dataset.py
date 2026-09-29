"""
interview.db에 쌓인 실제 Gemini 채점 결과를, Llama 파인튜닝용 JSONL로 변환한다.

기존 학습 데이터(claude/llama-3-2-finetuning-m8etwt 브랜치의 sample_dataset.jsonl)는
"질문+답변 -> 피드백 텍스트"만 가르쳤다. 이번엔 assistant 응답을
{"score":0~100,"feedback":"...","tip":"..."} JSON으로 바꿔서,
점수까지 같은 모델이 산정하도록 확장한다 (gemini_service.analyze_answer_with_gemini의
프롬프트/출력 형식과 동일하게 맞춰 기존 백엔드 파싱 코드를 그대로 재사용 가능하게 함).

실행:
    cd backend
    .venv\\Scripts\\python.exe training\\build_score_dataset.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "interview.db"
OUT_PATH = Path(__file__).resolve().parent / "data" / "score_dataset_from_db.jsonl"

SYSTEM_PROMPT = (
    "당신은 10년 차 전문 인사담당자이자 AI 면접관입니다.\n"
    "지원자의 면접 질문과 답변을 분석하여 반드시 아래 JSON 형식으로만 응답하세요 (코드블록 금지):\n"
    '{"score":0~100,"feedback":"1. 잘한 점\\n2. 아쉬운 점 및 개선 방향\\n3. 모범 답변 방향성 제안",'
    '"tip":"다음 답변을 위한 실질적 개선 팁 한 문장"}'
)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT question_text, answer_text, ai_score, ai_feedback
        FROM interview_questions
        WHERE answer_text IS NOT NULL AND answer_text != ''
          AND ai_score IS NOT NULL
          AND ai_feedback IS NOT NULL AND ai_feedback != ''
        """
    )
    rows = cur.fetchall()
    conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    written = skipped = 0
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            feedback = row["ai_feedback"]
            # 실제 Gemini 평가가 아니라 코드의 fallback/placeholder 문구인 항목은 학습에서 제외
            if "답변이 저장되었습니다" in feedback or len(feedback) < 15:
                skipped += 1
                continue

            assistant_json = {
                "score": int(row["ai_score"]),
                "feedback": row["ai_feedback"],
                "tip": "",  # 기존 DB에는 tip이 별도 컬럼으로 저장되어 있지 않아 비워둠
            }
            example = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"면접 질문: {row['question_text']}\n지원자 답변: {row['answer_text']}",
                    },
                    {"role": "assistant", "content": json.dumps(assistant_json, ensure_ascii=False)},
                ]
            }
            f.write(json.dumps(example, ensure_ascii=False) + "\n")
            written += 1

    print(f"{written}개 예시를 {OUT_PATH} 에 저장했습니다. (placeholder {skipped}개 제외)")


if __name__ == "__main__":
    main()
