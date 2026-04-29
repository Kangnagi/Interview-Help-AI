import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'

const PHASE = { INTRO: 'intro', INTERVIEW: 'interview', RESULT: 'result' }

const QUESTIONS = [
  '자기소개를 1분 이내로 해주세요.',
  '지원 동기를 말씀해 주세요.',
  '본인의 강점과 이를 업무에 어떻게 활용했는지 말씀해 주세요.',
  '가장 도전적이었던 프로젝트 경험을 공유해 주세요.',
  '마지막으로 하고 싶은 말씀이 있으신가요?',
]

const Q_LIMIT = 120 // 질문당 최대 답변 시간 (초)

export default function RealInterviewPage() {
  const navigate = useNavigate()
  const { resumeId } = useParams()
  const resume = useResumeStore((s) => s.getResume(resumeId))
  const { addInterviewRecord } = useResumeStore()

  const [phase, setPhase] = useState(PHASE.INTRO)
  const [qIndex, setQIndex] = useState(0)
  const [remaining, setRemaining] = useState(Q_LIMIT)
  const [answer, setAnswer] = useState('')
  const [answers, setAnswers] = useState([])
  const [totalSec, setTotalSec] = useState(0)
  const [exitConfirm, setExitConfirm] = useState(false)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const detectionRef = useRef(null)
  const [faceStatus, setFaceStatus] = useState('waiting')
  const [micActive, setMicActive] = useState(false)
  const micAnalyserRef = useRef(null)
  const timerRef = useRef(null)
  const totalRef = useRef(null)

  const currentQ = QUESTIONS[qIndex]
  const pct = Math.round(((Q_LIMIT - remaining) / Q_LIMIT) * 100)
  // 원형 타이머
  const r = 52, circ = 2 * Math.PI * r
  const color = remaining > 60 ? '#10b981' : remaining > 30 ? '#f59e0b' : '#ef4444'

  useEffect(() => {
    setFaceStatus('detecting')
    navigator.mediaDevices?.getUserMedia({ video: true, audio: false })
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
          setTimeout(() => setFaceStatus('detected'), 1500)
        }
      })
      .catch(() => { setFaceStatus('lost') })

    // 마이크 감지
    navigator.mediaDevices?.getUserMedia({ audio: true, video: false })
      .then((audioStream) => {
        const ctx = new (window.AudioContext || window.webkitAudioContext)()
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 256
        const source = ctx.createMediaStreamSource(audioStream)
        source.connect(analyser)
        micAnalyserRef.current = analyser
        const data = new Uint8Array(analyser.frequencyBinCount)
        const checkMic = () => {
          analyser.getByteFrequencyData(data)
          const avg = data.reduce((a, b) => a + b, 0) / data.length
          setMicActive(avg > 8)
          micAnalyserRef.requestId = requestAnimationFrame(checkMic)
        }
        checkMic()
      })
      .catch(() => {})
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      clearInterval(timerRef.current)
      clearInterval(totalRef.current)
      clearInterval(detectionRef.current)
    }
  }, [])

  useEffect(() => {
    if (phase === PHASE.INTERVIEW) {
      totalRef.current = setInterval(() => setTotalSec((p) => p + 1), 1000)
      startQTimer()
    }
    return () => { clearInterval(timerRef.current); clearInterval(totalRef.current) }
  }, [phase])

  const startQTimer = () => {
    clearInterval(timerRef.current)
    setRemaining(Q_LIMIT)
    timerRef.current = setInterval(() => {
      setRemaining((p) => {
        if (p <= 1) { clearInterval(timerRef.current); handleNext(); return 0 }
        return p - 1
      })
    }, 1000)
  }

  const handleNext = () => {
    clearInterval(timerRef.current)
    const newAnswers = [...answers, { q: currentQ, a: answer }]
    setAnswers(newAnswers)
    setAnswer('')
    if (qIndex + 1 >= QUESTIONS.length) {
      clearInterval(totalRef.current)
      addInterviewRecord(resumeId, { type: 'real', duration: totalSec, questions: newAnswers })
      setPhase(PHASE.RESULT)
    } else {
      setQIndex((p) => p + 1)
      startQTimer()
    }
  }

  const fmtTime = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`

  const handleExit = () => { streamRef.current?.getTracks().forEach((t) => t.stop()); navigate('/resume') }

  if (!resume) return <div style={{ padding: 40, textAlign: 'center' }}>자기소개서를 찾을 수 없습니다. <button onClick={() => navigate('/resume')} className="btn btn-primary" style={{ marginLeft: 10 }}>목록으로</button></div>

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#0a0d1a', display: 'flex', flexDirection: 'column', zIndex: 500 }}>
      <style>{`
        .ri-header { display:flex; align-items:center; justify-content:space-between; padding:16px 28px; background:#111422; border-bottom:1px solid rgba(255,255,255,.06); }
        .ri-body { flex:1; display:flex; gap:20px; padding:20px 28px; overflow:hidden; }
        .ri-left { flex:1.4; display:flex; flex-direction:column; gap:14px; }
        .ri-right { flex:1; display:flex; flex-direction:column; gap:14px; }
        .ri-panel { background:#111422; border-radius:14px; border:1px solid rgba(255,255,255,.07); overflow:hidden; }
        .ri-panel-title { font-size:12px; font-weight:700; color:rgba(255,255,255,.35); padding:10px 16px; border-bottom:1px solid rgba(255,255,255,.06); text-transform:uppercase; letter-spacing:.05em; }
        .ri-timer-ring { display:flex; align-items:center; justify-content:center; padding:24px; flex-direction:column; gap:12px; }
        .ri-q-bubble { background:#1e2540; border-radius:12px; padding:16px 20px; margin:0 16px 16px; }
        .ri-q-label { font-size:12px; color:#4f6ef7; font-weight:700; margin-bottom:8px; }
        .ri-q-text { font-size:16px; color:#fff; line-height:1.6; font-weight:500; }
        .ri-cam-video { width:100%; height:100%; object-fit:cover; display:block; transform:scaleX(-1); min-height:180px; }
        .ri-cam-panel { border:2px solid transparent; transition:border-color .15s, box-shadow .15s; }
        .ri-cam-panel.mic-on { border-color:#22c55e !important; box-shadow:0 0 14px rgba(34,197,94,.4); }
        .ri-answer-input { width:calc(100% - 32px); margin:0 16px 16px; background:#0f1220; border:1.5px solid rgba(255,255,255,.1); border-radius:10px; padding:12px 14px; color:#fff; font-size:14px; resize:none; min-height:80px; font-family:inherit; }
        .ri-answer-input:focus { border-color:#4f6ef7; outline:none; }
        .ri-progress { height:4px; background:#1a1d2e; }
        .ri-progress-bar { height:100%; background:linear-gradient(90deg,#4f6ef7,#10b981); transition:width .4s; }
        .ri-result-item { background:#1a1d2e; border-radius:10px; padding:14px; margin-bottom:12px; }
        .ri-result-q { font-size:13px; color:#4f6ef7; margin-bottom:6px; font-weight:600; }
        .ri-result-a { font-size:13px; color:rgba(255,255,255,.7); line-height:1.5; }
        .face-badge { position:absolute; bottom:8px; left:50%; transform:translateX(-50%); display:flex; align-items:center; gap:5px; padding:4px 10px; border-radius:99px; font-size:11px; font-weight:600; white-space:nowrap; backdrop-filter:blur(6px); }
        .face-badge.detecting { background:rgba(245,158,11,.85); color:#fff; }
        .face-badge.detected  { background:rgba(16,185,129,.85); color:#fff; }
        .face-badge.lost      { background:rgba(239,68,68,.85);  color:#fff; }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.4} }
        .face-dot { width:7px; height:7px; border-radius:50%; background:currentColor; animation:blink 1.2s infinite; }
      `}</style>

      {/* 상단 */}
      <div className="ri-header">
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>🎯 실전 면접</div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,.4)', marginTop: 2 }}>{resume.companyName} · {resume.jobTitle}</div>
        </div>
        {phase === PHASE.INTERVIEW && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,.4)' }}>총 진행 시간</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', fontFamily: 'monospace' }}>{fmtTime(totalSec)}</div>
            </div>
            <div style={{ width: 1, height: 32, background: 'rgba(255,255,255,.08)' }} />
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>Q {qIndex + 1} / {QUESTIONS.length}</div>
          </div>
        )}
        <button onClick={() => setExitConfirm(true)} style={{ background: '#ef4444', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 18px', font: 'inherit', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>나가기</button>
      </div>

      {/* 진행바 */}
      {phase === PHASE.INTERVIEW && (
        <div className="ri-progress">
          <div className="ri-progress-bar" style={{ width: `${((qIndex) / QUESTIONS.length) * 100}%` }} />
        </div>
      )}

      {/* 인트로 */}
      {phase === PHASE.INTRO && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 20 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 56, marginBottom: 16 }}>🎯</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', marginBottom: 10 }}>실전 면접 안내</div>
            <div style={{ fontSize: 14, color: 'rgba(255,255,255,.5)', lineHeight: 1.8, maxWidth: 400 }}>
              각 질문당 <b style={{ color: '#fff' }}>{Q_LIMIT}초</b>의 답변 시간이 주어집니다.<br />
              시간이 지나면 자동으로 다음 질문으로 넘어갑니다.<br />
              총 <b style={{ color: '#fff' }}>{QUESTIONS.length}개</b>의 질문이 준비되어 있습니다.
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={() => navigate('/resume')} style={{ background: 'transparent', color: 'rgba(255,255,255,.5)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '12px 24px', font: 'inherit', cursor: 'pointer', fontSize: 14 }}>취소</button>
            <button onClick={() => setPhase(PHASE.INTERVIEW)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 32px', font: 'inherit', fontWeight: 700, cursor: 'pointer', fontSize: 15 }}>면접 시작</button>
          </div>
        </div>
      )}

      {/* 면접 진행 */}
      {phase === PHASE.INTERVIEW && (
        <div className="ri-body">
          {/* 왼쪽 - AI 면접관 + 질문 */}
          <div className="ri-left">
            <div className="ri-panel" style={{ flex: 1 }}>
              <div className="ri-panel-title">🤖 AI 면접관</div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 28 }}>
                <div style={{ width: 90, height: 90, borderRadius: '50%', background: 'linear-gradient(135deg,#4f6ef7,#10b981)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 44 }}>🤖</div>
              </div>
              <div className="ri-q-bubble">
                <div className="ri-q-label">Q{qIndex + 1}</div>
                <div className="ri-q-text">{currentQ}</div>
              </div>
            </div>
            <div className="ri-panel">
              <div className="ri-panel-title">✍️ 답변 입력</div>
              <textarea
                className="ri-answer-input"
                placeholder="답변을 입력하거나 말씀해 주세요..."
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
              <div style={{ padding: '0 16px 16px', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  onClick={handleNext}
                  style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 24px', font: 'inherit', fontWeight: 600, cursor: 'pointer', fontSize: 14 }}
                >
                  {qIndex + 1 >= QUESTIONS.length ? '면접 종료 →' : '다음 질문 →'}
                </button>
              </div>
            </div>
          </div>

          {/* 오른쪽 - 타이머 + 카메라 */}
          <div className="ri-right">
            <div className="ri-panel">
              <div className="ri-panel-title">⏱ 답변 시간</div>
              <div className="ri-timer-ring">
                <svg width={120} height={120} viewBox="0 0 120 120">
                  <circle cx={60} cy={60} r={r} fill="none" stroke="#1e2540" strokeWidth={10} />
                  <circle
                    cx={60} cy={60} r={r} fill="none" stroke={color} strokeWidth={10}
                    strokeLinecap="round"
                    strokeDasharray={circ}
                    strokeDashoffset={circ * (1 - pct / 100)}
                    transform="rotate(-90 60 60)"
                    style={{ transition: 'stroke-dashoffset .9s, stroke .3s' }}
                  />
                  <text x={60} y={64} textAnchor="middle" dominantBaseline="middle" fill={color} fontSize={22} fontWeight={700} fontFamily="monospace">
                    {fmtTime(remaining)}
                  </text>
                </svg>
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,.4)' }}>남은 시간</div>
              </div>
            </div>

            <div className={`ri-panel ri-cam-panel${micActive ? ' mic-on' : ''}`} style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div className="ri-panel-title">📹 면접자 모습</div>
              <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                <video ref={videoRef} className="ri-cam-video" autoPlay playsInline muted />
                {faceStatus === 'detecting' && (
                  <div className="face-badge detecting"><span className="face-dot"/>얼굴 인식 중...</div>
                )}
                {faceStatus === 'detected' && (
                  <div className="face-badge detected"><span className="face-dot"/>얼굴 인식됨</div>
                )}
                {faceStatus === 'lost' && (
                  <div className="face-badge lost"><span className="face-dot"/>얼굴 감지 안됨</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 결과 화면 */}
      {phase === PHASE.RESULT && (
        <div style={{ flex: 1, overflow: 'auto', padding: '28px 40px' }}>
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 32 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>실전 면접 완료</div>
              <div style={{ fontSize: 14, color: 'rgba(255,255,255,.4)', marginTop: 8 }}>
                {QUESTIONS.length}개 질문 · 총 소요 시간 {fmtTime(totalSec)}
              </div>
            </div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,.5)', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '.05em' }}>답변 요약</div>
            {answers.map((item, i) => (
              <div key={i} className="ri-result-item">
                <div className="ri-result-q">Q{i + 1}. {item.q}</div>
                <div className="ri-result-a">{item.a || '(답변 없음)'}</div>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 12, marginTop: 24, justifyContent: 'center' }}>
              <button onClick={handleExit} style={{ background: 'transparent', color: 'rgba(255,255,255,.6)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '12px 24px', font: 'inherit', fontWeight: 600, cursor: 'pointer' }}>목록으로</button>
              <button onClick={() => navigate(`/resume/${resumeId}/history`)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 28px', font: 'inherit', fontWeight: 600, cursor: 'pointer' }}>기록 보기</button>
            </div>
          </div>
        </div>
      )}

      {/* 나가기 확인 */}
      {exitConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 600 }}>
          <div style={{ background: '#111422', borderRadius: 14, padding: '28px 32px', minWidth: 300, textAlign: 'center', border: '1px solid rgba(255,255,255,.1)' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', marginBottom: 10 }}>면접을 종료하시겠습니까?</div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 24 }}>실전 면접 중 나가면 기록이 저장되지 않습니다.</div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button onClick={() => setExitConfirm(false)} style={{ background: 'transparent', color: 'rgba(255,255,255,.6)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 8, padding: '10px 20px', font: 'inherit', cursor: 'pointer' }}>계속 진행</button>
              <button onClick={handleExit} style={{ background: '#ef4444', color: '#fff', border: 'none', borderRadius: 8, padding: '10px 20px', font: 'inherit', fontWeight: 600, cursor: 'pointer' }}>나가기</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
