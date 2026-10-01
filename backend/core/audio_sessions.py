"""
녹음 소켓(/ws/interview_audio)과 분석 파이프라인 사이의 동기화 — 인메모리 (uvicorn 워커 1개 기준).

문제: 화면은 '면접 종료 → 분석 시작 → 결과 화면 이동' 순서로 호출하고, 녹음 소켓은 화면을 떠날 때 닫힌다.
그래서 분석이 녹음 파일 저장보다 먼저 시작돼 음성 없이 분석되고, 소켓이 닫힌 뒤 분석이 한 번 더 돌았다.

해결:
- 녹음 소켓이 열려 있는 면접은 분석 파이프라인이 녹음 저장이 끝날 때까지(최대 AUDIO_WAIT_SECONDS) 기다린다.
- 같은 면접의 분석이 이미 돌고 있으면 두 번째 실행 요청은 건너뛴다.
"""
import asyncio
from typing import Dict, Set

AUDIO_WAIT_SECONDS = 20

_pending: Dict[int, asyncio.Event] = {}   # 녹음 소켓이 열려 있는 면접 → 저장 완료 시 set
_running: Set[int] = set()                # 분석 파이프라인이 돌고 있는 면접


def open_session(interview_id: int) -> None:
    if interview_id not in _pending or _pending[interview_id].is_set():
        _pending[interview_id] = asyncio.Event()


def finalize_session(interview_id: int) -> None:
    """녹음 저장(또는 저장할 것 없음)이 끝났음을 알린다."""
    event = _pending.pop(interview_id, None)
    if event:
        event.set()


async def wait_for_audio(interview_id: int, timeout: float = AUDIO_WAIT_SECONDS) -> bool:
    """녹음 저장 중이면 끝날 때까지 기다린다. 기다릴 녹음이 없거나 저장 완료면 True, 시간 초과면 False."""
    event = _pending.get(interview_id)
    if event is None:
        return True
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        return False


def try_start_analysis(interview_id: int) -> bool:
    """분석을 시작해도 되면 True (이미 돌고 있으면 False)."""
    if interview_id in _running:
        return False
    _running.add(interview_id)
    return True


def end_analysis(interview_id: int) -> None:
    _running.discard(interview_id)


def is_analysis_running(interview_id: int) -> bool:
    return interview_id in _running
