/**
 * WebSocket 서비스 — 면접 중 실시간 통신
 * 프레임 전송 / 분석 결과 수신
 */

class InterviewWebSocket {
  constructor() {
    this.ws = null
    this.interviewId = null
    this.onFrameAnalysis = null   // (result) => void
    this.onStatusChange  = null   // (status) => void
    this.reconnectTimer  = null
    this.isConnected = false
  }

  connect(interviewId) {
    this.interviewId = interviewId
    const url = `ws://${window.location.hostname}:8000/ws/interview/${interviewId}`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.isConnected = true
      this.ws.send(JSON.stringify({ type: 'start' }))
      console.log('[WS] 연결됨:', interviewId)
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'frame_analysis' && this.onFrameAnalysis) {
          this.onFrameAnalysis(msg.payload)
        } else if (msg.type === 'status' && this.onStatusChange) {
          this.onStatusChange(msg.payload?.status)
        }
      } catch (e) {
        console.warn('[WS] 메시지 파싱 실패', e)
      }
    }

    this.ws.onclose = () => {
      this.isConnected = false
      console.log('[WS] 연결 종료')
    }

    this.ws.onerror = (err) => {
      console.error('[WS] 오류', err)
    }
  }

  /**
   * 캔버스 프레임을 JPEG Blob으로 변환 후 전송
   * @param {HTMLVideoElement} videoEl
   */
  sendFrame(videoEl) {
    if (!this.isConnected || !videoEl) return
    const canvas = document.createElement('canvas')
    canvas.width  = 320
    canvas.height = 240
    const ctx = canvas.getContext('2d')
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(
      (blob) => blob?.arrayBuffer().then((buf) => this.ws.send(buf)),
      'image/jpeg',
      0.6,
    )
  }

  stop() {
    if (this.ws) {
      this.ws.send(JSON.stringify({ type: 'stop' }))
      this.ws.close()
    }
    this.isConnected = false
  }
}

export const interviewWS = new InterviewWebSocket()
