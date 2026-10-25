"""
면접 답변 녹음 파일 보관 (10/26 보안 점검 — 사용자 승인)

- 녹음은 UPLOAD_DIR/interview_{면접 번호}_{시각}.webm (routers/websocket.py process_final_audio_analysis가 저장)
- 30일이 지나면 파일을 지우고 질문의 audio_path를 비운다 (감점 장면 사진과 같은 기간, 서버 시작 시 + 6시간마다)
- 면접 기록을 지우면 그 면접의 녹음도 바로 지운다 (예전엔 기록을 지워도 녹음 파일이 남았다)
- 분석은 면접이 끝나자마자 하므로 30일 뒤 지워도 결과 화면 점수에는 영향이 없다
- 지우는 파일은 UPLOAD_DIR 바로 아래 interview_*.webm 만 (DB에 다른 경로가 들어 있어도 그 밖의 파일은 건드리지 않음)
"""
import asyncio
import logging
import os
import re
import time

from sqlalchemy import select, update

from core.config import settings
from core.database import AsyncSessionLocal
from models.interview import InterviewQuestion

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
PURGE_INTERVAL_SEC = 6 * 3600
_NAME = re.compile(r"interview_\d+_\d+\.webm")


def _upload_dir() -> str:
    return os.path.realpath(settings.UPLOAD_DIR)


def _safe_recording(path: str):
    """우리가 저장한 녹음 파일이면 실제 경로, 아니면 None (UPLOAD_DIR 밖 · 다른 이름은 지우지 않는다)."""
    if not path:
        return None
    real = os.path.realpath(path)
    if os.path.dirname(real) != _upload_dir() or not _NAME.fullmatch(os.path.basename(real)):
        return None
    return real


def _remove(paths) -> int:
    n = 0
    for p in paths:
        try:
            os.remove(p)
            n += 1
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("녹음 파일 삭제 실패: %s", os.path.basename(p))
    return n


async def delete_for_interview(db, interview_id: int) -> None:
    """면접 기록을 지울 때 — 그 면접 질문들이 쓰던 녹음 파일을 지운다 (질문 행은 호출부가 면접과 함께 지움)."""
    paths = (await db.execute(
        select(InterviewQuestion.audio_path).where(InterviewQuestion.interview_id == interview_id,
                                                   InterviewQuestion.audio_path.is_not(None)).distinct()
    )).scalars().all()
    files = {p for p in (_safe_recording(x) for x in paths) if p}
    # 파일 이름의 면접 번호가 같은 녹음도 (질문에 연결되기 전에 끊긴 녹음)
    d = _upload_dir()
    if os.path.isdir(d):
        files |= {os.path.join(d, f) for f in os.listdir(d) if _NAME.fullmatch(f) and f.startswith(f"interview_{interview_id}_")}
    n = await asyncio.to_thread(_remove, files)
    if n:
        logger.info(f"면접 {interview_id} 삭제 — 녹음 {n}개도 삭제")


async def purge_expired() -> int:
    """30일 지난 녹음 파일을 지우고 질문의 audio_path를 비운다 → 지운 파일 수."""
    d = _upload_dir()
    if not os.path.isdir(d):
        return 0
    cutoff = time.time() - RETENTION_DAYS * 86400
    old = [os.path.join(d, f) for f in os.listdir(d)
           if _NAME.fullmatch(f) and os.path.getmtime(os.path.join(d, f)) < cutoff]
    if not old:
        return 0
    n = await asyncio.to_thread(_remove, old)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(InterviewQuestion.id, InterviewQuestion.audio_path)
                                 .where(InterviewQuestion.audio_path.is_not(None)))).all()
        gone = set(old)
        ids = [qid for qid, p in rows if _safe_recording(p) in gone]
        if ids:
            await db.execute(update(InterviewQuestion).where(InterviewQuestion.id.in_(ids))
                             .values(audio_path=None, audio_start_sec=None, audio_end_sec=None))
            await db.commit()
    logger.info(f"녹음 {n}개 삭제 (보관 {RETENTION_DAYS}일 지남), 질문 {len(ids)}개의 녹음 연결 해제")
    return n


async def purge_loop() -> None:
    """서버 시작 시 한 번, 이후 6시간마다."""
    while True:
        try:
            await purge_expired()
        except Exception:
            logger.exception("녹음 자동 삭제 실패")
        await asyncio.sleep(PURGE_INTERVAL_SEC)
