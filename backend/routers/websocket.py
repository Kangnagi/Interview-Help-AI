import json
import logging
import asyncio
import os
import time
from typing import Dict, List, Optional, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from jose import JWTError, jwt

from core import audio_sessions
from core.config import settings
from core.database import AsyncSessionLocal
from core.vision_buffer import init_buffer, add_frame_result
from services.vision.mediapipe_service import mediapipe_service
from models.analysis import Analysis
from models.interview import Interview, InterviewQuestion, InterviewStatus
from routers.analysis import _run_analysis_pipeline


logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

MAX_AUDIO_BYTES = 200 * 1024 * 1024   # 면접 1개 녹음 메모리 상한 (opus 기준 수 시간 분량 — 비정상 전송 방어)
CHUNK_SECONDS = 0.25                  # 화면 MediaRecorder가 조각을 보내는 간격 (첫 조각 도착 시각 보정용)


class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[int, List[WebSocket]] = {}

    async def connect(self, interview_id: int, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(interview_id, []).append(ws)

    def disconnect(self, interview_id: int, ws: WebSocket):
        if interview_id in self._rooms and ws in self._rooms[interview_id]:
            self._rooms[interview_id].remove(ws)
            if not self._rooms[interview_id]:
                del self._rooms[interview_id]

    async def send_json(self, ws: WebSocket, data: dict):
        if ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps(data, ensure_ascii=False))

manager = ConnectionManager()


def _verify_ws_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None


async def _authorize(websocket: WebSocket, interview_id: int, token: str) -> Optional[int]:
    """토큰이 유효하고 그 면접이 본인 것이면 user_id, 아니면 소켓을 닫고 None.

    (예전엔 로그인만 확인해서 남의 면접 번호로 프레임·녹음을 보낼 수 있었다)
    """
    user_id = _verify_ws_token(token)
    if user_id is not None:
        async with AsyncSessionLocal() as db:
            owner = (await db.execute(select(Interview.user_id).where(Interview.id == interview_id))).scalar_one_or_none()
        if owner == user_id:
            return user_id
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return None


# ───────────────────────────────────────────────────────────
# 1) 메인 소켓 (비디오 프레임 분석 및 제어)
# ───────────────────────────────────────────────────────────
@router.websocket("/ws/interview/{interview_id}")
async def interview_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(...)
):
    if await _authorize(websocket, interview_id, token) is None:
        return

    await manager.connect(interview_id, websocket)
    init_buffer(interview_id)   # 이미 있으면 유지 — 면접 중 재연결해도 앞서 쌓인 프레임 결과를 지우지 않음

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            if message.get("text") is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                await manager.send_json(websocket, {"type": "status", "received": data.get("type")})

            elif message.get("bytes") is not None:
                frame_bytes = message["bytes"]
                # analyze_frame_sync는 동기(CPU 바운드) 함수 — 이벤트 루프에서 직접 호출하면
                # 이 프레임 분석이 끝날 때까지 다른 모든 연결(다른 면접자, 일반 API 요청)이
                # 전부 멈춘다. 별도 스레드로 넘겨 이벤트 루프가 계속 다른 요청을 처리하게 한다.
                result = await asyncio.to_thread(mediapipe_service.analyze_frame_sync, frame_bytes)

                # 실제로 분석한 프레임만 누적 — Stub 모드 · 깨진 프레임(face_detected None)은 항상 '양호'라 제외
                if mediapipe_service._initialized and result.get("face_detected") is not None:
                    add_frame_result(interview_id, result)

                await manager.send_json(websocket, {
                    "type": "frame_analysis",
                    "result": result
                })

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(interview_id, websocket)


# ───────────────────────────────────────────────────────────
# 2) 오디오 전용 소켓 (데이터 누적 후 사후 분석)
# ───────────────────────────────────────────────────────────
@router.websocket("/ws/interview_audio/{interview_id}")
async def interview_audio_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(...)
):
    """면접 전체를 하나의 webm 파일로 녹음한다.

    - 바이너리 메시지: MediaRecorder 조각 (250ms 간격)
    - 텍스트 메시지 {"type": "question", "question_id": N}: 지금부터 질문 N의 답변 (질문이 바뀔 때마다 전송)
      → 저장할 때 질문별 시작·끝 시각(audio_start_sec / audio_end_sec)을 기록해, 분석 단계에서 그 구간만 잘라 쓴다.
      (webm은 중간에서 자르면 뒤쪽 조각을 읽을 수 없어 파일을 나누지 않고 시각만 기록한다)
    - 이 메시지를 보내지 않으면 예전처럼 녹음 전체를 첫 번째 질문에 연결한다.
    """
    if await _authorize(websocket, interview_id, token) is None:
        return

    await websocket.accept()
    audio_sessions.open_session(interview_id)
    logger.info(f"[WS-Audio] 면접 {interview_id} 기록 시작")

    chunks: List[bytes] = []
    total_bytes = 0
    started_at: Optional[float] = None          # 녹음 시작 시각 (첫 조각 도착 - 조각 간격)
    markers: List[Tuple[int, float]] = []       # (question_id, 녹음 시작 기준 초)

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                if started_at is None:
                    started_at = time.monotonic() - CHUNK_SECONDS
                if total_bytes + len(message["bytes"]) > MAX_AUDIO_BYTES:
                    logger.warning(f"[WS-Audio] 면접 {interview_id} 녹음이 상한({MAX_AUDIO_BYTES // 2**20}MB)을 넘어 이후 조각은 버림")
                    continue
                chunks.append(message["bytes"])
                total_bytes += len(message["bytes"])
            elif message.get("text") is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "question" and isinstance(data.get("question_id"), int):
                    t = 0.0 if started_at is None else max(0.0, time.monotonic() - started_at)
                    markers.append((data["question_id"], round(t, 2)))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[WS-Audio] 면접 {interview_id} 오디오 수신 중 오류 발생: {e}")
    finally:
        logger.info(f"[WS-Audio] 면접 {interview_id} 종료 — 조각 {len(chunks)}개, {total_bytes / 2**20:.1f}MB, 질문 구간 {len(markers)}개")
        if chunks:
            # 소켓은 이미 닫혔으므로 여기서 저장을 끝까지 기다려도 사용자는 기다리지 않는다.
            # (예전엔 참조 없는 create_task로 띄워, 이벤트 루프 사정에 따라 저장이 중간에 사라질 수 있었다)
            await process_final_audio_analysis(interview_id, b"".join(chunks), markers)
        else:
            audio_sessions.finalize_session(interview_id)


_background_tasks: set = set()   # 실행 중인 백그라운드 분석 — 참조를 잡아 둬야 도중에 사라지지 않는다


async def process_final_audio_analysis(interview_id: int, full_audio: bytes, markers: List[Tuple[int, float]] = ()):
    """녹음을 저장하고 질문별 구간을 기록한다. 분석이 필요하면 한 번만 (백그라운드로) 실행한다."""
    file_name = f"interview_{interview_id}_{int(time.time())}.webm"
    file_path = os.path.join(settings.UPLOAD_DIR, file_name)
    run_pipeline = False

    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(full_audio)
        logger.info(f"[Storage] 면접 {interview_id} 오디오 저장 완료: {file_path}")

        async with AsyncSessionLocal() as db:
            questions = (await db.execute(
                select(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id).order_by(InterviewQuestion.order)
            )).scalars().all()
            by_id = {q.id: q for q in questions}
            valid = [(qid, t) for qid, t in markers if qid in by_id]

            if valid:
                # 같은 질문 표시가 여러 번 오면 마지막 것을 쓴다 (질문을 다시 녹음한 경우)
                last = {}
                for qid, t in valid:
                    last[qid] = t
                ordered = sorted(last.items(), key=lambda x: x[1])
                for i, (qid, start) in enumerate(ordered):
                    q = by_id[qid]
                    q.audio_path = file_path
                    q.audio_start_sec = start
                    q.audio_end_sec = ordered[i + 1][1] if i + 1 < len(ordered) else None
                    db.add(q)
                logger.info(f"[Storage] 면접 {interview_id} 질문별 구간 {len(ordered)}개 기록")
            elif questions:
                # 질문 표시가 없는 예전 방식 — 녹음 전체를 첫 질문에 연결 (질문별 음성 분석은 부정확)
                first = questions[0]
                first.audio_path, first.audio_start_sec, first.audio_end_sec = file_path, None, None
                db.add(first)
                logger.warning(f"[Storage] 면접 {interview_id} 질문 구간 표시 없음 — 녹음 전체를 첫 질문에 연결")
            else:
                logger.error(f"[Analysis] 면접 {interview_id}의 답변을 저장할 질문 객체를 찾지 못했습니다.")

            # 이미 종료(finish)된 면접인데 분석이 돌고 있지 않고, 이 녹음 이후의 분석 결과가 없으면 녹음을 반영해 한 번 분석
            interview = await db.get(Interview, interview_id)
            analysis = (await db.execute(select(Analysis).where(Analysis.interview_id == interview_id))).scalar_one_or_none()
            await db.commit()
            run_pipeline = (
                interview is not None and interview.status == InterviewStatus.COMPLETED
                and not audio_sessions.is_analysis_running(interview_id)
                and (analysis is None or analysis.total_score is None)
            )
    except Exception as e:
        logger.error(f"[Analysis] 녹음 저장 중 오류: {e}")
    finally:
        # 분석 파이프라인이 녹음 저장을 기다리고 있으면 이제 진행하게 한다
        audio_sessions.finalize_session(interview_id)

    if run_pipeline:
        logger.info(f"[Analysis] 면접 {interview_id} 녹음 저장 후 분석 실행 (아직 분석 결과 없음)")
        task = asyncio.create_task(_run_analysis_pipeline(interview_id))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
