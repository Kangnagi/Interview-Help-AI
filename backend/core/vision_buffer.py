"""
MediaPipe 실시간 프레임 분석 결과 인메모리 버퍼

WebSocket에서 프레임별로 누적한 eye_contact / posture_ok 결과를
면접 종료 후 분석 파이프라인이 꺼내 DB에 저장할 수 있도록 중계한다.

websocket.py → add_frame_result() · add_scene_frame() · set_scene_keep() · set_scene_question()
analysis.py  → get_and_clear_vision_scores() · pop_scenes() (→ services/vision/scenes.py가 파일로 저장)
"""
import time
from collections import deque
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

    # 시선: 프레임별 눈맞춤 점수(눈동자 위치, 0~100 — 화면 '실시간 분석'과 같은 값)의 평균. 얼굴이 안 보인 프레임은 0점.
    #       (점수가 없는 예전 결과는 정면 여부로 1 · 0)
    # 자세: 몸(어깨)이 잡힌 프레임만 (예전엔 어깨가 화면 밖이면 '자세 양호'로 쳐서, 자리를 비워도 자세 100점이 나왔다)
    eye_scores = [f["eye_contact_score"] / 100.0 if f.get("eye_contact_score") is not None
                  else (1.0 if f.get("eye_contact") else 0.0) for f in frames]
    posed          = [f for f in frames if f.get("pose_detected", True)]
    posture_scores = [1.0 if f.get("posture_ok") else 0.0 for f in posed]

    return {
        "eye_contact_score": round(sum(eye_scores)     / len(eye_scores)     * 100, 1),
        # 어깨가 한 번도 안 잡혔으면 None → 분석 단계가 자세만 추정값을 쓴다
        "posture_score":     round(sum(posture_scores) / len(posture_scores) * 100, 1) if posture_scores else None,
        "frame_count":       len(frames),
        "face_ratio":        round(sum(1 for f in frames if f.get("face_detected")) / len(frames) * 100, 1),
    }


# ── 감점 장면 (분석 결과 화면의 움직이는 이미지) ─────────────────────────────────────
# 프레임마다 감점 기준에 걸리는지 보고, 1초(2장) 이상 이어지면 그 앞 2장 + 걸린 동안(최대 6장)의 사진을 장면 후보로 남긴다.
# 사진은 메모리에만 두고, 분석 단계(services/vision/scenes.py)가 상위 몇 장면만 파일로 저장한다.
SCENE_PRE_FRAMES = 2        # 감점 시작 전 사진 수 (어떻게 그 자세가 됐는지 보이게)
SCENE_MAX_STREAK = 6        # 한 장면에 담는 감점 사진 최대 수 (2fps → 3초)
SCENE_MIN_STREAK = 2        # 1초(2장) 이상 이어진 것만 — 한 번 깜빡임 · 순간 흔들림은 감점 장면이 아님
SCENE_MAX_CANDIDATES = 12   # 면접 하나에 메모리에 두는 후보 수 (12 × 8장 × 약 15KB ≈ 1.4MB)
SCENE_MAX_FRAME_BYTES = 200 * 1024
_SCENE_WEIGHT = {"no_face": 1.2, "away": 1.0, "posture": 0.8, "eyes_closed": 0.7}

_scene_state: Dict[int, dict] = {}


def scene_reason(r: dict) -> Optional[str]:
    """이 프레임이 감점 기준에 걸리면 이유 — 분석 결과에서 깎이는 시선 · 자세와 같은 기준."""
    if r.get("face_detected") is False:
        return "no_face"
    eye = r.get("eye_contact_score")
    if eye is not None and eye < 40:
        return "away"
    if r.get("eyes_closed"):
        return "eyes_closed"
    if r.get("pose_detected") and r.get("posture_ok") is False:
        return "posture"
    return None


def _state(interview_id: int) -> dict:
    return _scene_state.setdefault(interview_id, {
        "keep": True, "t0": time.monotonic(), "q": None,
        "recent": deque(maxlen=SCENE_PRE_FRAMES), "streak": [], "scenes": [],
        "hold": False,      # 긴 감점이 한 장면 길이를 넘기면, 바른 자세로 돌아올 때까지 새 장면을 만들지 않음 (같은 장면이 둘로 쪼개지지 않게)
    })


def set_scene_keep(interview_id: int, keep: bool) -> None:
    """면접자가 '감점 장면 저장'을 끄면 그 면접의 사진을 남기지 않는다 (이미 모은 후보도 버림)."""
    st = _state(interview_id)
    st["keep"] = bool(keep)
    if not keep:
        st["recent"].clear()
        st["streak"].clear()
        st["scenes"].clear()


def set_scene_question(interview_id: int, order: Optional[int]) -> None:
    _state(interview_id)["q"] = order


def _finish_streak(st: dict) -> None:
    streak = st["streak"]
    if len(streak) >= SCENE_MIN_STREAK:
        reasons = [e["reason"] for e in streak]
        reason = max(set(reasons), key=reasons.count)
        eyes = [e["result"].get("eye_contact_score") for e in streak if e["result"].get("eye_contact_score") is not None]
        exprs = [e["result"].get("expression_score") for e in streak if e["result"].get("expression_score") is not None]
        eye = sum(eyes) / len(eyes) if eyes else None
        depth = (40 - eye) / 40 if reason == "away" and eye is not None else 0.5
        frames = list(st["recent"]) + streak
        st["last"] = {
            "reason": reason,
            "severity": len(streak) * _SCENE_WEIGHT.get(reason, 1.0) * (1 + max(0.0, depth)),
            "question_order": streak[0]["q"],
            "at_sec": round(streak[0]["t"], 1),
            "duration_sec": round(len(streak) / 2, 1),
            "eye_score": round(eye, 1) if eye is not None else None,
            "expression_score": round(sum(exprs) / len(exprs), 1) if exprs else None,
            "frames": [e["bytes"] for e in frames],
        }
        st["scenes"].append(st["last"])
        # 후보가 너무 많으면 가장 가벼운 것부터 버림 (메모리 상한)
        if len(st["scenes"]) > SCENE_MAX_CANDIDATES:
            st["scenes"].sort(key=lambda s: s["severity"], reverse=True)
            del st["scenes"][SCENE_MAX_CANDIDATES:]
        st["recent"].clear()
    st["streak"] = []


def add_scene_frame(interview_id: int, result: dict, frame_bytes: bytes) -> None:
    """실제로 분석한 프레임(사진 + 결과)을 장면 추적에 넣는다. 저장을 끈 면접이면 아무것도 남기지 않는다."""
    st = _state(interview_id)
    if not st["keep"] or not frame_bytes or len(frame_bytes) > SCENE_MAX_FRAME_BYTES or not frame_bytes.startswith(b"\xff\xd8"):
        return
    entry = {"t": time.monotonic() - st["t0"], "result": result, "bytes": frame_bytes,
             "q": st["q"], "reason": scene_reason(result)}
    if entry["reason"]:
        if st["hold"]:
            # 사진은 더 담지 않고, 감점이 이어진 시간만 늘린다 (결과 화면에 '5초 동안' 처럼 실제 길이가 보이게)
            if st.get("last"):
                st["last"]["duration_sec"] = round(st["last"]["duration_sec"] + 0.5, 1)
                st["last"]["severity"] += 0.5 * _SCENE_WEIGHT.get(st["last"]["reason"], 1.0)
            return
        st["streak"].append(entry)
        if len(st["streak"]) >= SCENE_MAX_STREAK:
            _finish_streak(st)
            st["hold"] = True
    else:
        st["hold"] = False
        if st["streak"]:
            _finish_streak(st)
        st["recent"].append(entry)


def pop_scenes(interview_id: int, limit: int = 5) -> Optional[list]:
    """분석 단계에서 한 번 — 가장 크게 감점된 장면부터 limit개 (같은 이유는 최대 3개).
    None = 이 면접은 장면 추적을 안 함(서버 재시작 · 카메라 없음), [] = 감점 장면 없음."""
    st = _scene_state.pop(interview_id, None)
    if st is None:
        return None
    _finish_streak(st)
    picked, per_reason = [], {}
    for s in sorted(st["scenes"], key=lambda s: s["severity"], reverse=True):
        if per_reason.get(s["reason"], 0) >= 3:
            continue
        picked.append(s)
        per_reason[s["reason"]] = per_reason.get(s["reason"], 0) + 1
        if len(picked) >= limit:
            break
    return sorted(picked, key=lambda s: s["severity"], reverse=True)
