"""
회원 탈퇴 — 계정에 딸린 기록을 모두 지우고, 계정 행은 개인정보를 비운 채 비활성으로 남긴다.

지우는 것
- 면접(질문 · 답변 · 분석 결과 · 답변 평가 · 관리자 검토) + 녹음 파일 + 감점 장면 사진
- 자기소개서(이력서 · 채용공고 포함)
- 이 사용자가 남긴 답변 평가

계정 행을 지우지 않고 비우는 이유
- SQLite는 가장 큰 번호의 행을 지우면 그 번호를 다음 가입자에게 다시 줄 수 있다 → 탈퇴 전 발급된 토큰(최대 60분)이
  새 가입자의 계정으로 통하게 된다. 번호를 남겨 두면 그런 일이 없다.
- 남는 것은 번호 · 가입 시각뿐이고 이메일 · 이름 · 비밀번호는 알아볼 수 없는 값으로 바뀐다 (같은 이메일로 다시 가입 가능).
"""
import logging
import secrets
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from models.analysis import Analysis
from models.feedback import AnswerRating
from models.interview import Interview
from models.resume import Resume
from models.user import User
from services.vision import scenes as scene_store
from services.voice import recordings

logger = logging.getLogger(__name__)


async def withdraw_user(db: AsyncSession, user: User) -> dict:
    """탈퇴 처리 (commit은 호출부의 get_db가 한다) → 지운 개수."""
    interviews = (await db.execute(select(Interview).where(Interview.user_id == user.id))).scalars().all()
    for iv in interviews:
        await db.execute(delete(Analysis).where(Analysis.interview_id == iv.id))
        await scene_store.delete_for_interview(db, iv.id)     # 감점 장면 사진 (파일 + 기록)
        await recordings.delete_for_interview(db, iv.id)      # 녹음 파일 (질문 행이 남아 있을 때 불러야 경로를 안다)
        await db.delete(iv)                                    # 질문 → 답변 평가 · 관리자 검토까지 함께 (ORM cascade)

    await db.execute(delete(AnswerRating).where(AnswerRating.user_id == user.id))
    n_resumes = len((await db.execute(select(Resume.id).where(Resume.user_id == user.id))).all())
    await db.execute(delete(Resume).where(Resume.user_id == user.id))

    user.email = f"withdrawn-{user.id}-{secrets.token_hex(4)}@deleted.invalid"
    user.username = "탈퇴한 사용자"
    user.hashed_password = hash_password(secrets.token_urlsafe(32))   # 아무도 모르는 비밀번호 → 로그인 불가
    user.is_active = False
    user.training_consent = None
    user.training_consent_at = None
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    user.updated_at = datetime.utcnow()
    await db.flush()

    logger.info(f"회원 탈퇴: user {user.id} — 면접 {len(interviews)}개, 자기소개서 {n_resumes}개 삭제")
    return {"interviews": len(interviews), "resumes": n_resumes}
