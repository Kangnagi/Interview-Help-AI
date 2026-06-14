import json
import logging
import asyncio
import os
from typing import Dict, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy import select
from jose import JWTError, jwt

from core.config import settings
from core.database import AsyncSessionLocal
from core.vision_buffer import init_buffer, add_frame_result
from services.vision.mediapipe_service import mediapipe_service
from models.interview import Interview, InterviewQuestion, InterviewStatus
from routers.analysis import _run_analysis_pipeline


logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])

# 세션별 오디오 데이터 누적 버퍼
audio_buffers: Dict[int, List[bytes]] = {}

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

# ───────────────────────────────────────────────────────────
# 1) 메인 소켓 (비디오 프레임 분석 및 제어)
# ───────────────────────────────────────────────────────────
@router.websocket("/ws/interview/{interview_id}")
async def interview_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(...)
):
    user_id = _verify_ws_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(interview_id, websocket)
    init_buffer(interview_id)

    try:
        while True:
            message = await websocket.receive()

            if "text" in message:
                data = json.loads(message["text"])
                await manager.send_json(websocket, {"type": "status", "received": data.get("type")})

            elif "bytes" in message:
                frame_bytes = message["bytes"]
                result = mediapipe_service.analyze_frame_sync(frame_bytes)

                # MediaPipe가 실제로 초기화된 경우에만 버퍼에 누적
                # (Stub 모드는 항상 True를 반환하므로 제외)
                if mediapipe_service._initialized:
                    add_frame_result(interview_id, result)

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
    
    # 저장 디렉토리 생성
    upload_dir = settings.UPLOAD_DIR
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

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
    # 저장 파일 경로 설정
    file_name = f"interview_{interview_id}_{int(asyncio.get_event_loop().time())}.webm"
    file_path = os.path.join(settings.UPLOAD_DIR, file_name)

    try:
        # 1. 오디오 파일 물리적 저장
        with open(file_path, "wb") as f:
            f.write(full_audio)
        logger.info(f"[Storage] 면접 {interview_id} 오디오 저장 완료: {file_path}")

        # 2. DB에 오디오 경로 업데이트 및 면접 상태 변경
        async with AsyncSessionLocal() as db:
            # (1) 해당 면접의 질문 레코드를 찾아 오디오 경로 기록
            stmt = select(InterviewQuestion).where(InterviewQuestion.interview_id == interview_id).order_by(InterviewQuestion.order).limit(1)
            result = await db.execute(stmt)
            question_to_update = result.scalar_one_or_none()

            if not question_to_update:
                logger.error(f"[Analysis] 면접 {interview_id}의 답변을 저장할 질문 객체를 찾지 못했습니다.")
                return
            
            # 오디오 경로 저장
            question_to_update.audio_path = file_path

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
        logger.error(f"[Analysis] 사후 분석 중 치명적 오류: {e}")
