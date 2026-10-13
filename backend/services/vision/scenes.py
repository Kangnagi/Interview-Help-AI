"""
감점 장면 사진 저장 · 조회 · 자동 삭제.

- save_scenes:   분석 단계에서 core/vision_buffer.pop_scenes()가 고른 장면을 파일 + DB(interview_scenes)로
- load_scenes:   결과 화면용 — 본인 확인은 호출하는 API가 한다
- delete_for_interview: 면접 기록을 지울 때 같이
- purge_expired: 30일 지난 장면의 사진 파일을 지우고 purged_at 기록 (서버 시작 시 + 6시간마다)

사진 파일 위치: UPLOAD_DIR/scenes/{interview_id}/{scene_id}_{n}.jpg — /uploads는 웹으로 내보내지 않는다 (main.py).
AI 학습 데이터에는 쓰지 않는다.
"""
import asyncio
import base64
import logging
import os
import shutil
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update

from core.config import settings
from core.database import AsyncSessionLocal
from models.scene import InterviewScene

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
PURGE_INTERVAL_SEC = 6 * 3600
SCENE_ROOT = os.path.join(settings.UPLOAD_DIR, "scenes")

REASON_LABELS = {
    "away": "정면을 보지 않음",
    "no_face": "얼굴이 화면을 벗어남",
    "posture": "어깨가 기울어짐",
    "eyes_closed": "눈을 오래 감음",
}


def _dir(interview_id: int) -> str:
    return os.path.join(SCENE_ROOT, str(int(interview_id)))


def _path(interview_id: int, scene_id: int, n: int) -> str:
    return os.path.join(_dir(interview_id), f"{int(scene_id)}_{int(n)}.jpg")


def _remove_dir(interview_id: int) -> None:
    shutil.rmtree(_dir(interview_id), ignore_errors=True)


async def save_scenes(db, interview_id: int, scenes: list) -> int:
    """장면 저장 — 같은 면접을 다시 분석하면 예전 장면을 지우고 새로 쓴다. 저장한 장면 수."""
    await db.execute(delete(InterviewScene).where(InterviewScene.interview_id == interview_id))
    await asyncio.to_thread(_remove_dir, interview_id)
    if not scenes:
        await db.flush()
        return 0
    rows = []
    for rank, s in enumerate(scenes, 1):
        row = InterviewScene(
            interview_id=interview_id, rank=rank, reason=s["reason"], question_order=s.get("question_order"),
            at_sec=s.get("at_sec"), duration_sec=s.get("duration_sec"), eye_score=s.get("eye_score"),
            expression_score=s.get("expression_score"), frame_count=len(s["frames"]),
        )
        db.add(row)
        rows.append((row, s["frames"]))
    await db.flush()      # id 받기

    def write_files():
        os.makedirs(_dir(interview_id), exist_ok=True)
        for row, frames in rows:
            for n, data in enumerate(frames):
                with open(_path(interview_id, row.id, n), "wb") as f:
                    f.write(data)
    await asyncio.to_thread(write_files)
    return len(rows)


def _read_frames(interview_id: int, scene_id: int, count: int) -> list:
    out = []
    for n in range(count):
        try:
            with open(_path(interview_id, scene_id, n), "rb") as f:
                out.append("data:image/jpeg;base64," + base64.b64encode(f.read()).decode("ascii"))
        except OSError:
            continue
    return out


async def load_scenes(db, interview_id: int, created_at: datetime) -> dict:
    """결과 화면용 — {'purged': bool, 'scenes': [...]} (사진은 data URL)."""
    rows = (await db.execute(
        select(InterviewScene).where(InterviewScene.interview_id == interview_id).order_by(InterviewScene.rank)
    )).scalars().all()
    expired = created_at is not None and datetime.utcnow() - created_at > timedelta(days=RETENTION_DAYS)
    if rows and (expired or any(r.purged_at for r in rows)):
        if expired and not all(r.purged_at for r in rows):     # 정리 작업보다 먼저 열어 본 경우 — 여기서 바로 지움
            await asyncio.to_thread(_remove_dir, interview_id)
            await db.execute(update(InterviewScene).where(InterviewScene.interview_id == interview_id)
                             .values(purged_at=datetime.utcnow()))
            await db.commit()
        return {"purged": True, "scenes": []}
    scenes = []
    for r in rows:
        frames = await asyncio.to_thread(_read_frames, interview_id, r.id, r.frame_count)
        if not frames:
            continue
        scenes.append({
            "id": r.id, "rank": r.rank, "reason": r.reason, "label": REASON_LABELS.get(r.reason, r.reason),
            "question_order": r.question_order, "at_sec": r.at_sec, "duration_sec": r.duration_sec,
            "eye_score": r.eye_score, "expression_score": r.expression_score, "frames": frames,
        })
    return {"purged": False, "scenes": scenes}


async def delete_for_interview(db, interview_id: int) -> None:
    await db.execute(delete(InterviewScene).where(InterviewScene.interview_id == interview_id))
    await asyncio.to_thread(_remove_dir, interview_id)


async def purge_expired() -> int:
    """보관 기간(30일)이 지난 장면 사진을 지운다 → 지운 면접 수."""
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(
            select(InterviewScene.interview_id).where(InterviewScene.created_at < cutoff, InterviewScene.purged_at.is_(None))
            .distinct()
        )).scalars().all()
        for iid in ids:
            await asyncio.to_thread(_remove_dir, iid)
        if ids:
            await db.execute(update(InterviewScene).where(InterviewScene.interview_id.in_(ids))
                             .values(purged_at=datetime.utcnow()))
            await db.commit()
    if ids:
        logger.info(f"감점 장면 사진 {len(ids)}개 면접분 삭제 (보관 {RETENTION_DAYS}일 지남)")
    return len(ids)


async def purge_loop() -> None:
    """서버 시작 시 한 번, 이후 6시간마다."""
    while True:
        try:
            await purge_expired()
        except Exception:
            logger.exception("감점 장면 자동 삭제 실패")
        await asyncio.sleep(PURGE_INTERVAL_SEC)
