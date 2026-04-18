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
from typing import Dict, List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import JWTError, jwt

from core.config import settings
from services.vision.mediapipe_service import mediapipe_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


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
        await ws.send_text(json.dumps(data, ensure_ascii=False))


manager = ConnectionManager()


# ───────────────────────────────────────────────────────────
# JWT 검증 — WebSocket은 헤더 대신 쿼리스트링으로 토큰 전달
# ───────────────────────────────────────────────────────────
def _verify_ws_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except JWTError:
        return None


# ───────────────────────────────────────────────────────────
# 메인 엔드포인트
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
                    "result": result,
                })

    except WebSocketDisconnect:
        manager.disconnect(interview_id, websocket)
    except Exception as e:
        logger.exception(f"[WS] 예외 발생: {e}")
        manager.disconnect(interview_id, websocket)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
