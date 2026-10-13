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
 * @param {boolean}  [opts.keepScenes=true]  감점 장면 사진 저장 (결과 화면의 움직이는 이미지, 30일 뒤 자동 삭제) — 환경 설정 화면에서 고름
 * @param {number}   [opts.questionOrder]    지금 답하는 질문 번호 — 감점 장면에 '질문 N 답변 중'을 붙이려고 서버에 알림
 */
export function useVisionStream({ interviewId, videoRef, active, onResult, fps = 2, keepScenes = true, questionOrder }) {
  const activeRef = useRef(active)
  const onResultRef = useRef(onResult)
  const keepRef = useRef(keepScenes)
  const questionRef = useRef(questionOrder)
  const wsRef = useRef(null)
  activeRef.current = active
  onResultRef.current = onResult
  keepRef.current = keepScenes

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
      wsRef.current = ws
      ws.onopen = () => {
        // 다시 연결될 때도 저장 여부 · 지금 질문을 다시 알린다
        ws.send(JSON.stringify({ type: 'start', keep_scenes: !!keepRef.current }))
        if (Number.isInteger(questionRef.current)) ws.send(JSON.stringify({ type: 'question', order: questionRef.current }))
      }
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
      wsRef.current = null
    }
  }, [interviewId, videoRef, fps])

  // 질문이 바뀌면 서버에 알림
  useEffect(() => {
    questionRef.current = questionOrder
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN && Number.isInteger(questionOrder)) {
      ws.send(JSON.stringify({ type: 'question', order: questionOrder }))
    }
  }, [questionOrder])
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
