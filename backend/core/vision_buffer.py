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
    # 이미 있으면 유지 — 면접 도중 소켓이 재연결돼도 앞서 쌓인 프레임 결과를 지우지 않는다
    # (버퍼는 면접 종료 후 분석 단계의 get_and_clear_vision_scores가 비운다)
    _vision_buffers.setdefault(interview_id, [])


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

    # 시선: 얼굴이 안 보인 프레임도 '정면을 안 봄'으로 센다 / 자세: 몸(어깨)이 잡힌 프레임만
    # (예전엔 어깨가 화면 밖이면 '자세 양호'로 쳐서, 자리를 비워도 자세 100점이 나왔다)
    eye_scores     = [1.0 if f.get("eye_contact") else 0.0 for f in frames]
    posed          = [f for f in frames if f.get("pose_detected", True)]
    posture_scores = [1.0 if f.get("posture_ok") else 0.0 for f in posed]

    return {
        "eye_contact_score": round(sum(eye_scores)     / len(eye_scores)     * 100, 1),
        # 어깨가 한 번도 안 잡혔으면 None → 분석 단계가 자세만 추정값을 쓴다
        "posture_score":     round(sum(posture_scores) / len(posture_scores) * 100, 1) if posture_scores else None,
        "frame_count":       len(frames),
        "face_ratio":        round(sum(1 for f in frames if f.get("face_detected")) / len(frames) * 100, 1),
    }
