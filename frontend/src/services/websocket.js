/**
 * WebSocket 서비스 — 면접 중 실시간 통신
 * 프레임 전송 / 분석 결과 수신
 */

class InterviewWebSocket {
  constructor() {
    this.ws = null
    this.audioWs = null
    this.mediaRecorder = null
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

    //추가: 신규 음성 전용 연결
    const audioUrl = `ws://${window.location.hostname}:8000/ws/interview_audio/${interviewId}`
    this.audioWs = new WebSocket(audioUrl)

    this.ws.onopen = () => {
      this.isConnected = true
      this.ws.send(JSON.stringify({ type: 'start' }))
      console.log('[WS] 연결됨:', interviewId)
    }
    // 추가: 오디오 소켓 연결 확인 로그 
    this.audioWs.onopen = () => console.log('[WS-Audio] 연결됨')

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

   // 추가: 외부에서 마이크 스트림을 전달받아 오디오 전송 시작
    startAudioRecording(audioStream) {
        // 이 함수를 호출하기 전에 브라우저에서 navigator.mediaDevices.getUserMedia({ audio: true }) 로 스트림을 받아와야 합니다.
        this.mediaRecorder = new MediaRecorder(audioStream);
        
        this.mediaRecorder.ondataavailable = async (event) => {
            if (event.data.size > 0 && this.audioWs && this.audioWs.readyState === WebSocket.OPEN) {
                const buffer = await event.data.arrayBuffer();
                this.audioWs.send(buffer);
            }
        };
        
        // 250ms(0.25초) 간격으로 잘라서 전송
        this.mediaRecorder.start(250);
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

    // 추가: 음성 소켓 및 녹음기 종료 처리 [5]
        if (this.audioWs) {
            this.audioWs.close()
        }
        if (this.mediaRecorder) {
            this.mediaRecorder.stop()
        }

    this.isConnected = false
  }
}

export const interviewWS = new InterviewWebSocket()
