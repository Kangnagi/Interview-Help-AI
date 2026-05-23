/**
 * WebSocket 서비스 — 면접 중 실시간 통신
 * 프레임 전송 / 분석 결과 수신
 */

class InterviewWebSocket {
  constructor() {
    this.ws = null                // WebSocket 연결 객체
    this.audioWs = null
    this.mediaRecorder = null
    this.interviewId = null       // 현재 연결된 면접 ID
    this.onFrameAnalysis = null   // 프레임 분석 결과 콜백 (result) => void
    this.onStatusChange  = null   // 상태 변경 콜백 (status) => void
    this.reconnectTimer  = null   // 자동 재연결 타이머 (미사용)
    this.isConnected = false      // 연결 상태 플래그
  }

  connect(interviewId) {
    // WebSocket 연결 시작 — 백엔드 /ws/interview/{id} 엔드포인트로 연결
    this.interviewId = interviewId
    const url = `ws://${window.location.hostname}:8000/ws/interview/${interviewId}`
    this.ws = new WebSocket(url)

    //추가: 신규 음성 전용 연결
    const audioUrl = `ws://${window.location.hostname}:8000/ws/interview_audio/${interviewId}`
    this.audioWs = new WebSocket(audioUrl)

    this.ws.onopen = () => {
      // 연결 성공 — 'start' 제어 메시지 전송
      this.isConnected = true
      this.ws.send(JSON.stringify({ type: 'start' }))
      console.log('[WS] 연결됨:', interviewId)
    }
    // 추가: 오디오 소켓 연결 확인 로그 
    this.audioWs.onopen = () => console.log('[WS-Audio] 연결됨')

    this.ws.onmessage = (event) => {
      // 서버로부터 메시지 수신 — JSON 파싱 후 타입별 처리
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'frame_analysis' && this.onFrameAnalysis) {
          // MediaPipe 분석 결과 수신 — 콜백 함수 호출
          this.onFrameAnalysis(msg.payload)
        } else if (msg.type === 'status' && this.onStatusChange) {
          // 상태 변경 메시지 수신 (예: recording → stopped)
          this.onStatusChange(msg.payload?.status)
        }
      } catch (e) {
        console.warn('[WS] 메시지 파싱 실패', e)
      }
    }

    this.ws.onclose = () => {
      // WebSocket 연결 종료
      this.isConnected = false
      console.log('[WS] 연결 종료')
    }

    this.ws.onerror = (err) => {
      // 연결 에러 발생
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
    /**
     * 비디오 요소의 프레임을 JPEG로 압축하여 바이너리로 전송
     * 백엔드 MediaPipe가 수신하여 실시간 얼굴/자세 분석
     * @param {HTMLVideoElement} videoEl — 웹캠 스트림이 흐르는 video 엘리먼트
     */
    if (!this.isConnected || !videoEl) return
    const canvas = document.createElement('canvas')
    canvas.width  = 320                                       // 분석용 작은 해상도 (성능)
    canvas.height = 240
    const ctx = canvas.getContext('2d')                       // 비디오 프레임을 캔버스에 그리기
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height)
    canvas.toBlob(
      (blob) => blob?.arrayBuffer().then((buf) => this.ws.send(buf)),// JPEG Blob을 바이너리로 변환 후 전송
      'image/jpeg',
      0.6,                                                            // JPEG 품질 60% (네트워크 효율)
    )
  }

  stop() {
    // WebSocket 연결 종료 — 'stop' 제어 메시지 전송 후 닫기
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

export const interviewWS = new InterviewWebSocket()   // 싱글톤 인스턴스 — 앱 전역에서 import 하여 사용
