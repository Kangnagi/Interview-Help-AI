import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition'
import InterviewSetup from '@/components/Interview/InterviewSetup'
import { interviewAPI, analysisAPI } from '@/services/api'
import { interviewWS } from '@/services/websocket'

const FALLBACK_QUESTIONS = [
  '자기소개를 1분 이내로 해주세요.',
  '지원 동기를 말씀해 주세요.',
  '본인의 강점과 이를 업무에 어떻게 활용했는지 말씀해 주세요.',
  '가장 도전적이었던 프로젝트 경험을 공유해 주세요.',
  '마지막으로 하고 싶은 말씀이 있으신가요?',
]
const Q_LIMIT = 120

// 이보다 짧은 답변은 꼬리 질문을 요청하지 않는다 (서버 FOLLOW_UP_MIN_ANSWER와 같게)
const FOLLOW_UP_MIN_ANSWER = 40

export default function RealInterviewPage() {
  const navigate = useNavigate()
  const { resumeId } = useParams()
  const resume = useResumeStore((s) => s.getResume(resumeId))
  const { addInterviewRecord } = useResumeStore()

  const [phase, setPhase] = useState('setup')
  const [deviceIds, setDeviceIds] = useState({ cameraId: '', micId: '' })
  const [sessionStarted, setSessionStarted] = useState(false)
  const [qIndex, setQIndex] = useState(0)
  const [remaining, setRemaining] = useState(Q_LIMIT)
  const [answer, setAnswer] = useState('')
  const [answers, setAnswers] = useState([])
  const [totalSec, setTotalSec] = useState(0)
  const [exitConfirm, setExitConfirm] = useState(false)
  const [faceStatus, setFaceStatus] = useState('waiting')
  const [micActive, setMicActive] = useState(false)
  const [deviceError, setDeviceError] = useState(null)

  const [backendInterviewId, setBackendInterviewId] = useState(null)
  const [backendQuestions, setBackendQuestions] = useState([])
  const [isCreating, setIsCreating] = useState(false)
  const [followUpLoading, setFollowUpLoading] = useState(false)   // 방금 답변으로 꼬리 질문을 만드는 중 (약 2~3초, 그동안 시간은 멈춤)

  const videoRef = useRef(null)
  const setupStartedRef = useRef(false)
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const totalRef = useRef(null)
  const detectionRef = useRef(null)
  const micRafRef = useRef(null)
  const handleNextRef = useRef(null)

  const activeQuestions = backendQuestions.length > 0
    ? backendQuestions.map((q) => q.question_text)
    : FALLBACK_QUESTIONS
  const currentQ = activeQuestions[qIndex]
  const isFollowUp = backendQuestions[qIndex]?.follow_up_of != null

  const pct = Math.round(((Q_LIMIT - remaining) / Q_LIMIT) * 100)
  const r = 44, circ = 2 * Math.PI * r
  const timerColor = remaining > 60 ? '#10b981' : remaining > 30 ? '#f59e0b' : '#ef4444'

  const { listening, interim, toggle: toggleSTT, stop: stopSTT, isSupported: sttSupported } =
    useSpeechRecognition({ onFinal: (t) => setAnswer((prev) => prev + t) })

  useEffect(() => {
    if (phase !== 'interview') stopSTT()
  }, [phase, stopSTT])

  const handleSetupReady = useCallback(async ({ cameraId, micId }) => {
    // '준비 완료'를 여러 번 눌러도 면접은 한 번만 만든다 (질문 생성 5~7초 사이에 다시 눌러 면접이 두 개씩 생겼다 — 10/4 · 10/6)
    if (setupStartedRef.current) return
    setupStartedRef.current = true
    setDeviceIds({ cameraId, micId })
    setSessionStarted(true)

    const resumeText = resume ? [
      resume.title         && `제목: ${resume.title}`,
      resume.companyName   && `지원 회사: ${resume.companyName}`,
      resume.jobTitle      && `지원 직무: ${resume.jobTitle}`,
      resume.jobDescription && `직무 설명: ${resume.jobDescription}`,
      resume.idealCandidate && `인재상: ${resume.idealCandidate}`,
      // 자기소개서는 여러 줄이라 맨 끝에 둔다 — 서버가 '자기소개서:' 뒤 전체를 떼어 키워드 질문에 쓴다
      resume.selfIntroduction && `자기소개서: ${resume.selfIntroduction}`,
    ].filter(Boolean).join('\n') : ''

    try {
      const { data: interview } = await interviewAPI.create({
        title: `${resume?.title || '실전'} 실전면접`,
        category: 'general',
        interview_type: 'real',
        resume_ref_id: resumeId,
        resume_text: resumeText || undefined,
      })
      setBackendInterviewId(interview.id)
      const { data: questions } = await interviewAPI.getQuestions(interview.id)
      setBackendQuestions(questions)
    } catch (err) {
      console.error('면접 세션 생성 실패:', err)
      setBackendQuestions(
        FALLBACK_QUESTIONS.map((q, i) => ({ id: null, order: i + 1, question_text: q }))
      )
    }

    setPhase('intro')
  }, [resume, resumeId])

  useEffect(() => {
    if (!sessionStarted) return
    setFaceStatus('detecting')

    const camConstraints = {
      video: deviceIds.cameraId ? { deviceId: { exact: deviceIds.cameraId } } : true,
      audio: false,
    }
    const micConstraints = {
      audio: deviceIds.micId ? { deviceId: { exact: deviceIds.micId } } : true,
      video: false,
    }

    navigator.mediaDevices.getUserMedia(camConstraints)
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
          // 얼굴 인식 기능(FaceDetector)이 없는 브라우저(대부분의 Chrome) — 확인 없이 '얼굴 인식됨'을 띄우던 것을 '카메라 연결됨'으로
          setFaceStatus('camera')
        }
      })
      .catch(() => {
        setFaceStatus('lost')
        setDeviceError('camera')
      })

    navigator.mediaDevices.getUserMedia(micConstraints)
      .then((audioStream) => {
        const ctx = new (window.AudioContext || window.webkitAudioContext)()
        if (ctx.state === 'suspended') ctx.resume()
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 512
        analyser.smoothingTimeConstant = 0.4
        ctx.createMediaStreamSource(audioStream).connect(analyser)
        const data = new Uint8Array(analyser.frequencyBinCount)
        const check = () => {
          analyser.getByteFrequencyData(data)
          const avg = data.slice(0, 60).reduce((a, b) => a + b, 0) / 60
          setMicActive(avg > 30)
          micRafRef.current = requestAnimationFrame(check)
        }
        check()
      })
      .catch(() => {
        setDeviceError((prev) => prev === 'camera' ? 'both' : 'mic')
      })

    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      clearInterval(detectionRef.current)
      cancelAnimationFrame(micRafRef.current)
    }
  }, [sessionStarted]) // eslint-disable-line react-hooks/exhaustive-deps

  // phase가 'interview'로 바뀔 때 video 요소에 스트림 재할당 (요소가 그 전엔 미렌더링)
  useEffect(() => {
    if (phase === 'interview' && streamRef.current && videoRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [phase])

  const startQTimer = useCallback(() => {
    clearInterval(timerRef.current)
    setRemaining(Q_LIMIT)
    timerRef.current = setInterval(() => {
      setRemaining((p) => {
        if (p <= 1) { clearInterval(timerRef.current); handleNextRef.current?.(); return 0 }
        return p - 1
      })
    }, 1000)
  }, [])

  const handleNext = useCallback(async () => {
    stopSTT()
    clearInterval(timerRef.current)

    const currentAnswer = [answer, interim].filter(Boolean).join(' ').trim()
    const currentAnswers = [...answers, { q: currentQ, a: currentAnswer }]
    const currentBackendQ = backendQuestions[qIndex]

    setAnswers(currentAnswers)
    setAnswer('')

    // 실시간 꼬리 질문 — 방금 답변을 보고 서버가 이어 물을 질문을 만들면 바로 다음 순서에 끼워 넣는다
    // (꼬리 질문에 대한 답변 · 짧은 답변은 요청하지 않음, 서버가 면접당 최대 2개로 제한)
    let questionsNow = backendQuestions
    if (backendInterviewId && currentBackendQ?.id && currentBackendQ.follow_up_of == null && currentAnswer.length >= FOLLOW_UP_MIN_ANSWER) {
      setFollowUpLoading(true)
      try {
        const { data } = await interviewAPI.followUp(backendInterviewId, currentBackendQ.id, { answer_text: currentAnswer })
        if (data?.question) {
          questionsNow = [...backendQuestions.slice(0, qIndex + 1), data.question, ...backendQuestions.slice(qIndex + 1)]
          setBackendQuestions(questionsNow)
        }
      } catch (err) {
        console.error('꼬리 질문 생성 실패 (원래 순서대로 진행):', err)
      } finally {
        setFollowUpLoading(false)
      }
    }
    const isLast = qIndex + 1 >= (questionsNow.length > 0 ? questionsNow.length : activeQuestions.length)

    if (isLast) {
      clearInterval(totalRef.current)
      if (backendInterviewId && currentBackendQ) {
        try {
          await interviewAPI.submitAnswer(backendInterviewId, currentBackendQ.id, { answer_text: currentAnswer })
        } catch (e) { console.error(e) }
      }
      if (backendInterviewId) {
        try {
          await interviewAPI.finish(backendInterviewId)
          await analysisAPI.start(backendInterviewId)
          addInterviewRecord(resumeId, {
            type: 'real',
            duration: totalSec,
            questions: currentAnswers,
            interviewId: backendInterviewId,
          })
          navigate(`/analysis/${backendInterviewId}`)
        } catch (err) {
          console.error('분석 시작 실패:', err)
          addInterviewRecord(resumeId, { type: 'real', duration: totalSec, questions: currentAnswers })
          setPhase('result')
        }
      } else {
        addInterviewRecord(resumeId, { type: 'real', duration: totalSec, questions: currentAnswers })
        setPhase('result')
      }
      return
    }

    // 중간 질문: 답변 저장 후 다음 질문으로 이동
    if (backendInterviewId && currentBackendQ) {
      interviewAPI.submitAnswer(backendInterviewId, currentBackendQ.id, { answer_text: currentAnswer }).catch(console.error)
    }
    setQIndex((p) => p + 1)
    startQTimer()
  }, [qIndex, answers, currentQ, answer, interim, activeQuestions.length, backendInterviewId, backendQuestions, resumeId, addInterviewRecord, navigate, stopSTT, totalSec, startQTimer])

  handleNextRef.current = handleNext

  const handleStart = async () => {
    // handleSetupReady에서 이미 생성된 경우 중복 생성 방지
    if (!backendInterviewId) {
      setIsCreating(true)
      try {
        const { data: interviewData } = await interviewAPI.create({
          title: resume?.title || '실전 면접',
          category: 'general',
        })
        setBackendInterviewId(interviewData.id)
        const { data: questions } = await interviewAPI.getQuestions(interviewData.id)
        setBackendQuestions(questions)
      } catch (err) {
        console.error('면접 생성 실패 (오프라인 모드로 진행):', err)
      } finally {
        setIsCreating(false)
      }
    }
    setPhase('interview')
    totalRef.current = setInterval(() => setTotalSec((p) => p + 1), 1000)
    startQTimer()
  }

  const fmt = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`

  const handleExit = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    navigate('/resume')
  }

  if (phase === 'setup') {
    return <InterviewSetup resumeInfo={resume} onReady={handleSetupReady} />
  }

  if (!resume) return (
    <div style={{ padding: 40, textAlign: 'center', color: '#fff', background: '#0a0d1a', minHeight: '100vh' }}>
      자기소개서를 찾을 수 없습니다.
      <button onClick={() => navigate('/resume')} style={{ marginLeft: 12, padding: '8px 16px', background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>목록으로</button>
    </div>
  )

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#0a0d1a', display: 'flex', flexDirection: 'column', zIndex: 500, fontFamily: 'inherit' }}>
      <style>{`
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
        .ri-result-item { background:#1a1d2e; border-radius:10px; padding:14px; margin-bottom:10px; }
        .ri-result-q { font-size:13px; color:#4f6ef7; margin-bottom:6px; font-weight:600; }
        .ri-result-a { font-size:13px; color:rgba(255,255,255,.7); line-height:1.5; }
        @keyframes stt-pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
        .stt-active { animation:stt-pulse 1s infinite; }
      `}</style>

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', background: '#111422', borderBottom: '1px solid rgba(255,255,255,.06)', flexShrink: 0 }}>
        <div>
          <span style={{ fontSize: 15, fontWeight: 700, color: '#fff' }}>🎯 실전 면접</span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,.35)', marginLeft: 12 }}>{resume.companyName} · {resume.jobTitle}</span>
        </div>
        {phase === 'interview' && (
          <span style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>
            Q {qIndex + 1} / {activeQuestions.length} &nbsp;·&nbsp; 총 {fmt(totalSec)}
          </span>
        )}
        <button onClick={() => setExitConfirm(true)} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '6px 16px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>나가기</button>
      </div>

      {/* 장치 오류 배너 */}
      {deviceError && (
        <div style={{ background: '#450a0a', borderBottom: '1px solid rgba(239,68,68,.3)', padding: '8px 20px', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span>⚠️</span>
          <span style={{ fontSize: 13, color: '#fca5a5', flex: 1 }}>
            {deviceError === 'camera' && '카메라에 연결하지 못했습니다. 브라우저 권한을 확인해 주세요.'}
            {deviceError === 'mic' && '마이크에 연결하지 못했습니다. 텍스트로 답변을 입력할 수 있습니다.'}
            {deviceError === 'both' && '카메라와 마이크에 연결하지 못했습니다. 브라우저 권한 설정을 확인해 주세요.'}
          </span>
          <button onClick={() => setDeviceError(null)} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,.3)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>
      )}

      {/* Progress bar */}
      {phase === 'interview' && (
        <div style={{ height: 3, background: '#1a1d2e', flexShrink: 0 }}>
          <div style={{ height: '100%', background: 'linear-gradient(90deg,#4f6ef7,#10b981)', width: `${(qIndex / activeQuestions.length) * 100}%`, transition: 'width .4s' }} />
        </div>
      )}

      {/* Intro */}
      {phase === 'intro' && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 20 }}>
          <div style={{ fontSize: 56 }}>🎯</div>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>실전 면접 안내</div>
          <div style={{ fontSize: 14, color: 'rgba(255,255,255,.5)', lineHeight: 1.9, textAlign: 'center' }}>
            각 질문당 <b style={{ color: '#fff' }}>{Q_LIMIT}초</b>의 답변 시간이 주어집니다.<br />
            시간이 지나면 자동으로 다음 질문으로 넘어갑니다.<br />
            총 <b style={{ color: '#fff' }}>{activeQuestions.length}개</b>의 질문이 준비되어 있습니다.
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <button onClick={() => navigate('/resume')} style={{ background: 'transparent', color: 'rgba(255,255,255,.5)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '12px 24px', fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>취소</button>
            <button
              onClick={handleStart}
              disabled={isCreating}
              style={{ background: isCreating ? '#334' : '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 36px', fontSize: 15, fontWeight: 700, cursor: isCreating ? 'wait' : 'pointer', fontFamily: 'inherit', opacity: isCreating ? 0.6 : 1 }}
            >
              {isCreating ? '준비 중...' : '면접 시작'}
            </button>
          </div>
        </div>
      )}

      {/* Interview stage */}
      {phase === 'interview' && (
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, #1a2040 0%, #0a0d1a 70%)', pointerEvents: 'none' }} />

          {/* Question */}
          <div key={qIndex} className="fade-up-center" style={{ position: 'absolute', top: '8%', left: '50%', width: '60%', maxWidth: 640, textAlign: 'center', zIndex: 10 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: isFollowUp ? '#f59e0b' : '#4f6ef7', letterSpacing: '.08em', marginBottom: 8, textTransform: 'uppercase' }}>
              {isFollowUp ? `Q${qIndex + 1} 꼬리 질문 · 방금 답변을 듣고 이어서 묻습니다` : `Q${qIndex + 1} 질문`}
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', lineHeight: 1.55, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, padding: '16px 24px', backdropFilter: 'blur(8px)' }}>
              {currentQ}
            </div>
          </div>

          {/* AI Interviewer */}
          <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -54%)', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 5 }}>
            <div style={{ width: 130, height: 130, borderRadius: '50%', background: 'linear-gradient(135deg,#4f6ef7,#10b981)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64, boxShadow: '0 0 48px rgba(79,110,247,.35)' }}>🤖</div>
            <div style={{ marginTop: 12, fontSize: 13, color: 'rgba(255,255,255,.4)', fontWeight: 500 }}>AI 면접관</div>
          </div>

          {/* Circular timer */}
          <div style={{ position: 'absolute', top: 20, right: 20, zIndex: 10 }}>
            <div style={{ background: 'rgba(17,20,34,.85)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 14, padding: '12px 14px', backdropFilter: 'blur(8px)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)' }}>답변 시간</div>
              <svg width={100} height={100} viewBox="0 0 100 100">
                <circle cx={50} cy={50} r={r} fill="none" stroke="#1e2540" strokeWidth={8} />
                <circle
                  cx={50} cy={50} r={r} fill="none"
                  stroke={timerColor} strokeWidth={8} strokeLinecap="round"
                  strokeDasharray={circ}
                  strokeDashoffset={circ * (pct / 100)}
                  transform="rotate(-90 50 50)"
                  style={{ transition: 'stroke-dashoffset .9s, stroke .3s' }}
                />
                <text x={50} y={54} textAnchor="middle" dominantBaseline="middle" fill={timerColor} fontSize={18} fontWeight={700} fontFamily="monospace">
                  {fmt(remaining)}
                </text>
              </svg>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,.3)' }}>총 {fmt(totalSec)}</div>
            </div>
          </div>

          {/* Camera */}
          <div style={{ position: 'absolute', bottom: 20, right: 20, zIndex: 10, width: 400, height: 290 }}>
            <div style={{
              width: '100%', height: '100%', borderRadius: 14, overflow: 'hidden', position: 'relative',
              border: micActive ? '2.5px solid #22c55e' : '2px solid rgba(255,255,255,.1)',
              boxShadow: micActive ? '0 0 16px rgba(34,197,94,.4)' : '0 4px 20px rgba(0,0,0,.5)',
              transition: 'border-color .15s, box-shadow .15s', background: '#111827',
            }}>
              <video ref={videoRef} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: 'scaleX(-1)' }} autoPlay playsInline muted />
              <div style={{ position: 'absolute', top: 6, left: 8, fontSize: 11, color: 'rgba(255,255,255,.5)', background: 'rgba(0,0,0,.4)', padding: '2px 7px', borderRadius: 99 }}>📹 나</div>
              {faceStatus === 'detecting' && <div className="face-badge detecting"><span className="face-dot" />인식 중...</div>}
              {faceStatus === 'detected' && <div className="face-badge detected"><span className="face-dot" />얼굴 인식됨</div>}
              {faceStatus === 'camera' && <div className="face-badge detected"><span className="face-dot" />카메라 연결됨</div>}
              {faceStatus === 'lost' && <div className="face-badge lost"><span className="face-dot" />얼굴 없음</div>}
            </div>
          </div>

          {/* Bottom answer panel */}
          <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 10, width: '55%', maxWidth: 600 }}>
            <div className="fade-up" key={qIndex}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                {sttSupported ? (
                  <button
                    onClick={toggleSTT}
                    className={listening ? 'stt-active' : ''}
                    style={{ background: listening ? 'rgba(239,68,68,.15)' : 'rgba(79,110,247,.12)', border: `1.5px solid ${listening ? '#ef4444' : 'rgba(79,110,247,.5)'}`, borderRadius: 8, padding: '7px 16px', color: listening ? '#ef4444' : '#6d85f8', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                  >
                    {listening ? '🔴 인식 중지' : '🎤 음성 입력'}
                  </button>
                ) : (
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,.25)' }}>이 브라우저는 음성 인식을 지원하지 않습니다</span>
                )}
                {listening && <span style={{ fontSize: 12, color: 'rgba(255,255,255,.4)', fontStyle: 'italic' }}>말씀하세요...</span>}
              </div>
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={sttSupported ? '답변을 입력하거나 위 버튼으로 음성 입력하세요' : '답변을 입력하세요'}
                style={{ width: '100%', background: 'rgba(17,20,34,.9)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 12, padding: '14px 16px', color: '#fff', fontSize: 14, resize: 'none', minHeight: 80, fontFamily: 'inherit', backdropFilter: 'blur(8px)', boxSizing: 'border-box' }}
              />
              {interim && (
                <div style={{ fontSize: 12, color: 'rgba(255,255,255,.35)', fontStyle: 'italic', marginTop: 5, padding: '0 4px' }}>💬 {interim}</div>
              )}
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
                <button onClick={handleNext} disabled={followUpLoading} style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 10, padding: '11px 32px', fontSize: 14, fontWeight: 700, cursor: followUpLoading ? 'wait' : 'pointer', fontFamily: 'inherit', opacity: followUpLoading ? 0.6 : 1 }}>
                  {followUpLoading ? '🤔 답변을 살펴보는 중…' : qIndex + 1 >= activeQuestions.length ? '면접 종료 →' : '다음 질문 →'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Result (fallback when backend unavailable) */}
      {phase === 'result' && (
        <div style={{ flex: 1, overflow: 'auto', padding: '32px 40px' }}>
          <div style={{ maxWidth: 700, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 32 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>실전 면접 완료</div>
              <div style={{ fontSize: 14, color: 'rgba(255,255,255,.4)', marginTop: 8 }}>{activeQuestions.length}개 질문 · 총 {fmt(totalSec)}</div>
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,.4)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '.05em' }}>답변 요약</div>
            {answers.map((item, i) => (
              <div key={i} className="ri-result-item">
                <div className="ri-result-q">Q{i + 1}. {item.q}</div>
                <div className="ri-result-a">{item.a || '(답변 없음)'}</div>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 12, marginTop: 24, justifyContent: 'center' }}>
              <button onClick={handleExit} style={{ background: 'transparent', color: 'rgba(255,255,255,.6)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '12px 24px', fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>목록으로</button>
              {backendInterviewId && (
                <button onClick={() => navigate(`/interview/${backendInterviewId}/result`)} style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 28px', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>📊 AI 분석 보기</button>
              )}
              <button onClick={() => navigate(`/resume/${resumeId}/history`)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 28px', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>기록 보기</button>
            </div>
          </div>
        </div>
      )}

      {/* Exit confirm */}
      {exitConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 600 }}>
          <div style={{ background: '#111422', borderRadius: 14, padding: '28px 32px', minWidth: 300, textAlign: 'center', border: '1px solid rgba(255,255,255,.1)' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 10 }}>면접을 종료하시겠습니까?</div>
            <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 24 }}>진행 중인 내용은 저장되지 않습니다.</div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button onClick={() => setExitConfirm(false)} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 8, padding: '10px 22px', color: 'rgba(255,255,255,.6)', cursor: 'pointer', fontSize: 14 }}>계속</button>
              <button onClick={handleExit} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '10px 22px', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>종료</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
