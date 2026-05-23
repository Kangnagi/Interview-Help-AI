"""
기존 interview.db에 새 컬럼 추가 마이그레이션.
백엔드 서버 실행 전 한 번만 실행하세요:
    python migrate_db.py
"""
import sqlite3

DB_PATH = "./interview.db"

MIGRATIONS = [
    "ALTER TABLE interviews ADD COLUMN interview_type VARCHAR DEFAULT 'practice'",
    "ALTER TABLE interviews ADD COLUMN resume_ref_id VARCHAR",
]

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(interviews)")
    existing_cols = {row[1] for row in cur.fetchall()}

    for sql in MIGRATIONS:
        col = sql.split("ADD COLUMN ")[1].split(" ")[0]
        if col not in existing_cols:
            cur.execute(sql)
            print(f"Added column: {col}")
        else:
            print(f"Already exists, skip: {col}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run()
