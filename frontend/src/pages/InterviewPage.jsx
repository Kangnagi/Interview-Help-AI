import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useInterviewStore } from '@/store/interviewStore'
import { useResumeStore } from '@/store/resumeStore' // 로컬 저장용 추가
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition' // 음성 인식 추가
import { interviewWS } from '@/services/websocket'
import toast from 'react-hot-toast'

export default function InterviewPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const frameTimer = useRef(null)

  const { questions, loadQuestions, currentQuestionIdx, nextQuestion, submitAnswer, finishInterview, startAnalysis } = useInterviewStore()

  const { addInterviewRecord } = useResumeStore() // 대시보드 통계 동기화용

  const [answer, setAnswer]       = useState('')
  const [recording, setRecording] = useState(false)
  const [timeLeft, setTimeLeft]   = useState(120)     // 질문당 2분
  const [camReady, setCamReady]   = useState(false)
  const [feedback, setFeedback]   = useState(null)    // 실시간 WS 피드백

  // 음성 인식 훅 연결
  const { listening, interim, toggle: toggleSTT, stop: stopSTT } = useSpeechRecognition({
    onFinal: (text) => setAnswer((prev) => prev + " " + text)
  })
  const currentQ = questions[currentQuestionIdx]
  const isLast   = currentQuestionIdx === questions.length - 1

  // ─ 카메라 초기화 ──────────────────────────────
  useEffect(() => {
    loadQuestions(id)

    navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      .then((stream) => {
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
        setCamReady(true)
      })
      .catch(() => toast.error('카메라/마이크 권한이 필요합니다'))

    interviewWS.onFrameAnalysis = (result) => setFeedback(result)
    interviewWS.connect(id)

    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      interviewWS.stop()
      clearInterval(frameTimer.current)
    }
  }, [id])

  // ─ 프레임 전송 타이머 ─────────────────────────
  useEffect(() => {
    if (camReady && recording) {
      frameTimer.current = setInterval(() => {
        interviewWS.sendFrame(videoRef.current)
      }, 1000)   // 1fps
    }
    return () => clearInterval(frameTimer.current)
  }, [camReady, recording])

  // ─ 타이머 ─────────────────────────────────────
  useEffect(() => {
    if (!recording) return
    const t = setInterval(() => setTimeLeft((prev) => {
      if (prev <= 1) { clearInterval(t); return 0 }
      return prev - 1
    }), 1000)
    return () => clearInterval(t)
  }, [recording])

  const handleRecord = () => {
    setRecording(true)
    setTimeLeft(120)
    toast('답변을 시작하세요!', { icon: '🎤' })
  }

  const handleNext = useCallback(async () => {
    if (!answer.trim()) return toast.error('답변을 입력해주세요')

    await submitAnswer(id, currentQ.id, answer)
    setAnswer('')
    setRecording(false)
    setTimeLeft(120)

    if (isLast) {
      await finishInterview(id)
      await startAnalysis(id)
      toast.success('면접이 완료되었습니다! 분석 중...')
      navigate(`/interview/${id}/result`)
    } else {
      nextQuestion()
      toast.success('다음 질문으로 이동합니다')
    }
  }, [answer, currentQ, isLast, id])

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
  const progress   = questions.length ? ((currentQuestionIdx + 1) / questions.length) * 100 : 0

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20, height: 'calc(100vh - 120px)' }}>

      {/* 왼쪽: 카메라 + 질문 + 답변 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* 진행 상황 */}
        <div className="card" style={{ padding: '14px 20px' }}>
          <div className="flex justify-between items-center" style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 500 }}>질문 {currentQuestionIdx + 1} / {questions.length}</span>
            {recording && (
              <span style={{ fontSize: 13, color: timeLeft < 30 ? 'var(--danger)' : 'var(--text-secondary)', fontWeight: 500 }}>
                ⏱ {formatTime(timeLeft)}
              </span>
            )}
          </div>
          <div style={{ height: 6, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{ width: `${progress}%`, height: '100%', background: 'var(--primary)', transition: 'width .4s' }} />
          </div>
        </div>

        {/* 카메라 */}
        <div style={{ background: '#111', borderRadius: 'var(--radius-lg)', overflow: 'hidden', aspectRatio: '16/9', position: 'relative' }}>
          <video ref={videoRef} autoPlay muted playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          {!camReady && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
              카메라 연결 중...
            </div>
          )}
          {recording && (
            <div style={{ position: 'absolute', top: 12, left: 12, background: 'rgba(239,68,68,.85)',
              color: '#fff', borderRadius: 99, padding: '3px 10px', fontSize: 12, fontWeight: 600 }}>
              ● REC
            </div>
          )}
        </div>

        {/* 질문 */}
        {currentQ && (
          <div className="card">
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6 }}>Q{currentQ.order}.</p>
            <p style={{ fontSize: 17, fontWeight: 600, lineHeight: 1.6 }}>{currentQ.question_text}</p>
          </div>
        )}

        {/* 답변 입력 */}
        <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div className="flex justify-between items-center" style={{ marginBottom: 10 }}>
            <p style={{ fontWeight: 600, fontSize: 14 }}>답변 입력</p>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{answer.length}자</span>
          </div>
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="답변을 입력하거나 말씀하세요 (음성 인식은 다음 단계에서 연동됩니다)"
            style={{ flex: 1, minHeight: 120, resize: 'none', border: '1.5px solid var(--border)',
              borderRadius: 'var(--radius-md)', padding: 12, fontSize: 14, lineHeight: 1.6, width: '100%' }}
          />
          <div className="flex gap-8" style={{ marginTop: 12 }}>
            {!recording && (
              <button className="btn btn-outline" onClick={handleRecord}>
                🎤 답변 시작
              </button>
            )}
            <button className="btn btn-primary w-full" onClick={handleNext}>
              {isLast ? '✅ 면접 종료' : '다음 질문 →'}
            </button>
          </div>
        </div>
      </div>

      {/* 오른쪽: 실시간 분석 패널 */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>📊 실시간 분석</h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 16 }}>
            AI 모델 연결 후 실시간 피드백이 표시됩니다
          </p>

          {[
            { label: '눈맞춤', value: feedback?.eye_contact ? '✅ 양호' : '⚠️ 주의', ok: feedback?.eye_contact },
            { label: '자세',   value: feedback?.posture_ok  ? '✅ 양호' : '⚠️ 주의', ok: feedback?.posture_ok  },
            { label: '표정',   value: feedback?.expression || '—', ok: true },
          ].map(({ label, value, ok }) => (
            <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
              <span style={{ fontSize: 13, fontWeight: 500, color: ok ? 'var(--secondary)' : 'var(--warning)' }}>{value}</span>
            </div>
          ))}
        </div>

        <div className="card">
          <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>💡 면접 팁</h3>
          {[
            '카메라를 정면으로 바라보세요',
            '천천히 또렷하게 말하세요',
            '구체적인 사례를 들어 답변하세요',
            '자신감 있는 자세를 유지하세요',
          ].map((tip, i) => (
            <p key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.6 }}>
              · {tip}
            </p>
          ))}
        </div>

        <div className="card" style={{ background: 'var(--primary-light)', border: '1px solid #C7D3FC' }}>
          <p style={{ fontSize: 12, color: '#3A57E8', fontWeight: 500, marginBottom: 4 }}>🔬 다음 단계 예정</p>
          <p style={{ fontSize: 12, color: '#4F6EF7', lineHeight: 1.7 }}>
            Whisper 음성 인식 · MediaPipe 표정 분석 · KoBERT 실시간 피드백
          </p>
        </div>
      </div>
    </div>
  )
}
