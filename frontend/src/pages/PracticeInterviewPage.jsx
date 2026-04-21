import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import toast from 'react-hot-toast'

// 더미 질문 데이터 (실제로는 AI API 연동)
const generateQuestions = (resume) => [
  { id: 1, question: `${resume?.companyName || '해당 기업'}에 지원하게 된 계기는 무엇인가요?` },
  { id: 2, question: `${resume?.jobTitle || '해당 직무'}에서 본인의 강점은 무엇이라고 생각하시나요?` },
  { id: 3, question: '가장 어려웠던 프로젝트 경험과 그 과정에서 배운 점을 말씀해주세요.' },
  { id: 4, question: '팀원과 갈등이 생겼을 때 어떻게 해결하셨나요? 구체적인 사례로 말씀해주세요.' },
  { id: 5, question: '5년 후 본인의 모습은 어떠할 것 같나요?' },
  { id: 6, question: '최근 해당 산업의 트렌드나 이슈 중 관심 있는 것이 있다면 말씀해주세요.' },
]

const FEEDBACK_TEMPLATES = [
  '답변이 구체적이고 명확했습니다. 특히 경험을 사례로 들어 설명한 부분이 좋았습니다.',
  '핵심을 잘 짚었으나 조금 더 구체적인 수치나 성과를 언급하면 더욱 인상적인 답변이 될 것입니다.',
  '논리적인 구성이 좋았습니다. STAR 기법(상황-과제-행동-결과)을 활용하면 더욱 체계적으로 전달할 수 있습니다.',
  '자신감 있는 답변이었습니다. 다만 답변 시간을 조금 더 활용하여 깊이를 더하면 좋을 것 같습니다.',
]

const PHASE = { QUESTION: 'question', RECORDING: 'recording', FEEDBACK: 'feedback', DONE: 'done' }

export default function PracticeInterviewPage() {
  const navigate = useNavigate()
  const { resumeId } = useParams()
  const { getResume, addInterviewRecord } = useResumeStore()
  const resume = getResume(resumeId)

  const questions = generateQuestions(resume)

  const [phase, setPhase]               = useState(PHASE.QUESTION)   // 현재 단계
  const [qIdx, setQIdx]                  = useState(0)                 // 질문 인덱스
  const [timer, setTimer]                = useState(0)                  // 답변 타이머 (초)
  const [totalTime, setTotalTime]        = useState(0)                  // 총 면접 시간
  const [answer, setAnswer]              = useState('')
  const [feedback, setFeedback]          = useState('')
  const [logOpen, setLogOpen]            = useState(false)
  const [exitConfirm, setExitConfirm]    = useState(false)
  const [log, setLog]                    = useState([])                 // 면접 로그

  const timerRef      = useRef(null)
  const totalTimerRef = useRef(null)
  const videoRef      = useRef(null)
  const streamRef     = useRef(null)

  const currentQ = questions[qIdx]

  // 총 면접 시간 타이머
  useEffect(() => {
    totalTimerRef.current = setInterval(() => setTotalTime((t) => t + 1), 1000)
    return () => clearInterval(totalTimerRef.current)
  }, [])

  // 카메라 시작
  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true, audio: false })
      .then((stream) => {
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      })
      .catch(() => {})
    return () => streamRef.current?.getTracks().forEach((t) => t.stop())
  }, [])

  // 답변 타이머
  useEffect(() => {
    if (phase === PHASE.RECORDING) {
      setTimer(0)
      timerRef.current = setInterval(() => setTimer((t) => t + 1), 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [phase, qIdx])

  const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  // 답변 시작
  const startAnswer = () => {
    setAnswer('')
    setPhase(PHASE.RECORDING)
  }

  // 답변 제출 → 피드백
  const submitAnswer = useCallback(() => {
    if (!answer.trim()) { toast.error('답변을 입력해주세요'); return }
    const fb = FEEDBACK_TEMPLATES[qIdx % FEEDBACK_TEMPLATES.length]
    setFeedback(fb)
    setLog((prev) => [...prev, { question: currentQ.question, answer, feedback: fb, time: timer }])
    setPhase(PHASE.FEEDBACK)
  }, [answer, qIdx, currentQ, timer])

  // 다음 질문
  const nextQuestion = () => {
    if (qIdx + 1 >= questions.length) {
      finishInterview()
      return
    }
    setQIdx((i) => i + 1)
    setAnswer('')
    setFeedback('')
    setPhase(PHASE.QUESTION)
  }

  // 면접 종료
  const finishInterview = () => {
    clearInterval(totalTimerRef.current)
    if (resumeId) {
      addInterviewRecord(resumeId, {
        type: 'practice',
        totalTime,
        questionCount: log.length,
        log,
      })
    }
    navigate('/resume')
    toast.success('연습면접이 완료되었습니다!')
  }

  if (!resume) return <div style={{ padding: 40 }}>자기소개서를 찾을 수 없습니다.</div>

  return (
    <div className="pi-page">
      {/* ── 왼쪽 사이드바 ── */}
      <aside className="pi-sidebar">
        <div className="pi-sidebar-logo">AI 면접 도우미</div>
        <nav className="pi-nav">
          <button className="pi-nav-item" onClick={() => { setExitConfirm(true) }}>🏠 대시보드</button>
          <button className="pi-nav-item" onClick={() => navigate('/resume')}>📄 자기소개서</button>
          <button className="pi-nav-item active">🎓 연습면접</button>
          <button className="pi-nav-item" onClick={() => navigate('/history')}>📋 면접 이력</button>
        </nav>
        <div className="pi-sidebar-footer">
          <button className="pi-nav-item" onClick={() => navigate('/settings')}>⚙️ 설정</button>
          <button className="pi-nav-item danger" onClick={() => setExitConfirm(true)}>🚪 로그아웃</button>
        </div>
      </aside>

      {/* ── 메인 ── */}
      <main className="pi-main">
        {/* 상단 바 */}
        <div className="pi-topbar">
          <div className="pi-topbar-left">
            <span className="pi-badge practice">🎓 연습면접</span>
            <span className="pi-resume-name">{resume.title}</span>
          </div>
          <div className="pi-topbar-right">
            <div className="pi-total-timer">⏱ {fmt(totalTime)}</div>
            <button className="btn btn-outline btn-sm" onClick={() => setExitConfirm(true)}>나가기</button>
          </div>
        </div>

        {/* 콘텐츠 */}
        <div className="pi-content">
          {/* AI 면접관 영역 */}
          <div className="pi-interviewer-zone">
            {/* AI 면접관 */}
            <div className="pi-ai-face">
              <div className="pi-ai-avatar">
                {phase === PHASE.QUESTION && <div className="pi-ai-speaking" />}
                {phase === PHASE.FEEDBACK && <div className="pi-ai-thinking" />}
                <span className="pi-ai-emoji">
                  {phase === PHASE.FEEDBACK ? '💭' : phase === PHASE.RECORDING ? '👂' : '🤖'}
                </span>
              </div>
              <p className="pi-ai-label">AI 면접관</p>
            </div>

            {/* 진행 상태 */}
            <div className="pi-progress-bar">
              {questions.map((_, i) => (
                <div
                  key={i}
                  className={`pi-progress-dot ${i < qIdx ? 'done' : i === qIdx ? 'current' : ''}`}
                />
              ))}
              <span className="pi-progress-text">{qIdx + 1} / {questions.length}</span>
            </div>

            {/* 면접자 카메라 */}
            <div className="pi-camera-box">
              <video ref={videoRef} autoPlay muted playsInline className="pi-video" />
              <div className="pi-camera-label">면접자</div>
              {phase === PHASE.RECORDING && (
                <div className="pi-rec-badge">● REC {fmt(timer)}</div>
              )}
            </div>
          </div>

          {/* 피드백 / 질문 패널 */}
          <div className="pi-panel">
            {/* 질문 */}
            <div className="pi-question-box">
              <div className="pi-question-num">Q{qIdx + 1}.</div>
              <p className="pi-question-text">{currentQ.question}</p>
            </div>

            {/* 단계별 UI */}
            {phase === PHASE.QUESTION && (
              <div className="pi-phase-question">
                <p className="pi-phase-hint">질문을 확인하고 준비가 되면 답변을 시작하세요</p>
                <button className="btn btn-primary btn-lg pi-action-btn" onClick={startAnswer}>
                  🎙️ 답변 시작
                </button>
              </div>
            )}

            {phase === PHASE.RECORDING && (
              <div className="pi-phase-recording">
                <div className="pi-timer-ring">
                  <span>{fmt(timer)}</span>
                  <small>답변 시간</small>
                </div>
                <textarea
                  className="pi-answer-area"
                  placeholder="답변을 입력하거나 음성으로 말씀해주세요..."
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                />
                <button
                  className="btn btn-primary btn-lg pi-action-btn"
                  onClick={submitAnswer}
                  disabled={!answer.trim()}
                >
                  ✅ 답변 완료
                </button>
              </div>
            )}

            {phase === PHASE.FEEDBACK && (
              <div className="pi-phase-feedback">
                <div className="pi-feedback-box">
                  <div className="pi-feedback-header">
                    <span>🤖 AI 면접관 피드백</span>
                  </div>
                  <p className="pi-feedback-text">{feedback}</p>
                </div>
                <div className="pi-my-answer">
                  <strong>내 답변:</strong>
                  <p>{answer}</p>
                </div>
                <button
                  className="btn btn-primary btn-lg pi-action-btn"
                  onClick={nextQuestion}
                >
                  {qIdx + 1 >= questions.length ? '🏁 면접 완료' : '➡️ 다음 질문'}
                </button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* ── 오른쪽 로그 패널 ── */}
      <aside className={`pi-log-panel ${logOpen ? 'open' : ''}`}>
        <button className="pi-log-toggle" onClick={() => setLogOpen(!logOpen)}>
          {logOpen ? '›' : '‹'}
          <span className="pi-log-toggle-label">면접 로그</span>
        </button>
        <div className="pi-log-content">
          <h4 className="pi-log-title">📋 면접 로그</h4>
          {log.length === 0 ? (
            <p className="pi-log-empty">아직 진행된 질문이 없습니다</p>
          ) : (
            log.map((item, i) => (
              <div key={i} className="pi-log-item">
                <div className="pi-log-q">Q{i + 1}. {item.question}</div>
                <div className="pi-log-a">{item.answer}</div>
                <div className="pi-log-f">💬 {item.feedback}</div>
                <div className="pi-log-time">답변 시간: {fmt(item.time)}</div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* 나가기 확인 모달 */}
      {exitConfirm && (
        <div className="modal-overlay" onClick={() => setExitConfirm(false)}>
          <div className="modal-box" style={{ maxWidth: 360 }} onClick={(e) => e.stopPropagation()}>
            <h3 style={{ fontWeight: 700, fontSize: 18 }}>면접을 종료하시겠습니까?</h3>
            <p style={{ color: 'var(--text-secondary)', marginTop: 8, fontSize: 14 }}>
              지금까지의 면접 기록은 저장됩니다.
            </p>
            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={() => setExitConfirm(false)}>계속하기</button>
              <button className="btn btn-danger" onClick={finishInterview}>종료</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .pi-page {
          display: flex;
          height: 100vh;
          overflow: hidden;
          position: fixed;
          inset: 0;
          background: #0F1117;
          color: #fff;
          font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
          z-index: 500;
        }

        /* 사이드바 */
        .pi-sidebar {
          width: 200px;
          flex-shrink: 0;
          background: #1A1D2E;
          display: flex;
          flex-direction: column;
          padding: 16px 0;
          border-right: 1px solid rgba(255,255,255,.06);
        }
        .pi-sidebar-logo {
          padding: 10px 20px 20px;
          font-size: 13px;
          font-weight: 700;
          color: rgba(255,255,255,.6);
          border-bottom: 1px solid rgba(255,255,255,.06);
          margin-bottom: 12px;
        }
        .pi-nav { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 0 10px; }
        .pi-nav-item {
          padding: 10px 12px;
          border-radius: 8px;
          font-size: 13px;
          color: rgba(255,255,255,.5);
          background: none;
          border: none;
          cursor: pointer;
          text-align: left;
          transition: all 0.15s;
        }
        .pi-nav-item:hover { background: rgba(255,255,255,.06); color: rgba(255,255,255,.9); }
        .pi-nav-item.active { background: rgba(79,110,247,.2); color: #6B8EFF; font-weight: 600; }
        .pi-nav-item.danger:hover { color: #F87171; }
        .pi-sidebar-footer { padding: 0 10px 10px; border-top: 1px solid rgba(255,255,255,.06); padding-top: 10px; }

        /* 메인 */
        .pi-main {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-width: 0;
        }

        .pi-topbar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 24px;
          background: #1A1D2E;
          border-bottom: 1px solid rgba(255,255,255,.06);
          flex-shrink: 0;
        }
        .pi-topbar-left { display: flex; align-items: center; gap: 12px; }
        .pi-topbar-right { display: flex; align-items: center; gap: 12px; }
        .pi-badge { font-size: 12px; padding: 4px 12px; border-radius: 99px; font-weight: 600; }
        .pi-badge.practice { background: rgba(16,185,129,.2); color: #34D399; }
        .pi-resume-name { font-size: 14px; color: rgba(255,255,255,.6); }
        .pi-total-timer { font-size: 16px; font-weight: 700; color: #6B8EFF; font-variant-numeric: tabular-nums; }
        .pi-total-timer::before { content: ''; }

        .pi-content {
          flex: 1;
          display: grid;
          grid-template-columns: 1fr 1.4fr;
          gap: 0;
          overflow: hidden;
        }

        /* AI 면접관 영역 */
        .pi-interviewer-zone {
          background: #13151F;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: space-between;
          padding: 32px 24px;
          border-right: 1px solid rgba(255,255,255,.06);
          gap: 20px;
        }

        .pi-ai-face { display: flex; flex-direction: column; align-items: center; gap: 12px; }
        .pi-ai-avatar {
          width: 140px; height: 140px;
          border-radius: 50%;
          background: linear-gradient(135deg, #2A2F4A, #1E2235);
          border: 3px solid rgba(107,142,255,.3);
          display: flex;
          align-items: center;
          justify-content: center;
          position: relative;
          overflow: hidden;
        }
        .pi-ai-speaking {
          position: absolute;
          inset: -4px;
          border-radius: 50%;
          border: 3px solid transparent;
          border-top-color: #6B8EFF;
          animation: spin 1.5s linear infinite;
        }
        .pi-ai-thinking {
          position: absolute;
          inset: -4px;
          border-radius: 50%;
          border: 3px solid #34D399;
          animation: pulse-ring 1.5s ease-in-out infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse-ring { 0%,100% { opacity: .2; transform: scale(.95); } 50% { opacity: 1; transform: scale(1.05); } }
        .pi-ai-emoji { font-size: 56px; }
        .pi-ai-label { font-size: 13px; color: rgba(255,255,255,.4); }

        .pi-progress-bar { display: flex; align-items: center; gap: 8px; }
        .pi-progress-dot {
          width: 10px; height: 10px;
          border-radius: 50%;
          background: rgba(255,255,255,.15);
          transition: all 0.3s;
        }
        .pi-progress-dot.done { background: #34D399; }
        .pi-progress-dot.current { background: #6B8EFF; transform: scale(1.3); }
        .pi-progress-text { font-size: 12px; color: rgba(255,255,255,.4); margin-left: 4px; }

        .pi-camera-box {
          width: 200px; height: 140px;
          border-radius: 12px;
          overflow: hidden;
          background: #000;
          border: 2px solid rgba(255,255,255,.1);
          position: relative;
        }
        .pi-video { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
        .pi-camera-label {
          position: absolute; bottom: 8px; left: 10px;
          font-size: 11px; color: rgba(255,255,255,.6);
          background: rgba(0,0,0,.5); padding: 2px 8px; border-radius: 4px;
        }
        .pi-rec-badge {
          position: absolute; top: 8px; right: 8px;
          font-size: 11px; color: #F87171; font-weight: 600;
          background: rgba(0,0,0,.6); padding: 3px 8px; border-radius: 4px;
          animation: blink 1s ease-in-out infinite;
        }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: .3; } }

        /* 패널 */
        .pi-panel {
          display: flex;
          flex-direction: column;
          padding: 28px;
          overflow-y: auto;
          gap: 20px;
          background: #0F1117;
        }

        .pi-question-box {
          background: #1A1D2E;
          border-radius: 12px;
          padding: 20px;
          border-left: 4px solid #6B8EFF;
        }
        .pi-question-num { font-size: 13px; font-weight: 700; color: #6B8EFF; margin-bottom: 8px; }
        .pi-question-text { font-size: 16px; line-height: 1.6; font-weight: 500; }

        .pi-phase-question, .pi-phase-recording, .pi-phase-feedback { display: flex; flex-direction: column; gap: 16px; }
        .pi-phase-hint { font-size: 14px; color: rgba(255,255,255,.4); }

        .pi-timer-ring {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 16px;
          background: rgba(107,142,255,.1);
          border-radius: 12px;
          border: 1px solid rgba(107,142,255,.2);
        }
        .pi-timer-ring span { font-size: 28px; font-weight: 700; color: #6B8EFF; font-variant-numeric: tabular-nums; }
        .pi-timer-ring small { font-size: 12px; color: rgba(255,255,255,.4); }

        .pi-answer-area {
          width: 100%;
          min-height: 120px;
          background: #1A1D2E;
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 10px;
          padding: 14px;
          color: #fff;
          font-size: 14px;
          line-height: 1.6;
          resize: vertical;
        }
        .pi-answer-area:focus { border-color: #6B8EFF; outline: none; }
        .pi-answer-area::placeholder { color: rgba(255,255,255,.25); }

        .pi-action-btn { width: 100%; justify-content: center; }
        .pi-action-btn.btn-primary {
          background: linear-gradient(135deg, #4F6EF7, #7B5CF7);
          border: none;
          font-size: 15px;
          padding: 14px;
        }
        .pi-action-btn.btn-primary:hover { filter: brightness(1.1); }
        .pi-action-btn:disabled { opacity: .4; pointer-events: none; }

        .pi-feedback-box {
          background: linear-gradient(135deg, rgba(16,185,129,.1), rgba(52,211,153,.05));
          border: 1px solid rgba(16,185,129,.3);
          border-radius: 12px;
          overflow: hidden;
        }
        .pi-feedback-header {
          padding: 10px 16px;
          font-size: 13px;
          font-weight: 700;
          color: #34D399;
          background: rgba(16,185,129,.1);
          border-bottom: 1px solid rgba(16,185,129,.2);
        }
        .pi-feedback-text { padding: 14px 16px; font-size: 14px; line-height: 1.7; color: rgba(255,255,255,.85); }

        .pi-my-answer {
          background: rgba(255,255,255,.04);
          border-radius: 10px;
          padding: 14px;
          font-size: 13px;
          color: rgba(255,255,255,.5);
          line-height: 1.6;
        }
        .pi-my-answer strong { color: rgba(255,255,255,.7); display: block; margin-bottom: 6px; }

        /* 로그 패널 */
        .pi-log-panel {
          width: 48px;
          flex-shrink: 0;
          background: #1A1D2E;
          border-left: 1px solid rgba(255,255,255,.06);
          position: relative;
          overflow: hidden;
          transition: width 0.3s ease;
        }
        .pi-log-panel.open { width: 300px; }
        .pi-log-toggle {
          position: absolute;
          top: 50%;
          transform: translateY(-50%);
          left: 0;
          width: 48px;
          height: 80px;
          background: none;
          border: none;
          cursor: pointer;
          color: rgba(255,255,255,.4);
          font-size: 18px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 4px;
          z-index: 1;
        }
        .pi-log-toggle:hover { color: rgba(255,255,255,.8); }
        .pi-log-toggle-label { font-size: 10px; writing-mode: vertical-rl; }
        .pi-log-content { padding: 60px 16px 16px 52px; height: 100%; overflow-y: auto; }
        .pi-log-title { font-size: 14px; font-weight: 700; margin-bottom: 16px; color: rgba(255,255,255,.8); }
        .pi-log-empty { font-size: 13px; color: rgba(255,255,255,.3); }
        .pi-log-item {
          margin-bottom: 20px;
          padding-bottom: 20px;
          border-bottom: 1px solid rgba(255,255,255,.06);
        }
        .pi-log-q { font-size: 12px; font-weight: 600; color: #6B8EFF; margin-bottom: 6px; line-height: 1.5; }
        .pi-log-a { font-size: 12px; color: rgba(255,255,255,.6); margin-bottom: 8px; line-height: 1.5; }
        .pi-log-f { font-size: 11px; color: #34D399; margin-bottom: 4px; line-height: 1.5; }
        .pi-log-time { font-size: 10px; color: rgba(255,255,255,.3); }

        .modal-overlay {
          position: fixed; inset: 0;
          background: rgba(0,0,0,.7);
          display: flex; align-items: center; justify-content: center;
          z-index: 2000;
        }
        .modal-box {
          background: #1A1D2E;
          color: #fff;
          border-radius: 14px;
          padding: 28px;
          width: 90%;
          animation: modalIn .2s ease;
          border: 1px solid rgba(255,255,255,.1);
        }
        @keyframes modalIn { from { opacity: 0; transform: scale(.95); } to { opacity: 1; transform: scale(1); } }
      `}</style>
    </div>
  )
}
