"""
실시간 면접 WebSocket 라우터
경로: /ws/interview/{interview_id}?token=<JWT>

프론트는 아래 두 가지 메시지를 주로 보냄:
1) 제어 메시지 (JSON text):  {"type": "start"|"stop"|"status"}
2) 비디오 프레임 (binary):   OpenCV/MediaPipe가 디코딩할 JPEG/PNG bytes

서버는 프레임 1장당 MediaPipe sync 분석 결과를 JSON으로 즉시 회신.
"""
import json
import logging
import asyncio
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from jose import JWTError, jwt

from core.config import settings
from core.database import AsyncSessionLocal
from services.vision.mediapipe_service import mediapipe_service
from services.voice.whisper_service import whisper_service
from models.interview import Interview, InterviewQuestion, InterviewStatus
from routers.analysis import _run_analysis_pipeline


logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# 세션별 오디오 데이터 누적 버퍼
audio_buffers: Dict[int, List[bytes]] = {}

# ───────────────────────────────────────────────────────────
# 연결 매니저 — interview_id 기준으로 소켓 묶어서 관리
# ───────────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self._rooms: Dict[int, List[WebSocket]] = {}

    async def connect(self, interview_id: int, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(interview_id, []).append(ws)
        logger.info(f"[WS] interview={interview_id} 연결 ({len(self._rooms[interview_id])}명)")

    def disconnect(self, interview_id: int, ws: WebSocket):
        if interview_id in self._rooms and ws in self._rooms[interview_id]:
            self._rooms[interview_id].remove(ws)
            if not self._rooms[interview_id]:
                del self._rooms[interview_id]
        logger.info(f"[WS] interview={interview_id} 해제")

    async def send_json(self, ws: WebSocket, data: dict):
        if ws.client_state.name == "CONNECTED":
            await ws.send_text(json.dumps(data, ensure_ascii=False))

manager = ConnectionManager()


# ───────────────────────────────────────────────────────────
# JWT 검증 — WebSocket은 헤더 대신 쿼리스트링으로 토큰 전달
# ───────────────────────────────────────────────────────────
def _verify_ws_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None


# ───────────────────────────────────────────────────────────
# 1) 메인 소켓 (비디오 프레임 분석 및 제어)
# ───────────────────────────────────────────────────────────
@router.websocket("/ws/interview/{interview_id}")
async def interview_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(..., description="JWT 액세스 토큰"),
):
    # 1) 인증
    user_id = _verify_ws_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 2) 연결 수락
    await manager.connect(interview_id, websocket)
    await manager.send_json(websocket, {
        "type": "connected",
        "interview_id": interview_id,
        "user_id": user_id,
    })

    try:
        while True:
            # 텍스트(JSON 제어) 또는 바이너리(프레임) 모두 받을 수 있도록 수신
            message = await websocket.receive()

            # ── 텍스트 제어 메시지 ──────────────────────
            if "text" in message and message["text"] is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    await manager.send_json(websocket, {"type": "error", "detail": "invalid JSON"})
                    continue

                msg_type = data.get("type")
                if msg_type == "start":
                    await manager.send_json(websocket, {"type": "status", "state": "recording"})
                elif msg_type == "stop":
                    await manager.send_json(websocket, {"type": "status", "state": "stopped"})
                elif msg_type == "ping":
                    await manager.send_json(websocket, {"type": "pong"})
                else:
                    await manager.send_json(websocket, {"type": "echo", "payload": data})

            # ── 바이너리 프레임 ────────────────────────
            elif "bytes" in message and message["bytes"] is not None:
                frame_bytes: bytes = message["bytes"]
                # MediaPipe sync 분석 (현재 Stub)
                result = mediapipe_service.analyze_frame_sync(frame_bytes)
                await manager.send_json(websocket, {
                    "type": "frame_analysis",
                    "result": result
                })

    except WebSocketDisconnect:
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
    user_id = _verify_ws_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    audio_buffers[interview_id] = [] # 버퍼 초기화
    logger.info(f"[WS-Audio] 면접 {interview_id} 기록 시작")

    try:
        while True:
            # 프론트에서 250ms마다 보내는 chunk 수신
            audio_chunk = await websocket.receive_bytes()
            audio_buffers[interview_id].append(audio_chunk)

    except WebSocketDisconnect:
        logger.info(f"[WS-Audio] 면접 {interview_id} 정상 종료")
    except Exception as e:
        logger.error(f"[WS-Audio] 면접 {interview_id} 오디오 수신 중 오류 발생: {e}")
    finally:
        logger.info(f"[WS-Audio] 면접 {interview_id} 최종 분석 착수")
        if interview_id in audio_buffers:
            if audio_buffers[interview_id]:
                full_audio = b"".join(audio_buffers[interview_id])
                # 백그라운드 태스크로 분석 실행
                asyncio.create_task(process_final_audio_analysis(interview_id, full_audio))
            del audio_buffers[interview_id]

async def process_final_audio_analysis(interview_id: int, full_audio: bytes):
    """모든 오디오 데이터가 모인 후 수행되는 작업"""
    try:
        # 1. STT (Whisper)
        stt_result = await whisper_service.transcribe_bytes(full_audio)
        stt_text = stt_result.get("text")

        if not stt_text:
            logger.warning(f"[Analysis] 면접 {interview_id}에서 음성을 텍스트로 변환하지 못했습니다. (원인: {stt_result.get('error', '알 수 없음')})")

        # 2. 변환된 텍스트를 DB에 저장하고, 면접 상태를 '완료'로 변경
        # 참고: 현재 구조는 모든 질문의 답변을 하나의 오디오로 받습니다.
        # 따라서 임시로 첫 번째 질문에 모든 답변 내용을 저장합니다.
        async with AsyncSessionLocal() as db:
            # (1) 답변 텍스트 저장
            stmt = select(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id).order_by(InterviewQuestion.order).limit(1)
            result = await db.execute(stmt)
            question_to_update = result.scalar_one_or_none()

            if not question_to_update:
                logger.error(f"[Analysis] 면접 {interview_id}의 답변을 저장할 질문 객체를 찾지 못했습니다.")
                return
            
            # 사용자가 직접 타이핑한 텍스트가 없고, STT 텍스트가 있을 때만 덮어쓰기
            if stt_text:
                question_to_update.answer_text = stt_text
            elif not question_to_update.answer_text:
                # 음성 인식도 실패하고 타이핑된 텍스트도 없을 경우 임시 텍스트 삽입
                question_to_update.answer_text = "음성 인식을 실패하여 임시 텍스트로 대체합니다. 저는 백엔드 개발자로서 훌륭한 역량과 경험을 가지고 있습니다."

            db.add(question_to_update)

            # (2) 면접 상태를 'COMPLETED'로 변경
            interview_stmt = select(Interview).where(Interview.id == interview_id)
            interview_result = await db.execute(interview_stmt)
            interview_to_update = interview_result.scalar_one_or_none()
            if interview_to_update:
                interview_to_update.status = InterviewStatus.COMPLETED
                db.add(interview_to_update)
            
            await db.commit()
            logger.info(f"[DB] 면접 {interview_id}의 답변 텍스트 저장 및 상태 'COMPLETED'로 변경 완료.")

        # 3. 전체 분석 파이프라인 자동 실행
        await _run_analysis_pipeline(interview_id)

    except Exception as e:
        logger.error(f"[Analysis] 사후 분석 중 치명적 오류: {e}")
