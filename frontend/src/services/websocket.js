/**
 * WebSocket 서비스 — 실전 면접
 * 카메라 프레임 전송 / MediaPipe 분석 결과 수신
 */

import { useAuthStore } from '@/store/authStore'

class InterviewWebSocket {
  constructor() {
    this.ws = null
    this.interviewId = null

    this.onFrameAnalysis = null
    this.onStatusChange = null

    this.isConnected = false
  }

  connect(interviewId) {
    this.interviewId = interviewId

    // Zustand authStore에서 JWT 가져오기
    const token = useAuthStore.getState().token

    if (!token) {
      console.error('[WS] JWT 토큰이 없습니다.')
      return
    }

    const protocol =
      window.location.protocol === 'https:'
        ? 'wss'
        : 'ws'

    const url =
      `${protocol}://${window.location.hostname}:8000` +
      `/ws/interview/${interviewId}` +
      `?token=${encodeURIComponent(token)}`

    console.log(
      '[WS] 연결 시도:',
      `${protocol}://${window.location.hostname}:8000/ws/interview/${interviewId}?token=***`
    )

    this.ws = new WebSocket(url)

    // 연결 성공
    this.ws.onopen = () => {
      this.isConnected = true

      console.log(
        '[WS] 연결 성공:',
        interviewId
      )

      this.ws.send(
        JSON.stringify({
          type: 'start',
        })
      )
    }

    // 서버 메시지
    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        console.log(
          '[WS] 서버 수신:',
          msg
        )

        // FastAPI:
        //
        // {
        //   "type": "frame_analysis",
        //   "result": result
        // }
        //
        if (msg.type === 'frame_analysis') {
          if (this.onFrameAnalysis) {
            this.onFrameAnalysis(msg.result)
          }

          return
        }

        // FastAPI:
        //
        // {
        //   "type": "status",
        //   "received": "start"
        // }
        //
        if (msg.type === 'status') {
          if (this.onStatusChange) {
            this.onStatusChange(
              msg.received
            )
          }

          return
        }

      } catch (error) {
        console.warn(
          '[WS] 메시지 파싱 실패:',
          error,
          event.data
        )
      }
    }

    // 종료
    this.ws.onclose = (event) => {
      this.isConnected = false

      console.log(
        '[WS] 연결 종료:',
        event.code,
        event.reason
      )
    }

    // 오류
    this.ws.onerror = (error) => {
      this.isConnected = false

      console.error(
        '[WS] WebSocket 오류:',
        error
      )
    }
  }

  /**
   * 현재 video 프레임을 JPEG로 변환하여 서버로 전송
   */
  sendFrame(videoEl) {
    if (
      !this.ws ||
      this.ws.readyState !== WebSocket.OPEN ||
      !this.isConnected
    ) {
      return
    }

    if (!videoEl) {
      return
    }

    if (
      !videoEl.videoWidth ||
      !videoEl.videoHeight
    ) {
      console.warn(
        '[WS] video 프레임이 아직 준비되지 않았습니다.'
      )

      return
    }

    const canvas =
      document.createElement('canvas')

    canvas.width = 320
    canvas.height = 240

    const ctx =
      canvas.getContext('2d')

    if (!ctx) {
      console.error(
        '[WS] Canvas Context 생성 실패'
      )

      return
    }

    // 화면에 보이는 거울 방향과 상관없이
    // 원본 프레임을 서버에 전송
    ctx.drawImage(
      videoEl,
      0,
      0,
      canvas.width,
      canvas.height
    )

    canvas.toBlob(
      async (blob) => {
        if (!blob) {
          console.warn(
            '[WS] JPEG Blob 생성 실패'
          )
          return
        }

        if (
          !this.ws ||
          this.ws.readyState !== WebSocket.OPEN
        ) {
          return
        }

        try {
          const buffer =
            await blob.arrayBuffer()

          this.ws.send(buffer)

          console.log(
            '[WS] 카메라 프레임 전송:',
            buffer.byteLength,
            'bytes'
          )

        } catch (error) {
          console.error(
            '[WS] 프레임 전송 실패:',
            error
          )
        }
      },
      'image/jpeg',
      0.6
    )
  }

  stop() {
    if (this.ws) {
      if (
        this.ws.readyState ===
        WebSocket.OPEN
      ) {
        this.ws.send(
          JSON.stringify({
            type: 'stop',
          })
        )
      }

      this.ws.close()
      this.ws = null
    }

    this.isConnected = false

    console.log(
      '[WS] 연결 종료 요청'
    )
  }
}

export const interviewWS =
  new InterviewWebSocket()