import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from core.security import get_current_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stt", tags=["STT"])

MAX_AUDIO_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id),
):
    content = await audio.read()
    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="오디오 파일이 너무 큽니다 (최대 50MB)")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="오디오 파일이 비어 있습니다")

    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            f.write(content)
            tmp_path = f.name

        return {"text": "서버 측 STT(Whisper)가 비활성화되었습니다. 프론트엔드의 Web STT를 사용하세요."}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
