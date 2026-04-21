import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'

// 면접 단계
const PHASE = { WAITING: 'waiting', QUESTION: 'question', ANSWERING: 'answering', FEEDBACK: 'feedback', DONE: 'done' }

// 샘플 질문 목록 (실제 서비스에서는 AI API 연동)
const SAMPLE_QUESTIONS = [
  '자기소개를 간략하게 해주세요.',
  '해당 직무에 지원하게 된 이유가 무엇인가요?',
  '본인의 가장 큰 강점과 약점은 무엇인가요?',
  '이전 직장(또는 프로젝트)에서 가장 힘들었던 상황과 어떻게 극복했는지 말씀해 주세요.',
  '5년 후 본인의 모습을 어떻게 생각하시나요?',
  '팀원과의 갈등이 생겼을 때 어떻게 해결하시나요?',
  '입사 후 가장 먼저 하고 싶은 일은 무엇인가요?',
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

  const [phase, setPhase] = useState(PHASE.WAITING)
  const [qIndex, setQIndex] = useState(0)
  const [answer, setAnswer] = useState('')
  const [log, setLog] = useState([])          // { q, a, feedback }
  const [logOpen, setLogOpen] = useState(false)
  const [totalSec, setTotalSec] = useState(0)
  const [answerSec, setAnswerSec] = useState(0)
  const [exitConfirm, setExitConfirm] = useState(false)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const totalTimer = useRef(null)
  const answerTimer = useRef(null)

  const questions = SAMPLE_QUESTIONS.slice(0, 5)
  const currentQ = questions[qIndex]

  // 카메라 시작
  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true, audio: false })
      .then((s) => { streamRef.current = s; if (videoRef.current) videoRef.current.srcObject = s })
      .catch(() => {})
    return () => { streamRef.current?.getTracks().forEach((t) => t.stop()) }
  }, [])

  // 총 면접 타이머
  useEffect(() => {
    if (phase === PHASE.WAITING || phase === PHASE.DONE) return
    totalTimer.current = setInterval(() => setTotalSec((p) => p + 1), 1000)
    return () => clearInterval(totalTimer.current)
  }, [phase])

  // 답변 타이머
  useEffect(() => {
    clearInterval(answerTimer.current)
    if (phase === PHASE.ANSWERING) {
      setAnswerSec(0)
      answerTimer.current = setInterval(() => setAnswerSec((p) => p + 1), 1000)
    }
    return () => clearInterval(answerTimer.current)
  }, [phase])

  const fmtTime = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`

  const startInterview = () => setPhase(PHASE.QUESTION)

  const startAnswer = () => { setPhase(PHASE.ANSWERING); setAnswer('') }

  const submitAnswer = () => {
    clearInterval(answerTimer.current)
    setPhase(PHASE.FEEDBACK)
  }

  const nextQuestion = () => {
    const feedback = SAMPLE_FEEDBACK[Math.floor(Math.random() * SAMPLE_FEEDBACK.length)]
    setLog((prev) => [...prev, { q: currentQ, a: answer, feedback }])
    if (qIndex + 1 >= questions.length) {
      setPhase(PHASE.DONE)
      addInterviewRecord(resumeId, {
        type: 'practice',
        duration: totalSec,
        questions: questions.map((q) => ({ question: q })),
      })
    } else {
      setQIndex((p) => p + 1)
      setPhase(PHASE.QUESTION)
    }
  }

  const handleExit = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    navigate('/resume')
  }

  if (!resume) return <div style={{ padding: 40, textAlign: 'center' }}>자기소개서를 찾을 수 없습니다. <button onClick={() => navigate('/resume')} className="btn btn-primary" style={{ marginLeft: 10 }}>목록으로</button></div>

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#0f1117', display: 'flex', zIndex: 500 }}>
      <style>{`
        .pi-sidebar { width:200px; background:#1a1d2e; display:flex; flex-direction:column; padding:20px 0; flex-shrink:0; }
        .pi-sidebar-title { font-size:13px; font-weight:700; color:rgba(255,255,255,.4); padding:0 16px 12px; text-transform:uppercase; letter-spacing:.05em; }
        .pi-nav-item { padding:10px 16px; font-size:13px; color:rgba(255,255,255,.5); cursor:default; }
        .pi-nav-item.active { background:rgba(79,110,247,.2); color:#4f6ef7; border-left:3px solid #4f6ef7; }
        .pi-center { flex:1; display:flex; flex-direction:column; overflow:hidden; }
        .pi-top { display:flex; align-items:center; justify-content:space-between; padding:14px 20px; background:#1a1d2e; border-bottom:1px solid rgba(255,255,255,.06); }
        .pi-top-title { font-size:16px; font-weight:700; color:#fff; }
        .pi-body { flex:1; display:flex; gap:16px; padding:16px; overflow:hidden; }
        .pi-interviewer { flex:3; background:#1a1d2e; border-radius:12px; display:flex; flex-direction:column; overflow:hidden; position:relative; }
        .pi-right { flex:2; display:flex; flex-direction:column; gap:12px; min-width:0; }
        .pi-timer-box { background:#1a1d2e; border-radius:10px; padding:12px 16px; display:flex; align-items:center; justify-content:space-between; }
        .pi-timer-label { font-size:12px; color:rgba(255,255,255,.4); }
        .pi-timer-val { font-size:20px; font-weight:700; color:#fff; font-variant-numeric:tabular-nums; font-family:monospace; }
        .pi-cam-box { flex:1; background:#111827; border-radius:10px; overflow:hidden; position:relative; }
        .pi-cam-label { position:absolute; top:8px; left:10px; font-size:11px; color:rgba(255,255,255,.5); background:rgba(0,0,0,.4); padding:2px 8px; border-radius:99px; }
        .pi-cam-video { width:100%; height:100%; object-fit:cover; display:block; transform:scaleX(-1); }
        .pi-phase-box { background:#1e2235; border-radius:12px; padding:20px; margin:16px; flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; }
        .pi-q-label { font-size:13px; color:rgba(255,255,255,.4); margin-bottom:10px; }
        .pi-q-text { font-size:18px; font-weight:600; color:#fff; line-height:1.5; margin-bottom:20px; }
        .pi-answer-area { width:100%; background:#111827; border:1.5px solid rgba(255,255,255,.1); border-radius:10px; padding:14px; color:#fff; font-size:14px; resize:none; min-height:100px; font-family:inherit; }
        .pi-answer-area:focus { border-color:#4f6ef7; outline:none; }
        .pi-feedback-box { background:#1e3a1e; border:1.5px solid #22c55e; border-radius:10px; padding:16px; margin:0 16px 16px; }
        .pi-feedback-label { font-size:12px; font-weight:700; color:#22c55e; margin-bottom:8px; }
        .pi-feedback-text { font-size:14px; color:rgba(255,255,255,.85); line-height:1.6; }
        .pi-log-panel { width:0; background:#1a1d2e; overflow:hidden; transition:width .25s; flex-shrink:0; }
        .pi-log-panel.open { width:280px; border-left:1px solid rgba(255,255,255,.06); }
        .pi-log-inner { width:280px; padding:16px; height:100%; overflow-y:auto; }
        .pi-log-title { font-size:13px; font-weight:700; color:rgba(255,255,255,.5); margin-bottom:12px; }
        .pi-log-item { background:#232742; border-radius:8px; padding:12px; margin-bottom:10px; font-size:12px; }
        .pi-log-q { color:#4f6ef7; margin-bottom:6px; font-weight:600; }
        .pi-log-a { color:rgba(255,255,255,.7); margin-bottom:6px; }
        .pi-log-f { color:#22c55e; }
        .pi-progress { height:3px; background:#1a1d2e; }
        .pi-progress-bar { height:100%; background:linear-gradient(90deg,#4f6ef7,#10b981); transition:width .4s; }
        .pi-btn { padding:10px 24px; border-radius:8px; font-size:14px; font-weight:600; border:none; cursor:pointer; transition:background .15s; }
        .pi-btn-primary { background:#4f6ef7; color:#fff; }
        .pi-btn-primary:hover { background:#3a57e8; }
        .pi-btn-outline { background:transparent; color:rgba(255,255,255,.6); border:1.5px solid rgba(255,255,255,.15); }
        .pi-btn-outline:hover { border-color:#fff; color:#fff; }
        .pi-btn-green { background:#10b981; color:#fff; }
        .pi-btn-green:hover { background:#059669; }
        .pi-btn-danger { background:#ef4444; color:#fff; }
      `}</style>

      {/* 왼쪽 사이드바 */}
      <div className="pi-sidebar">
        <div className="pi-sidebar-title">화면 조회 리스트</div>
        {['대시보드', '자기소개서 작성', '면접 이력'].map((t) => (
          <div key={t} className="pi-nav-item">{t}</div>
        ))}
        <div style={{ flex: 1 }} />
        <div className="pi-nav-item" style={{ borderTop: '1px solid rgba(255,255,255,.06)', paddingTop: 16 }}>개인정보</div>
        <div className="pi-nav-item">설정</div>
        <div className="pi-nav-item">로그아웃</div>
      </div>

      {/* 가운데 영역 */}
      <div className="pi-center">
        {/* 상단 바 */}
        <div className="pi-top">
          <div className="pi-top-title">🎓 연습 면접</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>{resume.companyName} · {resume.jobTitle}</span>
            <span style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>Q {qIndex + 1} / {questions.length}</span>
            <button className="pi-btn" style={{ background: '#ef4444', color: '#fff', padding: '6px 16px', fontSize: 13 }} onClick={() => setExitConfirm(true)}>나가기</button>
          </div>
        </div>

        {/* 진행바 */}
        <div className="pi-progress">
          <div className="pi-progress-bar" style={{ width: `${(qIndex / questions.length) * 100}%` }} />
        </div>

        {/* 본체 */}
        <div className="pi-body">
          {/* AI 면접관 패널 */}
          <div className="pi-interviewer">
            <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,.06)', fontSize: 13, color: 'rgba(255,255,255,.5)' }}>
              🤖 AI 면접관
            </div>
            {/* AI 면접관 아바타 */}
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 0 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ width: 100, height: 100, borderRadius: '50%', background: 'linear-gradient(135deg,#4f6ef7,#10b981)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 48, margin: '0 auto 16px' }}>🤖</div>
                <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>AI 면접관</div>
              </div>
            </div>

            {/* 단계별 화면 */}
            <div className="pi-phase-box" style={{ margin: '0 16px 16px' }}>
              {phase === PHASE.WAITING && (
                <>
                  <div style={{ fontSize: 32, marginBottom: 16 }}>🎤</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#fff', marginBottom: 8 }}>연습 면접 준비됨</div>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 20 }}>총 {questions.length}개의 질문이 준비되었습니다</div>
                  <button className="pi-btn pi-btn-primary" onClick={startInterview}>면접 시작</button>
                </>
              )}
              {phase === PHASE.QUESTION && (
                <>
                  <div className="pi-q-label">Q{qIndex + 1}. 질문</div>
                  <div className="pi-q-text">{currentQ}</div>
                  <button className="pi-btn pi-btn-primary" onClick={startAnswer}>답변 시작</button>
                </>
              )}
              {phase === PHASE.ANSWERING && (
                <>
                  <div className="pi-q-label" style={{ marginBottom: 8 }}>Q{qIndex + 1}. {currentQ}</div>
                  <textarea
                    className="pi-answer-area"
                    placeholder="답변을 입력하거나 말씀해 주세요..."
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    autoFocus
                  />
                  <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
                    <button className="pi-btn pi-btn-outline" onClick={() => setPhase(PHASE.QUESTION)}>재시작</button>
                    <button className="pi-btn pi-btn-green" onClick={submitAnswer}>답변 완료</button>
                  </div>
                </>
              )}
              {phase === PHASE.FEEDBACK && (
                <>
                  <div className="pi-q-label">💡 AI 피드백</div>
                  <div style={{ background: '#1e3a1e', border: '1.5px solid #22c55e', borderRadius: 10, padding: 14, marginBottom: 16, textAlign: 'left', width: '100%' }}>
                    <div style={{ fontSize: 12, color: '#22c55e', marginBottom: 6, fontWeight: 700 }}>피드백</div>
                    <div style={{ fontSize: 14, color: 'rgba(255,255,255,.85)', lineHeight: 1.6 }}>
                      {SAMPLE_FEEDBACK[Math.floor(Math.random() * SAMPLE_FEEDBACK.length)]}
                    </div>
                  </div>
                  <button className="pi-btn pi-btn-primary" onClick={nextQuestion}>
                    {qIndex + 1 >= questions.length ? '면접 종료' : '다음 질문 →'}
                  </button>
                </>
              )}
              {phase === PHASE.DONE && (
                <>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>🎉</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 8 }}>면접 완료!</div>
                  <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 20 }}>
                    총 {questions.length}개 질문 · {fmtTime(totalSec)} 소요
                  </div>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button className="pi-btn pi-btn-outline" onClick={handleExit}>목록으로</button>
                    <button className="pi-btn pi-btn-primary" onClick={() => { setPhase(PHASE.WAITING); setQIndex(0); setLog([]); setTotalSec(0) }}>다시 시작</button>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* 오른쪽 패널 */}
          <div className="pi-right">
            {/* 타이머 */}
            <div className="pi-timer-box">
              <div>
                <div className="pi-timer-label">전체 면접 시간</div>
                <div className="pi-timer-val">{fmtTime(totalSec)}</div>
              </div>
              {phase === PHASE.ANSWERING && (
                <div style={{ textAlign: 'right' }}>
                  <div className="pi-timer-label">답변 시간</div>
                  <div className="pi-timer-val" style={{ color: answerSec > 120 ? '#ef4444' : '#10b981' }}>{fmtTime(answerSec)}</div>
                </div>
              )}
            </div>

            {/* 카메라 */}
            <div className="pi-cam-box">
              <div className="pi-cam-label">📹 면접자 모습</div>
              <video ref={videoRef} className="pi-cam-video" autoPlay playsInline muted />
              {!videoRef.current?.srcObject && (
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8 }}>
                  <div style={{ fontSize: 32 }}>📷</div>
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,.4)' }}>카메라 연결 중...</div>
                </div>
              )}
            </div>

            {/* 면접 로그 토글 */}
            <button
              className="pi-btn"
              style={{ background: logOpen ? '#232742' : '#1a1d2e', color: 'rgba(255,255,255,.7)', border: '1px solid rgba(255,255,255,.1)', fontSize: 13 }}
              onClick={() => setLogOpen((p) => !p)}
            >
              {logOpen ? '▶ 로그 닫기' : '◀ 면접 로그'} ({log.length})
            </button>
          </div>
        </div>
      </div>

      {/* 면접 로그 패널 (오른쪽 날개) */}
      <div className={`pi-log-panel${logOpen ? ' open' : ''}`}>
        <div className="pi-log-inner">
          <div className="pi-log-title">📋 면접 로그</div>
          {log.length === 0 && <div style={{ fontSize: 13, color: 'rgba(255,255,255,.3)', textAlign: 'center', marginTop: 40 }}>아직 기록이 없습니다</div>}
          {log.map((item, i) => (
            <div key={i} className="pi-log-item">
              <div className="pi-log-q">Q{i + 1}. {item.q}</div>
              <div className="pi-log-a">A: {item.a || '(답변 없음)'}</div>
              <div className="pi-log-f">💡 {item.feedback}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 나가기 확인 모달 */}
      {exitConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 600 }}>
          <div style={{ background: '#1a1d2e', borderRadius: 14, padding: '28px 32px', minWidth: 300, textAlign: 'center', border: '1px solid rgba(255,255,255,.1)' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', marginBottom: 10 }}>면접을 종료하시겠습니까?</div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 24 }}>진행 중인 내용은 저장되지 않습니다.</div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button className="pi-btn pi-btn-outline" onClick={() => setExitConfirm(false)}>계속 진행</button>
              <button className="pi-btn pi-btn-danger" onClick={handleExit}>종료</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
