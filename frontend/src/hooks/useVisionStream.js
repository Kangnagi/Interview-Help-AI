import { useEffect, useRef } from 'react'
import { wsUrl } from '@/services/websocket'

/**
 * 면접 중 카메라 프레임을 서버(MediaPipe, /ws/interview/{id})로 보내 자세 · 시선을 실제로 잰다.
 * 서버는 프레임마다 결과를 돌려주고(face_detected · eye_contact · posture_ok · eyes_closed · smile …),
 * 면접 종료 후 분석 단계에서 모은 결과로 자세 · 시선 점수를 낸다 (core/vision_buffer.py).
 * (예전엔 연습 · 실전 화면이 프레임을 보내지 않아 자세 · 시선이 답변 점수로 만든 추정값이었다)
 *
 * @param {object}   opts
 * @param {number}   opts.interviewId  서버 면접 ID — 없으면 연결하지 않음
 * @param {object}   opts.videoRef     카메라 영상이 붙은 <video> ref
 * @param {boolean}  opts.active       true일 때만 프레임을 보냄 (질문 · 답변 중)
 * @param {function} opts.onResult     (result) => void — 프레임 분석 결과
 * @param {number}   [opts.fps=2]      초당 프레임 수 (서버 분석 1장 약 10~20ms)
 */
export function useVisionStream({ interviewId, videoRef, active, onResult, fps = 2 }) {
  const activeRef = useRef(active)
  const onResultRef = useRef(onResult)
  activeRef.current = active
  onResultRef.current = onResult

  useEffect(() => {
    if (!interviewId) return
    let disposed = false
    let ws = null
    let waiting = false          // 앞 프레임 결과를 기다리는 중이면 다음 프레임을 보내지 않음 (느린 망에서 쌓이지 않게)
    let waitingSince = 0
    let retryTimer = null
    const canvas = document.createElement('canvas')
    canvas.width = 320           // 분석용 작은 해상도
    canvas.height = 240
    const ctx = canvas.getContext('2d')

    const connect = () => {
      const token = localStorage.getItem('token')    // 자동 연장된 최신 토큰
      if (disposed || !token) return
      ws = new WebSocket(wsUrl(`/ws/interview/${interviewId}?token=${encodeURIComponent(token)}`))
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'frame_analysis') {
            waiting = false
            onResultRef.current?.(msg.result)
          }
        } catch { /* 상태 메시지 등은 무시 */ }
      }
      ws.onclose = () => {
        waiting = false
        if (!disposed) retryTimer = setTimeout(connect, 3000)   // 끊기면 3초 뒤 다시 연결
      }
    }

    const tick = () => {
      const video = videoRef.current
      if (!activeRef.current || !ws || ws.readyState !== WebSocket.OPEN || !video || video.readyState < 2) return
      if (waiting && Date.now() - waitingSince < 3000) return
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      waiting = true
      waitingSince = Date.now()
      canvas.toBlob((blob) => {
        if (!blob || !ws || ws.readyState !== WebSocket.OPEN) { waiting = false; return }
        blob.arrayBuffer().then((buf) => ws.send(buf)).catch(() => { waiting = false })
      }, 'image/jpeg', 0.6)
    }

    connect()
    const timer = setInterval(tick, Math.round(1000 / fps))
    return () => {
      disposed = true
      clearInterval(timer)
      clearTimeout(retryTimer)
      ws?.close()
    }
  }, [interviewId, videoRef, fps])
}

/**
 * 프레임 결과 → 카메라 칸 표시 상태. 한두 장 흔들림에 표시가 깜빡이지 않게 최근 3장을 본다.
 * 'detected'(얼굴 인식됨) · 'away'(정면을 봐 주세요) · 'lost'(얼굴 없음) · null(판단 못 함 — 표시 유지)
 */
export function faceStatusFromResults(recent) {
  const known = recent.filter((r) => r && r.face_detected != null)
  if (known.length === 0) return null
  if (known.every((r) => !r.face_detected)) return 'lost'
  const faced = known.filter((r) => r.face_detected)
  if (faced.length >= 2 && faced.every((r) => !r.eye_contact)) return 'away'
  return 'detected'
}
