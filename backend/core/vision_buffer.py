"""
MediaPipe 실시간 프레임 분석 결과 인메모리 버퍼

WebSocket에서 프레임별로 누적한 eye_contact / posture_ok 결과를
면접 종료 후 분석 파이프라인이 꺼내 DB에 저장할 수 있도록 중계한다.

websocket.py → add_frame_result()
analysis.py  → get_and_clear_vision_scores()
"""
from typing import Dict, List, Optional

_vision_buffers: Dict[int, List[dict]] = {}


def init_buffer(interview_id: int) -> None:
    _vision_buffers[interview_id] = []


def add_frame_result(interview_id: int, result: dict) -> None:
    if interview_id in _vision_buffers:
        _vision_buffers[interview_id].append(result)


def get_and_clear_vision_scores(interview_id: int) -> Optional[dict]:
    """
    버퍼에 누적된 프레임 결과를 집계하고 버퍼를 삭제한다.
    데이터가 없으면 None을 반환해 호출 측이 폴백 로직을 쓰도록 한다.
    """
    frames = _vision_buffers.pop(interview_id, [])
    if not frames:
        return None

    eye_scores     = [1.0 if f.get("eye_contact") else 0.0 for f in frames]
    posture_scores = [1.0 if f.get("posture_ok")  else 0.0 for f in frames]

    return {
        "eye_contact_score": round(sum(eye_scores)     / len(eye_scores)     * 100, 1),
        "posture_score":     round(sum(posture_scores) / len(posture_scores) * 100, 1),
        "frame_count":       len(frames),
    }
