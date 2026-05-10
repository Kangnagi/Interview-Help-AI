import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import InterviewSetup from '@/components/Interview/InterviewSetup'

const PHASE = {
  SETUP: 'setup',
  WAITING: 'waiting',
  QUESTION: 'question',
  ANSWERING: 'answering',
  FEEDBACK: 'feedback',
  DONE: 'done',
}

const SAMPLE_QUESTIONS = [
  '자기소개를 간략하게 해주세요.',
  '해당 직무에 지원하게 된 이유가 무엇인가요?',
  '본인의 가장 큰 강점과 약점은 무엇인가요?',
  '이전 프로젝트에서 가장 힘들었던 상황과 어떻게 극복했는지 말씀해 주세요.',
  '5년 후 본인의 모습을 어떻게 생각하시나요?',
]

const SAMPLE_FEEDBACK = [
  '답변이 구체적이고 명확했습니다. STAR 기법을 잘 활용하셨어요.',
  '핵심을 잘 짚었지만, 구체적인 수치나 사례를 더 추가하면 좋겠습니다.',
  '자신감 있게 답변하셨습니다. 조금 더 간결하게 정리하면 더욱 좋을 것 같습니다.',
  '경험을 바탕으로 한 답변이 인상적입니다. 마무리 멘트를 더 강하게 하면 좋겠습니다.',
]

export default function PracticeInterviewPage() {
  const navigate = useNavigate()
  const { resumeId } = useParams()
  const resume = useResumeStore((s) => s.getResume(resumeId))
  const { addInterviewRecord } = useResumeStore()

  const [phase, setPhase] = useState(PHASE.SETUP)
  const [deviceIds, setDeviceIds] = useState({ cameraId: '', micId: '' })
  const [sessionStarted, setSessionStarted] = useState(false)
  const [qIndex, setQIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [log, setLog] = useState([])
  const [logOpen, setLogOpen] = useState(false)
  const [totalSec, setTotalSec] = useState(0)
  const [answerSec, setAnswerSec] = useState(0)
  const [exitConfirm, setExitConfirm] = useState(false)
  const [faceStatus, setFaceStatus] = useState('waiting')
  const [feedback, setFeedback] = useState('')

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const totalTimer = useRef(null)
  const answerTimer = useRef(null)
  const detectionRef = useRef(null)

  const questions = SAMPLE_QUESTIONS.slice(0, 5)
  const currentQ = questions[qIndex]

  const { listening, interim, toggle: toggleSTT, stop: stopSTT, isSupported: sttSupported } =
    useSpeechRecognition({ onFinal: (t) => setAnswer((prev) => prev + t) })

  // Stop STT when leaving ANSWERING
  useEffect(() => {
    if (phase !== PHASE.ANSWERING) stopSTT()
  }, [phase, stopSTT])

  // Setup complete → start session
  const handleSetupReady = useCallback(({ cameraId, micId }) => {
    setDeviceIds({ cameraId, micId })
    setPhase(PHASE.WAITING)
    setSessionStarted(true)
  }, [])

  // Init camera + face detection after setup
  useEffect(() => {
    if (!sessionStarted) return
    setFaceStatus('detecting')

    const constraints = {
      video: deviceIds.cameraId ? { deviceId: { exact: deviceIds.cameraId } } : true,
      audio: deviceIds.micId ? { deviceId: { exact: deviceIds.micId } } : true,
    }
    navigator.mediaDevices.getUserMedia(constraints)
      .then((s) => {
        streamRef.current = s
        if (videoRef.current) videoRef.current.srcObject = s
        if (typeof FaceDetector !== 'undefined') {
          const detector = new FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
          detectionRef.current = setInterval(async () => {
            if (!videoRef.current || videoRef.current.readyState < 2) return
            try {
              const faces = await detector.detect(videoRef.current)
              setFaceStatus(faces.length > 0 ? 'detected' : 'lost')
            } catch { setFaceStatus('detected') }
          }, 800)
        } else {
          setTimeout(() => setFaceStatus('detected'), 1000)
        }
      })
      .catch(() => setFaceStatus('lost'))

    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      clearInterval(detectionRef.current)
    }
  }, [sessionStarted]) // eslint-disable-line react-hooks/exhaustive-deps

  // Total timer
  useEffect(() => {
    if ([PHASE.WAITING, PHASE.DONE, PHASE.SETUP].includes(phase)) return
    totalTimer.current = setInterval(() => setTotalSec((p) => p + 1), 1000)
    return () => clearInterval(totalTimer.current)
  }, [phase])

  // Answer timer
  useEffect(() => {
    clearInterval(answerTimer.current)
    if (phase === PHASE.ANSWERING) {
      setAnswerSec(0)
      answerTimer.current = setInterval(() => setAnswerSec((p) => p + 1), 1000)
    }
    return () => clearInterval(answerTimer.current)
  }, [phase])

  const fmt = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`

  const submitAnswer = () => {
    stopSTT()
    clearInterval(answerTimer.current)
    const fb = SAMPLE_FEEDBACK[Math.floor(Math.random() * SAMPLE_FEEDBACK.length)]
    setFeedback(fb)
    setPhase(PHASE.FEEDBACK)
  }

  const nextQuestion = () => {
    setLog((prev) => [...prev, { q: currentQ, a: answer, feedback }])
    if (qIndex + 1 >= questions.length) {
      addInterviewRecord(resumeId, { type: 'practice', duration: totalSec, questions: questions.map((q) => ({ question: q })) })
      setPhase(PHASE.DONE)
    } else {
      setQIndex((p) => p + 1)
      setAnswer('')
      setPhase(PHASE.QUESTION)
    }
  }

  const handleExit = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    navigate('/resume')
  }

  if (phase === PHASE.SETUP) {
    return <InterviewSetup resumeInfo={resume} onReady={handleSetupReady} />
  }

  if (!resume) return (
    <div style={{ padding: 40, textAlign: 'center', color: '#fff', background: '#0f1117', minHeight: '100vh' }}>
      자기소개서를 찾을 수 없습니다.
      <button onClick={() => navigate('/resume')} style={{ marginLeft: 12, padding: '8px 16px', background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>목록으로</button>
    </div>
  )

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#0a0d1a', display: 'flex', zIndex: 500, fontFamily: 'inherit' }}>
      <style>{`
        .pi-log-panel { width:0; overflow:hidden; transition:width .25s; flex-shrink:0; background:#111422; }
        .pi-log-panel.open { width:270px; border-left:1px solid rgba(255,255,255,.07); }
        .pi-log-inner { width:270px; padding:16px; height:100%; overflow-y:auto; }
        .pi-log-item { background:#1e2235; border-radius:8px; padding:12px; margin-bottom:10px; font-size:12px; }
        .pi-log-q { color:#4f6ef7; font-weight:600; margin-bottom:5px; }
        .pi-log-a { color:rgba(255,255,255,.6); margin-bottom:5px; line-height:1.5; }
        .pi-log-f { color:#22c55e; line-height:1.5; }
        .face-badge { position:absolute; bottom:8px; left:50%; transform:translateX(-50%); display:flex; align-items:center; gap:5px; padding:4px 10px; border-radius:99px; font-size:11px; font-weight:600; white-space:nowrap; backdrop-filter:blur(6px); }
        .face-badge.detecting { background:rgba(245,158,11,.85); color:#fff; }
        .face-badge.detected  { background:rgba(16,185,129,.85); color:#fff; }
        .face-badge.lost      { background:rgba(239,68,68,.85); color:#fff; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
        .face-dot { width:6px; height:6px; border-radius:50%; background:currentColor; animation:blink 1.2s infinite; }
        @keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
        @keyframes fadeUpCenter { from{opacity:0;transform:translateX(-50%) translateY(10px)} to{opacity:1;transform:translateX(-50%) translateY(0)} }
        .fade-up-center { animation:fadeUpCenter .35s ease forwards; }
        .fade-up { animation:fadeUp .35s ease; }
        @keyframes stt-pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
        .stt-active { animation:stt-pulse 1s infinite; }
      `}</style>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Top bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', background: '#111422', borderBottom: '1px solid rgba(255,255,255,.06)', flexShrink: 0 }}>
          <div>
            <span style={{ fontSize: 15, fontWeight: 700, color: '#fff' }}>🎓 연습 면접</span>
            <span style={{ fontSize: 12, color: 'rgba(255,255,255,.35)', marginLeft: 12 }}>{resume.companyName} · {resume.jobTitle}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {phase !== PHASE.WAITING && phase !== PHASE.DONE && (
              <span style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>Q {qIndex + 1} / {questions.length}</span>
            )}
            <button onClick={() => setLogOpen((p) => !p)} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 8, padding: '6px 14px', color: 'rgba(255,255,255,.6)', fontSize: 12, cursor: 'pointer' }}>
              📋 로그 {log.length > 0 ? `(${log.length})` : ''}
            </button>
            <button onClick={() => setExitConfirm(true)} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '6px 16px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>나가기</button>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ height: 3, background: '#1a1d2e', flexShrink: 0 }}>
          <div style={{ height: '100%', background: 'linear-gradient(90deg,#4f6ef7,#10b981)', width: `${(qIndex / questions.length) * 100}%`, transition: 'width .4s' }} />
        </div>

        {/* Stage */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, #1a2040 0%, #0a0d1a 70%)', pointerEvents: 'none' }} />

          {/* Question */}
          {[PHASE.QUESTION, PHASE.ANSWERING, PHASE.FEEDBACK].includes(phase) && (
            <div key={qIndex} className="fade-up-center" style={{ position: 'absolute', top: '8%', left: '50%', width: '60%', maxWidth: 640, textAlign: 'center', zIndex: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#4f6ef7', letterSpacing: '.08em', marginBottom: 8, textTransform: 'uppercase' }}>Q{qIndex + 1} 질문</div>
              <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', lineHeight: 1.55, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, padding: '16px 24px', backdropFilter: 'blur(8px)' }}>
                {currentQ}
              </div>
            </div>
          )}

          {/* AI Interviewer */}
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -54%)', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 5 }}>
            <div style={{ width: 130, height: 130, borderRadius: '50%', background: 'linear-gradient(135deg,#4f6ef7,#10b981)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64, boxShadow: '0 0 48px rgba(79,110,247,.35)' }}>🤖</div>
            <div style={{ marginTop: 12, fontSize: 13, color: 'rgba(255,255,255,.4)', fontWeight: 500 }}>AI 면접관</div>
          </div>

          {/* Timer */}
          <div style={{ position: 'absolute', top: 20, right: 20, zIndex: 10 }}>
            <div style={{ background: 'rgba(17,20,34,.85)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, padding: '10px 16px', backdropFilter: 'blur(8px)', textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)', marginBottom: 2 }}>면접 시간</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#fff', fontFamily: 'monospace' }}>{fmt(totalSec)}</div>
              {phase === PHASE.ANSWERING && (
                <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,.08)' }}>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)', marginBottom: 2 }}>답변 시간</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: answerSec > 120 ? '#ef4444' : '#10b981', fontFamily: 'monospace' }}>{fmt(answerSec)}</div>
                </div>
              )}
            </div>
          </div>

          {/* Camera (bottom right) */}
          <div style={{ position: 'absolute', bottom: 20, right: 20, zIndex: 10, width: 400, height: 290 }}>
            <div style={{ width: '100%', height: '100%', borderRadius: 14, overflow: 'hidden', position: 'relative', border: '2px solid rgba(255,255,255,.1)', boxShadow: '0 4px 20px rgba(0,0,0,.5)', background: '#111827' }}>
              <video ref={videoRef} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: 'scaleX(-1)' }} autoPlay playsInline muted />
              <div style={{ position: 'absolute', top: 6, left: 8, fontSize: 11, color: 'rgba(255,255,255,.5)', background: 'rgba(0,0,0,.4)', padding: '2px 7px', borderRadius: 99 }}>📹 나</div>
              {faceStatus === 'detecting' && <div className="face-badge detecting"><span className="face-dot" />인식 중...</div>}
              {faceStatus === 'detected' && <div className="face-badge detected"><span className="face-dot" />얼굴 인식됨</div>}
              {faceStatus === 'lost' && <div className="face-badge lost"><span className="face-dot" />얼굴 없음</div>}
            </div>
          </div>

          {/* Bottom action panel */}
          <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 10, width: '55%', maxWidth: 600 }}>

            {phase === PHASE.WAITING && (
              <div className="fade-up" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 15, color: 'rgba(255,255,255,.5)', marginBottom: 16 }}>총 {questions.length}개 질문이 준비되었습니다</div>
                <button onClick={() => setPhase(PHASE.QUESTION)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '13px 40px', fontSize: 15, fontWeight: 700, cursor: 'pointer' }}>
                  면접 시작 →
                </button>
              </div>
            )}

            {phase === PHASE.QUESTION && (
              <div className="fade-up" style={{ textAlign: 'center' }}>
                <button onClick={() => setPhase(PHASE.ANSWERING)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '13px 40px', fontSize: 15, fontWeight: 700, cursor: 'pointer' }}>
                  🎤 답변 시작
                </button>
              </div>
            )}

            {phase === PHASE.ANSWERING && (
              <div className="fade-up">
                {/* STT toggle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  {sttSupported ? (
                    <button
                      onClick={toggleSTT}
                      className={listening ? 'stt-active' : ''}
                      style={{
                        background: listening ? 'rgba(239,68,68,.15)' : 'rgba(79,110,247,.12)',
                        border: `1.5px solid ${listening ? '#ef4444' : 'rgba(79,110,247,.5)'}`,
                        borderRadius: 8, padding: '7px 16px',
                        color: listening ? '#ef4444' : '#6d85f8',
                        fontSize: 13, fontWeight: 600, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: 6,
                      }}
                    >
                      {listening ? '🔴 인식 중지' : '🎤 음성 입력'}
                    </button>
                  ) : (
                    <span style={{ fontSize: 12, color: 'rgba(255,255,255,.25)' }}>이 브라우저는 음성 인식을 지원하지 않습니다</span>
                  )}
                  {listening && (
                    <span style={{ fontSize: 12, color: 'rgba(255,255,255,.4)', fontStyle: 'italic' }}>말씀하세요...</span>
                  )}
                </div>

                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder={sttSupported ? '답변을 입력하거나 위 버튼으로 음성 입력하세요' : '답변을 입력하세요'}
                  autoFocus
                  style={{ width: '100%', background: 'rgba(17,20,34,.9)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 12, padding: '14px 16px', color: '#fff', fontSize: 14, resize: 'none', minHeight: 90, fontFamily: 'inherit', backdropFilter: 'blur(8px)', boxSizing: 'border-box' }}
                />

                {/* Interim transcript */}
                {interim && (
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,.35)', fontStyle: 'italic', marginTop: 5, padding: '0 4px' }}>
                    💬 {interim}
                  </div>
                )}

                <div style={{ display: 'flex', gap: 10, marginTop: 10, justifyContent: 'center' }}>
                  <button onClick={() => { stopSTT(); setPhase(PHASE.QUESTION); setAnswer('') }} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '10px 24px', color: 'rgba(255,255,255,.6)', fontSize: 14, cursor: 'pointer' }}>재시작</button>
                  <button onClick={submitAnswer} style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 28px', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>✅ 답변 완료</button>
                </div>
              </div>
            )}

            {phase === PHASE.FEEDBACK && (
              <div className="fade-up">
                <div style={{ background: 'rgba(16,185,129,.12)', border: '1.5px solid rgba(34,197,94,.4)', borderRadius: 12, padding: '14px 18px', marginBottom: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#22c55e', marginBottom: 6 }}>💡 AI 피드백</div>
                  <div style={{ fontSize: 14, color: 'rgba(255,255,255,.85)', lineHeight: 1.6 }}>{feedback}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <button onClick={nextQuestion} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '11px 32px', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                    {qIndex + 1 >= questions.length ? '🎉 면접 종료' : '다음 질문 →'}
                  </button>
                </div>
              </div>
            )}

            {phase === PHASE.DONE && (
              <div className="fade-up" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 42, marginBottom: 10 }}>🎉</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 6 }}>면접 완료!</div>
                <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 20 }}>{questions.length}개 질문 · {fmt(totalSec)} 소요</div>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                  <button onClick={handleExit} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '10px 24px', color: 'rgba(255,255,255,.6)', fontSize: 14, cursor: 'pointer' }}>목록으로</button>
                  <button onClick={() => { setPhase(PHASE.WAITING); setQIndex(0); setLog([]); setTotalSec(0) }} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 28px', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>다시 시작</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Log panel */}
      <div className={`pi-log-panel${logOpen ? ' open' : ''}`}>
        <div className="pi-log-inner">
          <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,.45)', marginBottom: 14 }}>📋 면접 로그</div>
          {log.length === 0
            ? <div style={{ fontSize: 13, color: 'rgba(255,255,255,.25)', textAlign: 'center', marginTop: 40 }}>아직 기록이 없습니다</div>
            : log.map((item, i) => (
              <div key={i} className="pi-log-item">
                <div className="pi-log-q">Q{i + 1}. {item.q}</div>
                <div className="pi-log-a">A: {item.a || '(없음)'}</div>
                <div className="pi-log-f">💡 {item.feedback}</div>
              </div>
            ))
          }
        </div>
      </div>

      {/* Exit confirm */}
      {exitConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 600 }}>
          <div style={{ background: '#111422', borderRadius: 14, padding: '28px 32px', minWidth: 300, textAlign: 'center', border: '1px solid rgba(255,255,255,.1)' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 10 }}>면접을 종료하시겠습니까?</div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 24 }}>진행 중인 내용은 저장되지 않습니다.</div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button onClick={() => setExitConfirm(false)} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 8, padding: '10px 22px', color: 'rgba(255,255,255,.6)', cursor: 'pointer', fontSize: 14 }}>계속 진행</button>
              <button onClick={handleExit} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '10px 22px', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>종료</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
