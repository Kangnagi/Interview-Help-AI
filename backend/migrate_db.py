"""
기존 interview.db에 새 컬럼 추가 마이그레이션.
백엔드 서버 실행 전 한 번만 실행하세요:
    python migrate_db.py
"""
import sqlite3

DB_PATH = "./interview.db"

# (테이블명, ALTER TABLE 구문) 목록 — 이미 존재하는 컬럼은 자동으로 건너뜀
MIGRATIONS = [
    ("interviews", "ALTER TABLE interviews ADD COLUMN interview_type VARCHAR DEFAULT 'practice'"),
    ("interviews", "ALTER TABLE interviews ADD COLUMN resume_ref_id VARCHAR"),
    ("users", "ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"),
    ("users", "ALTER TABLE users ADD COLUMN locked_until DATETIME"),
]

def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_cols_by_table = {}

    for table, sql in MIGRATIONS:
        if table not in existing_cols_by_table:
            cur.execute(f"PRAGMA table_info({table})")
            existing_cols_by_table[table] = {row[1] for row in cur.fetchall()}

        col = sql.split("ADD COLUMN ")[1].split(" ")[0]
        if col not in existing_cols_by_table[table]:
            cur.execute(sql)
            existing_cols_by_table[table].add(col)
            print(f"Added column: {table}.{col}")
        else:
            print(f"Already exists, skip: {table}.{col}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    run()
