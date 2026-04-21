import { useState, useEffect, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import toast from 'react-hot-toast'

const QUESTIONS_TEMPLATE = (resume) => [
  { id: 1, q: `자기소개를 해주세요. ${resume?.companyName || ''}에 지원한 이유도 함께 말씀해주세요.` },
  { id: 2, q: `${resume?.jobTitle || '해당 직무'}에서 본인이 어떤 기여를 할 수 있을지 말씀해주세요.` },
  { id: 3, q: '팀 프로젝트에서 갈등 상황을 경험한 적이 있다면, 어떻게 해결하셨나요?' },
  { id: 4, q: '본인의 단점과 그것을 극복하기 위해 어떤 노력을 하고 있는지 말씀해주세요.' },
  { id: 5, q: '마지막으로 저희 회사에 궁금한 사항이나 하고 싶은 말씀이 있으신가요?' },
]

const ANSWER_LIMIT = 120 // 2분 = 120초

const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

const PHASE = { INTRO: 'intro', ANSWER: 'answer', RESULT: 'result' }

export default function RealInterviewPage() {
  const navigate = useNavigate()
  const { resumeId } = useParams()
  const { getResume, addInterviewRecord } = useResumeStore()
  const resume = getResume(resumeId)

  const questions = QUESTIONS_TEMPLATE(resume)

  const [phase, setPhase]         = useState(PHASE.INTRO)
  const [qIdx, setQIdx]           = useState(0)
  const [answerTimer, setAnswerTimer] = useState(ANSWER_LIMIT)
  const [totalTime, setTotalTime] = useState(0)
  const [answers, setAnswers]     = useState(Array(questions.length).fill(''))
  const [currentAnswer, setCurrentAnswer] = useState('')
  const [exitConfirm, setExitConfirm] = useState(false)

  const timerRef       = useRef(null)
  const totalTimerRef  = useRef(null)
  const videoRef       = useRef(null)
  const streamRef      = useRef(null)

  // 총 타이머
  useEffect(() => {
    if (phase !== PHASE.INTRO) {
      totalTimerRef.current = setInterval(() => setTotalTime((t) => t + 1), 1000)
    }
    return () => clearInterval(totalTimerRef.current)
  }, [phase])

  // 카메라
  useEffect(() => {
    navigator.mediaDevices?.getUserMedia({ video: true, audio: false })
      .then((s) => { streamRef.current = s; if (videoRef.current) videoRef.current.srcObject = s })
      .catch(() => {})
    return () => streamRef.current?.getTracks().forEach((t) => t.stop())
  }, [])

  // 답변 타이머
  useEffect(() => {
    if (phase === PHASE.ANSWER) {
      setAnswerTimer(ANSWER_LIMIT)
      clearInterval(timerRef.current)
      timerRef.current = setInterval(() => {
        setAnswerTimer((t) => {
          if (t <= 1) {
            clearInterval(timerRef.current)
            handleAutoNext()
            return 0
          }
          return t - 1
        })
      }, 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  // eslint-disable-next-line
  }, [phase, qIdx])

  const handleAutoNext = () => {
    const newAnswers = [...answers]
    newAnswers[qIdx] = currentAnswer
    setAnswers(newAnswers)
    setCurrentAnswer('')
    if (qIdx + 1 >= questions.length) {
      finishInterview(newAnswers)
    } else {
      setQIdx((i) => i + 1)
    }
  }

  const handleNextManual = () => {
    clearInterval(timerRef.current)
    const newAnswers = [...answers]
    newAnswers[qIdx] = currentAnswer
    setAnswers(newAnswers)
    setCurrentAnswer('')
    if (qIdx + 1 >= questions.length) {
      finishInterview(newAnswers)
    } else {
      setQIdx((i) => i + 1)
    }
  }

  const finishInterview = (finalAnswers = answers) => {
    clearInterval(totalTimerRef.current)
    clearInterval(timerRef.current)
    if (resumeId) {
      addInterviewRecord(resumeId, {
        type: 'real',
        totalTime,
        questionCount: questions.length,
        log: questions.map((q, i) => ({ question: q.q, answer: finalAnswers[i] || '(무응답)' })),
      })
    }
    setPhase(PHASE.RESULT)
  }

  const timerPct = (answerTimer / ANSWER_LIMIT) * 100
  const timerColor = timerPct > 50 ? '#34D399' : timerPct > 20 ? '#F59E0B' : '#EF4444'

  if (!resume) return <div style={{ padding: 40, color: '#fff' }}>자기소개서를 찾을 수 없습니다.</div>

  return (
    <div className="ri-page">
      {/* ── 인트로 화면 ── */}
      {phase === PHASE.INTRO && (
        <div className="ri-intro">
          <div className="ri-intro-card">
            <div className="ri-intro-icon">💼</div>
            <h2>실전 면접 준비</h2>
            <p className="ri-intro-sub">{resume.title}</p>
            <p className="ri-intro-company">🏢 {resume.companyName} · {resume.jobTitle}</p>
            <div className="ri-intro-rules">
              <div className="ri-rule">⏱ 질문당 최대 {fmt(ANSWER_LIMIT)} 답변시간</div>
              <div className="ri-rule">📋 총 {questions.length}개 질문</div>
              <div className="ri-rule">🎥 카메라와 마이크가 필요합니다</div>
              <div className="ri-rule">🔇 조용한 환경에서 진행하세요</div>
            </div>
            <button
              className="ri-start-btn"
              onClick={() => setPhase(PHASE.ANSWER)}
            >
              면접 시작하기 →
            </button>
            <button className="ri-back-btn" onClick={() => navigate('/resume')}>돌아가기</button>
          </div>
        </div>
      )}

      {/* ── 면접 진행 ── */}
      {phase === PHASE.ANSWER && (
        <div className="ri-interview">
          {/* 상단 바 */}
          <div className="ri-bar">
            <div className="ri-bar-left">
              <span className="ri-badge real">💼 실전면접</span>
              <span className="ri-bar-name">{resume.title}</span>
            </div>
            <div className="ri-bar-center">
              <div className="ri-bar-progress">
                {questions.map((_, i) => (
                  <div key={i} className={`ri-dot ${i < qIdx ? 'done' : i === qIdx ? 'curr' : ''}`} />
                ))}
                <span className="ri-dot-label">{qIdx + 1}/{questions.length}</span>
              </div>
            </div>
            <div className="ri-bar-right">
              <span className="ri-total-time">전체 {fmt(totalTime)}</span>
              <button className="ri-exit-btn" onClick={() => setExitConfirm(true)}>나가기</button>
            </div>
          </div>

          {/* 메인 레이아웃 */}
          <div className="ri-body">
            {/* AI 면접관 */}
            <div className="ri-ai-section">
              <div className="ri-ai-bg">
                <div className="ri-ai-avatar">
                  <span className="ri-ai-emoji">🧑‍💼</span>
                  <div className="ri-ai-ring" />
                </div>
                <p className="ri-ai-name">AI 면접관</p>
                <p className="ri-ai-hint">{resume.companyName} 인사팀</p>
              </div>

              {/* 질문 말풍선 */}
              <div className="ri-speech-bubble">
                <span className="ri-q-label">Q{qIdx + 1}</span>
                <p>{questions[qIdx].q}</p>
              </div>
            </div>

            {/* 면접자 영역 */}
            <div className="ri-candidate-section">
              {/* 타이머 */}
              <div className="ri-timer-box">
                <svg className="ri-timer-svg" viewBox="0 0 100 100">
                  <circle cx="50" cy="50" r="44" fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="8" />
                  <circle
                    cx="50" cy="50" r="44"
                    fill="none" stroke={timerColor} strokeWidth="8"
                    strokeDasharray={`${2 * Math.PI * 44}`}
                    strokeDashoffset={`${2 * Math.PI * 44 * (1 - timerPct / 100)}`}
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.5s' }}
                    transform="rotate(-90 50 50)"
                  />
                </svg>
                <div className="ri-timer-inner">
                  <span className="ri-timer-val" style={{ color: timerColor }}>{fmt(answerTimer)}</span>
                  <small>남은시간</small>
                </div>
              </div>

              {/* 카메라 */}
              <div className="ri-camera">
                <video ref={videoRef} autoPlay muted playsInline className="ri-video" />
                <div className="ri-rec-dot">● LIVE</div>
              </div>

              {/* 답변 입력 */}
              <textarea
                className="ri-answer-input"
                placeholder="답변을 입력하거나 음성으로 말씀해주세요..."
                value={currentAnswer}
                onChange={(e) => setCurrentAnswer(e.target.value)}
              />

              <button className="ri-next-btn" onClick={handleNextManual}>
                {qIdx + 1 >= questions.length ? '면접 완료' : '다음 질문 →'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 결과 화면 ── */}
      {phase === PHASE.RESULT && (
        <div className="ri-result">
          <div className="ri-result-card">
            <div className="ri-result-icon">🎉</div>
            <h2>면접이 완료되었습니다!</h2>
            <p className="ri-result-sub">총 소요시간 <strong>{fmt(totalTime)}</strong></p>

            <div className="ri-result-summary">
              {questions.map((q, i) => (
                <div key={i} className="ri-result-item">
                  <div className="ri-result-q">Q{i + 1}. {q.q}</div>
                  <div className="ri-result-a">{answers[i] || '(무응답)'}</div>
                </div>
              ))}
            </div>

            <div className="ri-result-actions">
              <button className="ri-result-btn primary" onClick={() => navigate('/resume')}>
                목록으로 돌아가기
              </button>
              <button className="ri-result-btn" onClick={() => navigate('/dashboard')}>
                대시보드
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 나가기 확인 */}
      {exitConfirm && (
        <div className="ri-overlay" onClick={() => setExitConfirm(false)}>
          <div className="ri-modal" onClick={(e) => e.stopPropagation()}>
            <h3>면접을 종료하시겠습니까?</h3>
            <p>지금까지의 답변은 저장됩니다.</p>
            <div className="ri-modal-btns">
              <button className="ri-modal-cancel" onClick={() => setExitConfirm(false)}>계속하기</button>
              <button className="ri-modal-exit" onClick={() => finishInterview()}>종료</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .ri-page {
          position: fixed; inset: 0;
          background: #0A0C14;
          color: #fff;
          font-family: 'Pretendard', 'Noto Sans KR', sans-serif;
          z-index: 500;
          overflow: hidden;
        }

        /* 인트로 */
        .ri-intro {
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: radial-gradient(ellipse at center, #1A1F35 0%, #0A0C14 70%);
        }
        .ri-intro-card {
          text-align: center;
          max-width: 480px;
          width: 90%;
          padding: 48px 40px;
          background: rgba(255,255,255,.04);
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 20px;
        }
        .ri-intro-icon { font-size: 52px; margin-bottom: 16px; }
        .ri-intro-card h2 { font-size: 26px; font-weight: 800; margin-bottom: 8px; }
        .ri-intro-sub { color: rgba(255,255,255,.5); font-size: 14px; }
        .ri-intro-company { color: #6B8EFF; font-size: 13px; margin-top: 8px; }
        .ri-intro-rules {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin: 28px 0;
          text-align: left;
        }
        .ri-rule {
          padding: 12px 16px;
          background: rgba(255,255,255,.04);
          border-radius: 8px;
          font-size: 14px;
          color: rgba(255,255,255,.7);
        }
        .ri-start-btn {
          width: 100%;
          padding: 16px;
          background: linear-gradient(135deg, #4F6EF7, #7B5CF7);
          color: #fff;
          border: none;
          border-radius: 12px;
          font-size: 16px;
          font-weight: 700;
          cursor: pointer;
          transition: filter 0.2s;
        }
        .ri-start-btn:hover { filter: brightness(1.1); }
        .ri-back-btn {
          margin-top: 12px;
          background: none;
          border: none;
          color: rgba(255,255,255,.3);
          font-size: 13px;
          cursor: pointer;
        }
        .ri-back-btn:hover { color: rgba(255,255,255,.6); }

        /* 면접 진행 */
        .ri-interview { height: 100%; display: flex; flex-direction: column; }

        .ri-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 28px;
          background: #13151F;
          border-bottom: 1px solid rgba(255,255,255,.06);
          flex-shrink: 0;
          gap: 16px;
        }
        .ri-bar-left, .ri-bar-right { display: flex; align-items: center; gap: 12px; flex: 1; }
        .ri-bar-right { justify-content: flex-end; }
        .ri-bar-center { display: flex; justify-content: center; flex: 1; }
        .ri-badge { font-size: 12px; padding: 4px 12px; border-radius: 99px; font-weight: 700; }
        .ri-badge.real { background: rgba(245,158,11,.2); color: #FCD34D; }
        .ri-bar-name { font-size: 13px; color: rgba(255,255,255,.5); }
        .ri-bar-progress { display: flex; align-items: center; gap: 8px; }
        .ri-dot { width: 12px; height: 12px; border-radius: 50%; background: rgba(255,255,255,.15); transition: all .3s; }
        .ri-dot.done { background: #FCD34D; }
        .ri-dot.curr { background: #fff; transform: scale(1.4); }
        .ri-dot-label { font-size: 12px; color: rgba(255,255,255,.4); margin-left: 4px; }
        .ri-total-time { font-size: 14px; font-weight: 700; color: rgba(255,255,255,.5); }
        .ri-exit-btn {
          padding: 6px 16px; border: 1px solid rgba(255,255,255,.15); border-radius: 8px;
          background: none; color: rgba(255,255,255,.5); font-size: 13px; cursor: pointer;
        }
        .ri-exit-btn:hover { border-color: #EF4444; color: #EF4444; }

        .ri-body {
          flex: 1;
          display: grid;
          grid-template-columns: 1fr 1fr;
          overflow: hidden;
        }

        /* AI 섹션 */
        .ri-ai-section {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 28px;
          padding: 32px;
          background: linear-gradient(135deg, #0F1117, #1A1D2E);
          border-right: 1px solid rgba(255,255,255,.06);
        }
        .ri-ai-bg { display: flex; flex-direction: column; align-items: center; gap: 10px; }
        .ri-ai-avatar {
          width: 160px; height: 160px;
          border-radius: 50%;
          background: linear-gradient(135deg, #1E2235, #2A3050);
          border: 3px solid rgba(245,158,11,.3);
          display: flex; align-items: center; justify-content: center;
          position: relative;
        }
        .ri-ai-emoji { font-size: 70px; }
        .ri-ai-ring {
          position: absolute; inset: -6px;
          border-radius: 50%;
          border: 2px solid rgba(245,158,11,.4);
          animation: pulse-ring 2s ease-in-out infinite;
        }
        @keyframes pulse-ring { 0%,100% { transform: scale(1); opacity: .4; } 50% { transform: scale(1.04); opacity: 1; } }
        .ri-ai-name { font-size: 15px; font-weight: 700; }
        .ri-ai-hint { font-size: 12px; color: rgba(255,255,255,.3); }

        .ri-speech-bubble {
          background: rgba(255,255,255,.06);
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 16px;
          padding: 20px 24px;
          width: 100%;
          max-width: 420px;
          position: relative;
        }
        .ri-q-label {
          font-size: 12px;
          font-weight: 700;
          color: #FCD34D;
          display: block;
          margin-bottom: 10px;
        }
        .ri-speech-bubble p { font-size: 16px; line-height: 1.7; }

        /* 면접자 섹션 */
        .ri-candidate-section {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding: 28px;
          gap: 16px;
          background: #0F1117;
          overflow-y: auto;
        }

        .ri-timer-box {
          width: 100px; height: 100px;
          position: relative; flex-shrink: 0;
        }
        .ri-timer-svg { width: 100%; height: 100%; }
        .ri-timer-inner {
          position: absolute; inset: 0;
          display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        .ri-timer-val { font-size: 18px; font-weight: 800; font-variant-numeric: tabular-nums; }
        .ri-timer-inner small { font-size: 10px; color: rgba(255,255,255,.4); }

        .ri-camera {
          width: 240px; height: 170px;
          border-radius: 12px; overflow: hidden;
          background: #000; border: 2px solid rgba(255,255,255,.1);
          position: relative; flex-shrink: 0;
        }
        .ri-video { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
        .ri-rec-dot {
          position: absolute; top: 8px; right: 10px;
          font-size: 10px; font-weight: 700; color: #EF4444;
          background: rgba(0,0,0,.6); padding: 3px 8px; border-radius: 4px;
          animation: blink 1.2s ease-in-out infinite;
        }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: .2; } }

        .ri-answer-input {
          width: 100%; min-height: 110px;
          background: rgba(255,255,255,.05);
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 12px;
          padding: 14px;
          color: #fff; font-size: 14px; line-height: 1.6;
          resize: vertical;
        }
        .ri-answer-input:focus { border-color: rgba(245,158,11,.4); outline: none; }
        .ri-answer-input::placeholder { color: rgba(255,255,255,.2); }

        .ri-next-btn {
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, #D97706, #F59E0B);
          color: #fff; border: none; border-radius: 12px;
          font-size: 15px; font-weight: 700; cursor: pointer;
          transition: filter .2s;
        }
        .ri-next-btn:hover { filter: brightness(1.1); }

        /* 결과 화면 */
        .ri-result {
          height: 100%;
          display: flex; align-items: center; justify-content: center;
          background: radial-gradient(ellipse at center, #1A1F35 0%, #0A0C14 70%);
          overflow-y: auto;
          padding: 40px 20px;
        }
        .ri-result-card {
          width: 100%; max-width: 600px;
          padding: 40px;
          background: rgba(255,255,255,.04);
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 20px;
          text-align: center;
        }
        .ri-result-icon { font-size: 52px; margin-bottom: 16px; }
        .ri-result-card h2 { font-size: 24px; font-weight: 800; }
        .ri-result-sub { color: rgba(255,255,255,.5); margin-top: 8px; }
        .ri-result-sub strong { color: #FCD34D; }
        .ri-result-summary {
          margin: 28px 0;
          display: flex; flex-direction: column; gap: 16px;
          text-align: left;
        }
        .ri-result-item {
          padding: 16px;
          background: rgba(255,255,255,.04);
          border-radius: 10px;
          border: 1px solid rgba(255,255,255,.07);
        }
        .ri-result-q { font-size: 13px; color: #FCD34D; font-weight: 600; margin-bottom: 8px; }
        .ri-result-a { font-size: 13px; color: rgba(255,255,255,.6); line-height: 1.6; }
        .ri-result-actions { display: flex; gap: 12px; justify-content: center; }
        .ri-result-btn {
          padding: 13px 28px;
          border-radius: 10px;
          font-size: 14px; font-weight: 600; cursor: pointer;
          border: 1px solid rgba(255,255,255,.15);
          background: rgba(255,255,255,.06); color: rgba(255,255,255,.7);
          transition: all .2s;
        }
        .ri-result-btn:hover { background: rgba(255,255,255,.1); }
        .ri-result-btn.primary {
          background: linear-gradient(135deg, #4F6EF7, #7B5CF7);
          border: none; color: #fff;
        }

        /* 모달 */
        .ri-overlay {
          position: absolute; inset: 0;
          background: rgba(0,0,0,.7);
          display: flex; align-items: center; justify-content: center;
          z-index: 999;
        }
        .ri-modal {
          background: #1A1D2E;
          border: 1px solid rgba(255,255,255,.1);
          border-radius: 14px;
          padding: 28px;
          width: 90%;
          max-width: 360px;
        }
        .ri-modal h3 { font-size: 17px; font-weight: 700; }
        .ri-modal p { font-size: 13px; color: rgba(255,255,255,.4); margin-top: 8px; }
        .ri-modal-btns { display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }
        .ri-modal-cancel, .ri-modal-exit {
          padding: 8px 20px; border-radius: 8px; font-size: 14px; cursor: pointer;
        }
        .ri-modal-cancel { background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.1); color: rgba(255,255,255,.6); }
        .ri-modal-exit { background: #EF4444; border: none; color: #fff; font-weight: 600; }
      `}</style>
    </div>
  )
}
