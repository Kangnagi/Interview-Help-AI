import json
import logging
import asyncio
from typing import Dict, List

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    status,
)

from sqlalchemy import select
from jose import JWTError, jwt

from core.config import settings
from core.database import AsyncSessionLocal

from services.vision.mediapipe_service import mediapipe_service
from services.voice.whisper_service import whisper_service

from models.interview import (
    Interview,
    InterviewQuestion,
    InterviewStatus,
)

from routers.analysis import _run_analysis_pipeline


logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


# ============================================================
# 오디오 데이터 버퍼
# ============================================================

audio_buffers: Dict[int, List[bytes]] = {}


# ============================================================
# WebSocket 연결 관리자
# ============================================================

class ConnectionManager:

    def __init__(self):
        self._rooms: Dict[int, List[WebSocket]] = {}

    async def connect(
        self,
        interview_id: int,
        ws: WebSocket,
    ):
        await ws.accept()

        self._rooms.setdefault(
            interview_id,
            [],
        ).append(ws)

        logger.info(
            f"[WS] 면접 {interview_id} WebSocket 연결 완료"
        )

    def disconnect(
        self,
        interview_id: int,
        ws: WebSocket,
    ):
        if (
            interview_id in self._rooms
            and ws in self._rooms[interview_id]
        ):
            self._rooms[interview_id].remove(ws)

            if not self._rooms[interview_id]:
                del self._rooms[interview_id]

        logger.info(
            f"[WS] 면접 {interview_id} WebSocket 연결 정리"
        )

    async def send_json(
        self,
        ws: WebSocket,
        data: dict,
    ):
        try:
            if ws.client_state.name == "CONNECTED":
                await ws.send_text(
                    json.dumps(
                        data,
                        ensure_ascii=False,
                    )
                )

        except Exception as e:
            logger.error(
                f"[WS] JSON 전송 실패: {e}",
                exc_info=True,
            )


manager = ConnectionManager()


# ============================================================
# JWT 인증
# ============================================================

def _verify_ws_token(
    token: str,
) -> int | None:

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        return int(
            payload.get("sub")
        )

    except (
        JWTError,
        ValueError,
        TypeError,
    ):
        return None


# ============================================================
# 1. 메인 WebSocket
#
# 웹캠
#   ↓
# JPEG 프레임
#   ↓
# FastAPI
#   ↓
# MediaPipe
#   ↓
# 분석 결과
#   ↓
# React
# ============================================================

@router.websocket(
    "/ws/interview/{interview_id}"
)
async def interview_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(...),
):

    # --------------------------------------------------------
    # JWT 확인
    # --------------------------------------------------------

    user_id = _verify_ws_token(token)

    if user_id is None:

        logger.warning(
            f"[WS] 잘못된 JWT - 면접 {interview_id}"
        )

        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION
        )

        return

    logger.info(
        f"[WS] 면접 WebSocket 연결 요청 "
        f"interview_id={interview_id}, "
        f"user_id={user_id}"
    )

    # --------------------------------------------------------
    # 연결
    # --------------------------------------------------------

    await manager.connect(
        interview_id,
        websocket,
    )

    try:

        # ====================================================
        # WebSocket 메시지 계속 수신
        # ====================================================

        while True:

            message = await websocket.receive()

            # ------------------------------------------------
            # 연결 종료 메시지
            # ------------------------------------------------

            if message.get("type") == "websocket.disconnect":

                logger.info(
                    f"[WS] 클라이언트 연결 종료 "
                    f"interview_id={interview_id}"
                )

                break

            # =================================================
            # TEXT 메시지
            # =================================================

            text_data = message.get("text")

            if text_data is not None:

                try:

                    data = json.loads(
                        text_data
                    )

                except json.JSONDecodeError as e:

                    logger.warning(
                        f"[WS] 잘못된 JSON 메시지: {e}"
                    )

                    await manager.send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": "잘못된 JSON 형식입니다.",
                        },
                    )

                    continue

                message_type = data.get(
                    "type"
                )

                logger.info(
                    f"[WS] TEXT 수신: "
                    f"{message_type}"
                )

                # --------------------------------------------
                # 면접 시작
                # --------------------------------------------

                if message_type == "start":

                    await manager.send_json(
                        websocket,
                        {
                            "type": "status",
                            "received": "start",
                        },
                    )

                    logger.info(
                        f"[WS] 면접 {interview_id} "
                        f"실시간 얼굴 분석 시작"
                    )

                # --------------------------------------------
                # 면접 종료
                # --------------------------------------------

                elif message_type == "stop":

                    await manager.send_json(
                        websocket,
                        {
                            "type": "status",
                            "received": "stop",
                        },
                    )

                    logger.info(
                        f"[WS] 면접 {interview_id} "
                        f"실시간 분석 종료 요청"
                    )

                    break

                else:

                    await manager.send_json(
                        websocket,
                        {
                            "type": "status",
                            "received": message_type,
                        },
                    )

                continue

            # =================================================
            # BINARY 메시지
            #
            # 프론트에서 JPEG 이미지가 들어오는 부분
            # =================================================

            frame_bytes = message.get(
                "bytes"
            )

            if frame_bytes is not None:

                logger.debug(
                    f"[WS] 영상 프레임 수신: "
                    f"{len(frame_bytes)} bytes"
                )

                # --------------------------------------------
                # 빈 프레임 방지
                # --------------------------------------------

                if len(frame_bytes) == 0:

                    logger.warning(
                        "[WS] 빈 영상 프레임 수신"
                    )

                    continue

                # =================================================
                # MediaPipe 분석
                #
                # 중요:
                #
                # analyze_frame_sync()가 CPU 작업이므로
                # 이벤트 루프를 막지 않도록 별도 스레드에서 실행
                # =================================================

                try:

                    result = await asyncio.to_thread(
                        mediapipe_service.analyze_landmarks,
                        frame_bytes,
                    )

                    logger.info(
                        "[MediaPipe] 얼굴 분석 완료: "
                        f"{result}"
                    )

                except Exception as e:

                    logger.error(
                        "[MediaPipe] 얼굴 분석 실패: "
                        f"{e}",
                        exc_info=True,
                    )

                    # 프론트가 분석 실패 상태를 알 수 있도록
                    # 에러 메시지를 전달
                    await manager.send_json(
                        websocket,
                        {
                            "type": "frame_analysis",
                            "result": {
                                "face_detected": False,
                                "landmark_detected": False,
                                "landmark_count": 0,
                                "blink_score": 0,
                                "expression_score": 0,
                                "eye_contact_score": 0,
                                "error": str(e),
                            },
                        },
                    )

                    continue

                # =================================================
                # 분석 결과 확인
                # =================================================

                if result is None:

                    logger.warning(
                        "[MediaPipe] 분석 결과가 None입니다."
                    )

                    result = {
                        "face_detected": False,
                        "landmark_detected": False,
                        "landmark_count": 0,
                        "blink_score": 0,
                        "expression_score": 0,
                        "eye_contact_score": 0,
                    }

                # =================================================
                # React로 분석 결과 전송
                # =================================================

                await manager.send_json(
                    websocket,
                    {
                        "type": "frame_analysis",
                        "result": result,
                    },
                )

                logger.debug(
                    "[WS] MediaPipe 분석 결과 전송 완료"
                )

                continue

    except WebSocketDisconnect:

        logger.info(
            f"[WS] 정상 연결 종료 "
            f"interview_id={interview_id}"
        )

    except Exception as e:

        logger.error(
            f"[WS] WebSocket 처리 중 오류: {e}",
            exc_info=True,
        )

    finally:

        manager.disconnect(
            interview_id,
            websocket,
        )

        logger.info(
            f"[WS] 면접 {interview_id} "
            f"WebSocket 종료 처리 완료"
        )


# ============================================================
# 2. 오디오 전용 WebSocket
# ============================================================

@router.websocket(
    "/ws/interview_audio/{interview_id}"
)
async def interview_audio_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(...),
):

    user_id = _verify_ws_token(token)

    if user_id is None:

        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION
        )

        return

    await websocket.accept()

    audio_buffers[interview_id] = []

    logger.info(
        f"[WS-Audio] 면접 {interview_id} "
        f"기록 시작"
    )

    try:

        while True:

            audio_chunk = (
                await websocket.receive_bytes()
            )

            audio_buffers[
                interview_id
            ].append(
                audio_chunk
            )

    except WebSocketDisconnect:

        logger.info(
            f"[WS-Audio] 면접 {interview_id} "
            f"정상 종료"
        )

    except Exception as e:

        logger.error(
            f"[WS-Audio] 면접 {interview_id} "
            f"오디오 수신 중 오류: {e}",
            exc_info=True,
        )

    finally:

        logger.info(
            f"[WS-Audio] 면접 {interview_id} "
            f"최종 분석 착수"
        )

        if interview_id in audio_buffers:

            if audio_buffers[
                interview_id
            ]:

                full_audio = b"".join(
                    audio_buffers[
                        interview_id
                    ]
                )

                asyncio.create_task(
                    process_final_audio_analysis(
                        interview_id,
                        full_audio,
                    )
                )

            del audio_buffers[
                interview_id
            ]


# ============================================================
# 최종 음성 분석
# ============================================================

async def process_final_audio_analysis(
    interview_id: int,
    full_audio: bytes,
):

    try:

        # ====================================================
        # 1. STT
        # ====================================================

        stt_result = (
            await whisper_service.transcribe_bytes(
                full_audio
            )
        )

        stt_text = stt_result.get(
            "text"
        )

        if not stt_text:

            logger.warning(
                f"[Analysis] 면접 {interview_id} "
                f"음성을 텍스트로 변환하지 못했습니다. "
                f"(원인: "
                f"{stt_result.get('error', '알 수 없음')})"
            )

        # ====================================================
        # 2. DB 저장
        # ====================================================

        async with AsyncSessionLocal() as db:

            stmt = (
                select(InterviewQuestion)
                .where(
                    InterviewQuestion.interview_id
                    == interview_id
                )
                .order_by(
                    InterviewQuestion.order
                )
                .limit(1)
            )

            result = await db.execute(
                stmt
            )

            question_to_update = (
                result.scalar_one_or_none()
            )

            if not question_to_update:

                logger.error(
                    f"[Analysis] 면접 {interview_id} "
                    f"질문 객체를 찾지 못했습니다."
                )

                return

            # ------------------------------------------------
            # STT 결과 저장
            # ------------------------------------------------

            if stt_text:

                question_to_update.answer_text = (
                    stt_text
                )

            elif not question_to_update.answer_text:

                question_to_update.answer_text = (
                    "음성 인식을 실패하여 임시 텍스트로 "
                    "대체합니다. 저는 백엔드 개발자로서 "
                    "훌륭한 역량과 경험을 가지고 있습니다."
                )

            db.add(
                question_to_update
            )

            # ------------------------------------------------
            # 면접 상태 변경
            # ------------------------------------------------

            interview_stmt = (
                select(Interview)
                .where(
                    Interview.id
                    == interview_id
                )
            )

            interview_result = (
                await db.execute(
                    interview_stmt
                )
            )

            interview_to_update = (
                interview_result.scalar_one_or_none()
            )

            if interview_to_update:

                interview_to_update.status = (
                    InterviewStatus.COMPLETED
                )

                db.add(
                    interview_to_update
                )

            await db.commit()

            logger.info(
                f"[DB] 면접 {interview_id} "
                f"답변 텍스트 저장 및 "
                f"COMPLETED 변경 완료"
            )

        # ====================================================
        # 3. 전체 분석
        # ====================================================

        await _run_analysis_pipeline(
            interview_id
        )

    except Exception as e:

        logger.error(
            f"[Analysis] 사후 분석 중 치명적 오류: "
            f"{e}",
            exc_info=True,
        )