import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import { interviewWS } from '@/services/websocket'

const QUESTIONS = [
  '자기소개를 1분 이내로 해주세요.',
  '지원 동기를 말씀해 주세요.',
  '본인의 강점과 이를 업무에 어떻게 활용했는지 말씀해 주세요.',
  '가장 도전적이었던 프로젝트 경험을 공유해 주세요.',
  '마지막으로 하고 싶은 말씀이 있으신가요?',
]

const Q_LIMIT = 120

export default function RealInterviewPage() {
  const navigate = useNavigate()
  const { resumeId } = useParams()

  const resume = useResumeStore((s) => s.getResume(resumeId))
  const { addInterviewRecord } = useResumeStore()

  const [phase, setPhase] = useState('intro')
  const [qIndex, setQIndex] = useState(0)
  const [remaining, setRemaining] = useState(Q_LIMIT)
  const [answer, setAnswer] = useState('')
  const [answers, setAnswers] = useState([])
  const [totalSec, setTotalSec] = useState(0)

  const [exitConfirm, setExitConfirm] = useState(false)

  // 카메라 / 분석 상태
  const [faceStatus, setFaceStatus] = useState('waiting')
  const [cameraError, setCameraError] = useState('')
  const [micActive, setMicActive] = useState(false)

  // MediaPipe 분석 결과
  const [analysis, setAnalysis] = useState(null)

  const videoRef = useRef(null)
  const streamRef = useRef(null)

  const timerRef = useRef(null)
  const totalRef = useRef(null)

  const frameTimerRef = useRef(null)

  // 오디오 분석용
  const audioContextRef = useRef(null)
  const animationFrameRef = useRef(null)

  const currentQ = QUESTIONS[qIndex]

  const pct = Math.round(
    ((Q_LIMIT - remaining) / Q_LIMIT) * 100
  )

  const r = 44
  const circ = 2 * Math.PI * r

  const timerColor =
    remaining > 60
      ? '#10b981'
      : remaining > 30
        ? '#f59e0b'
        : '#ef4444'

  // ============================================================
  // 1. 카메라 + 마이크 초기화
  // ============================================================
  useEffect(() => {
    let mounted = true

    const initializeMedia = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        console.error('[Camera] getUserMedia를 지원하지 않는 브라우저입니다.')
        setFaceStatus('lost')
        setCameraError('이 브라우저에서는 카메라를 사용할 수 없습니다.')
        return
      }

      try {
        setFaceStatus('detecting')
        setCameraError('')

        console.log('[Camera] 카메라/마이크 권한 요청')

        // 카메라와 마이크를 한 번에 요청
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: {
              ideal: 640,
            },
            height: {
              ideal: 480,
            },
            facingMode: 'user',
          },
          audio: true,
        })

        if (!mounted) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        streamRef.current = stream

        console.log('[Camera] 미디어 연결 성공')
        console.log(
          '[Camera] video tracks:',
          stream.getVideoTracks()
        )
        console.log(
          '[Camera] audio tracks:',
          stream.getAudioTracks()
        )

        // 현재 video가 이미 존재한다면 바로 연결
        if (videoRef.current) {
          videoRef.current.srcObject = stream

          try {
            await videoRef.current.play()
          } catch (error) {
            console.warn(
              '[Camera] video 자동 재생 실패:',
              error
            )
          }
        }

        // --------------------------------------------------------
        // 마이크 음량 분석
        // --------------------------------------------------------
        const audioTracks = stream.getAudioTracks()

        if (audioTracks.length > 0) {
          try {
            const AudioContextClass =
              window.AudioContext ||
              window.webkitAudioContext

            if (AudioContextClass) {
              const audioContext = new AudioContextClass()

              audioContextRef.current = audioContext

              if (audioContext.state === 'suspended') {
                await audioContext.resume()
              }

              const analyser =
                audioContext.createAnalyser()

              analyser.fftSize = 512
              analyser.smoothingTimeConstant = 0.4

              const source =
                audioContext.createMediaStreamSource(stream)

              source.connect(analyser)

              const data =
                new Uint8Array(analyser.frequencyBinCount)

              const checkMic = () => {
                if (!mounted) return

                analyser.getByteFrequencyData(data)

                let sum = 0

                for (
                  let i = 0;
                  i < Math.min(60, data.length);
                  i++
                ) {
                  sum += data[i]
                }

                const avg =
                  sum / Math.min(60, data.length)

                setMicActive(avg > 30)

                animationFrameRef.current =
                  requestAnimationFrame(checkMic)
              }

              checkMic()
            }
          } catch (error) {
            console.warn(
              '[Mic] 마이크 분석 초기화 실패:',
              error
            )
          }
        }

        setFaceStatus('waiting')

      } catch (error) {
        console.error(
          '[Camera] 카메라/마이크 연결 실패:',
          error
        )

        if (!mounted) return

        setFaceStatus('lost')

        if (error?.name === 'NotAllowedError') {
          setCameraError(
            '카메라 또는 마이크 권한이 거부되었습니다. Chrome 주소창의 카메라 권한을 확인해주세요.'
          )
        } else if (error?.name === 'NotFoundError') {
          setCameraError(
            '연결된 카메라를 찾을 수 없습니다.'
          )
        } else if (error?.name === 'NotReadableError') {
          setCameraError(
            '카메라가 다른 프로그램에서 사용 중입니다.'
          )
        } else {
          setCameraError(
            `카메라 연결 실패: ${error?.message || '알 수 없는 오류'}`
          )
        }
      }
    }

    initializeMedia()

    return () => {
      mounted = false

      if (animationFrameRef.current) {
        cancelAnimationFrame(
          animationFrameRef.current
        )
      }

      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {})
        audioContextRef.current = null
      }

      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) => track.stop())

        streamRef.current = null
      }
    }
  }, [])

  // ============================================================
  // 2. phase가 interview로 변경되면 video에 카메라 연결
  // ============================================================
  useEffect(() => {
    if (phase !== 'interview') return

    const video = videoRef.current
    const stream = streamRef.current

    if (!video) {
      console.warn(
        '[Camera] interview 상태인데 videoRef가 없습니다.'
      )
      return
    }

    if (!stream) {
      console.warn(
        '[Camera] interview 상태인데 카메라 스트림이 없습니다.'
      )
      return
    }

    console.log(
      '[Camera] interview 진입 → video에 stream 연결'
    )

    video.srcObject = stream

    const playVideo = async () => {
      try {
        await video.play()

        console.log(
          '[Camera] video 재생 성공:',
          video.videoWidth,
          'x',
          video.videoHeight
        )
      } catch (error) {
        console.warn(
          '[Camera] video.play() 실패:',
          error
        )
      }
    }

    playVideo()
  }, [phase])

  // ============================================================
  // 3. WebSocket 연결
  // ============================================================
  useEffect(() => {
    if (phase !== 'interview') return

    console.log(
      '[WS] 실전면접 WebSocket 연결:',
      resumeId
    )

    // MediaPipe 분석 결과 수신
    interviewWS.onFrameAnalysis = (result) => {
      console.log(
        '[MediaPipe] 분석 결과:',
        result
      )

      setAnalysis(result)

      if (result?.face_detected === true) {
        setFaceStatus('detected')
      } else if (result?.face_detected === false) {
        setFaceStatus('lost')
      }
    }

    // 상태 메시지
    interviewWS.onStatusChange = (status) => {
      console.log(
        '[WS] 상태:',
        status
      )
    }

    interviewWS.connect(resumeId)

    return () => {
      console.log(
        '[WS] 실전면접 WebSocket 종료'
      )

      interviewWS.stop()

      interviewWS.onFrameAnalysis = null
      interviewWS.onStatusChange = null
    }
  }, [phase, resumeId])

  // ============================================================
  // 4. 카메라 프레임 → WebSocket
  // ============================================================
  useEffect(() => {
    if (phase !== 'interview') return

    // 기존 타이머 제거
    if (frameTimerRef.current) {
      clearInterval(frameTimerRef.current)
      frameTimerRef.current = null
    }

    console.log(
      '[Camera] 실시간 프레임 전송 시작'
    )

    // 1초마다 1프레임
    frameTimerRef.current = setInterval(() => {
      if (!videoRef.current) return

      if (
        !videoRef.current.videoWidth ||
        !videoRef.current.videoHeight
      ) {
        console.warn(
          '[Camera] 아직 video 프레임이 준비되지 않았습니다.'
        )
        return
      }

      interviewWS.sendFrame(videoRef.current)

    }, 1000)

    return () => {
      if (frameTimerRef.current) {
        clearInterval(frameTimerRef.current)
        frameTimerRef.current = null
      }

      console.log(
        '[Camera] 실시간 프레임 전송 종료'
      )
    }
  }, [phase])

  // ============================================================
  // 5. 질문 타이머
  // ============================================================
  const handleNext = useCallback(() => {
    clearInterval(timerRef.current)

    const newAnswers = [
      ...answers,
      {
        q: currentQ,
        a: answer,
      },
    ]

    setAnswers(newAnswers)
    setAnswer('')

    if (qIndex + 1 >= QUESTIONS.length) {
      clearInterval(totalRef.current)

      // 최종 기록
      addInterviewRecord(resumeId, {
        type: 'real',
        duration: totalSec,
        questions: newAnswers,
      })

      // WebSocket 종료
      interviewWS.stop()

      setPhase('result')
    } else {
      setQIndex((p) => p + 1)

      setRemaining(Q_LIMIT)

      startQTimer()
    }
  }, [
    answers,
    currentQ,
    answer,
    qIndex,
    resumeId,
    totalSec,
    addInterviewRecord,
  ])

  const startQTimer = useCallback(() => {
    clearInterval(timerRef.current)

    setRemaining(Q_LIMIT)

    timerRef.current = setInterval(() => {
      setRemaining((p) => {
        if (p <= 1) {
          clearInterval(timerRef.current)

          handleNext()

          return 0
        }

        return p - 1
      })
    }, 1000)
  }, [handleNext])

  // ============================================================
  // 6. 면접 시작
  // ============================================================
  const handleStart = () => {
    console.log(
      '[Interview] 면접 시작'
    )

    setPhase('interview')

    setRemaining(Q_LIMIT)

    setTotalSec(0)

    totalRef.current = setInterval(() => {
      setTotalSec((p) => p + 1)
    }, 1000)

    startQTimer()
  }

  // ============================================================
  // 7. 시간 포맷
  // ============================================================
  const fmt = (sec) =>
    `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(
      sec % 60
    ).padStart(2, '0')}`

  // ============================================================
  // 8. 종료
  // ============================================================
  const handleExit = () => {
    clearInterval(timerRef.current)
    clearInterval(totalRef.current)
    clearInterval(frameTimerRef.current)

    interviewWS.stop()

    if (streamRef.current) {
      streamRef.current
        .getTracks()
        .forEach((track) => track.stop())

      streamRef.current = null
    }

    navigate('/resume')
  }

  // ============================================================
  // resume가 없는 경우
  // ============================================================
  if (!resume) {
    return (
      <div
        style={{
          padding: 40,
          textAlign: 'center',
          color: '#fff',
          background: '#0a0d1a',
          minHeight: '100vh',
        }}
      >
        자기소개서를 찾을 수 없습니다.

        <button
          onClick={() => navigate('/resume')}
          style={{
            marginLeft: 12,
            padding: '8px 16px',
            background: '#4f6ef7',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            cursor: 'pointer',
          }}
        >
          목록으로
        </button>
      </div>
    )
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: '#0a0d1a',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 500,
        fontFamily: 'inherit',
      }}
    >
      <style>{`
        .face-badge {
          position:absolute;
          bottom:8px;
          left:50%;
          transform:translateX(-50%);
          display:flex;
          align-items:center;
          gap:5px;
          padding:4px 10px;
          border-radius:99px;
          font-size:11px;
          font-weight:600;
          white-space:nowrap;
          backdrop-filter:blur(6px);
        }

        .face-badge.waiting {
          background:rgba(107,114,128,.85);
          color:#fff;
        }

        .face-badge.detecting {
          background:rgba(245,158,11,.85);
          color:#fff;
        }

        .face-badge.detected {
          background:rgba(16,185,129,.85);
          color:#fff;
        }

        .face-badge.lost {
          background:rgba(239,68,68,.85);
          color:#fff;
        }

        .face-dot {
          width:6px;
          height:6px;
          border-radius:50%;
          background:currentColor;
          animation:blink 1.2s infinite;
        }

        @keyframes blink {
          0%,100% {
            opacity:1;
          }

          50% {
            opacity:.3;
          }
        }

        @keyframes fadeUp {
          from {
            opacity:0;
            transform:translateY(10px);
          }

          to {
            opacity:1;
            transform:none;
          }
        }

        @keyframes fadeUpCenter {
          from {
            opacity:0;
            transform:translateX(-50%) translateY(10px);
          }

          to {
            opacity:1;
            transform:translateX(-50%) translateY(0);
          }
        }

        .fade-up-center {
          animation:fadeUpCenter .35s ease forwards;
        }

        .fade-up {
          animation:fadeUp .35s ease;
        }

        .ri-result-item {
          background:#1a1d2e;
          border-radius:10px;
          padding:14px;
          margin-bottom:10px;
        }

        .ri-result-q {
          font-size:13px;
          color:#4f6ef7;
          margin-bottom:6px;
          font-weight:600;
        }

        .ri-result-a {
          font-size:13px;
          color:rgba(255,255,255,.7);
          line-height:1.5;
        }
      `}</style>

      {/* ====================================================== */}
      {/* 상단 바 */}
      {/* ====================================================== */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 20px',
          background: '#111422',
          borderBottom:
            '1px solid rgba(255,255,255,.06)',
          flexShrink: 0,
        }}
      >
        <div>
          <span
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: '#fff',
            }}
          >
            🎯 실전 면접
          </span>

          <span
            style={{
              fontSize: 12,
              color: 'rgba(255,255,255,.35)',
              marginLeft: 12,
            }}
          >
            {resume.companyName} · {resume.jobTitle}
          </span>
        </div>

        {phase === 'interview' && (
          <span
            style={{
              fontSize: 13,
              color: 'rgba(255,255,255,.4)',
            }}
          >
            Q {qIndex + 1} / {QUESTIONS.length}
            &nbsp;·&nbsp;
            총 {fmt(totalSec)}
          </span>
        )}

        <button
          onClick={() => setExitConfirm(true)}
          style={{
            background: '#ef4444',
            border: 'none',
            borderRadius: 8,
            padding: '6px 16px',
            color: '#fff',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          나가기
        </button>
      </div>

      {/* ====================================================== */}
      {/* 진행바 */}
      {/* ====================================================== */}
      {phase === 'interview' && (
        <div
          style={{
            height: 3,
            background: '#1a1d2e',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              height: '100%',
              background:
                'linear-gradient(90deg,#4f6ef7,#10b981)',
              width: `${
                (qIndex / QUESTIONS.length) * 100
              }%`,
              transition: 'width .4s',
            }}
          />
        </div>
      )}

      {/* ====================================================== */}
      {/* 인트로 */}
      {/* ====================================================== */}
      {phase === 'intro' && (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          <div
            style={{
              fontSize: 56,
            }}
          >
            🎯
          </div>

          <div
            style={{
              fontSize: 22,
              fontWeight: 800,
              color: '#fff',
            }}
          >
            실전 면접 안내
          </div>

          <div
            style={{
              fontSize: 14,
              color: 'rgba(255,255,255,.5)',
              lineHeight: 1.9,
              textAlign: 'center',
            }}
          >
            각 질문당{' '}
            <b style={{ color: '#fff' }}>
              {Q_LIMIT}초
            </b>
            의 답변 시간이 주어집니다.
            <br />
            시간이 지나면 자동으로 다음 질문으로 넘어갑니다.
            <br />
            총{' '}
            <b style={{ color: '#fff' }}>
              {QUESTIONS.length}개
            </b>
            의 질문이 준비되어 있습니다.
          </div>

          {cameraError && (
            <div
              style={{
                maxWidth: 600,
                padding: '12px 16px',
                background: 'rgba(239,68,68,.12)',
                border:
                  '1px solid rgba(239,68,68,.3)',
                borderRadius: 10,
                color: '#fca5a5',
                fontSize: 13,
                textAlign: 'center',
              }}
            >
              ⚠️ {cameraError}
            </div>
          )}

          <div
            style={{
              display: 'flex',
              gap: 12,
            }}
          >
            <button
              onClick={() => navigate('/resume')}
              style={{
                background: 'transparent',
                color: 'rgba(255,255,255,.5)',
                border:
                  '1.5px solid rgba(255,255,255,.15)',
                borderRadius: 10,
                padding: '12px 24px',
                fontSize: 14,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              취소
            </button>

            <button
              onClick={handleStart}
              style={{
                background: '#4f6ef7',
                color: '#fff',
                border: 'none',
                borderRadius: 10,
                padding: '12px 36px',
                fontSize: 15,
                fontWeight: 700,
                cursor: 'pointer',
                fontFamily: 'inherit',
              }}
            >
              면접 시작
            </button>
          </div>
        </div>
      )}

      {/* ====================================================== */}
      {/* 면접 진행 */}
      {/* ====================================================== */}
      {phase === 'interview' && (
        <div
          style={{
            flex: 1,
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* 배경 */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background:
                'radial-gradient(ellipse at 50% 40%, #1a2040 0%, #0a0d1a 70%)',
              pointerEvents: 'none',
            }}
          />

          {/* ================================================= */}
          {/* 질문 */}
          {/* ================================================= */}
          <div
            key={qIndex}
            className="fade-up-center"
            style={{
              position: 'absolute',
              top: '8%',
              left: '50%',
              width: '60%',
              maxWidth: 640,
              textAlign: 'center',
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: '#4f6ef7',
                letterSpacing: '.08em',
                marginBottom: 8,
                textTransform: 'uppercase',
              }}
            >
              Q{qIndex + 1} 질문
            </div>

            <div
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: '#fff',
                lineHeight: 1.55,
                background:
                  'rgba(255,255,255,.04)',
                border:
                  '1px solid rgba(255,255,255,.08)',
                borderRadius: 14,
                padding: '16px 24px',
                backdropFilter: 'blur(8px)',
              }}
            >
              {currentQ}
            </div>
          </div>

          {/* ================================================= */}
          {/* AI 면접관 */}
          {/* ================================================= */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform:
                'translate(-50%, -54%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              zIndex: 5,
            }}
          >
            <div
              style={{
                width: 130,
                height: 130,
                borderRadius: '50%',
                background:
                  'linear-gradient(135deg,#4f6ef7,#10b981)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 64,
                boxShadow:
                  '0 0 48px rgba(79,110,247,.35)',
              }}
            >
              🤖
            </div>

            <div
              style={{
                marginTop: 12,
                fontSize: 13,
                color: 'rgba(255,255,255,.4)',
                fontWeight: 500,
              }}
            >
              AI 면접관
            </div>
          </div>

          {/* ================================================= */}
          {/* 원형 타이머 */}
          {/* ================================================= */}
          <div
            style={{
              position: 'absolute',
              top: 20,
              right: 20,
              zIndex: 10,
            }}
          >
            <div
              style={{
                background:
                  'rgba(17,20,34,.85)',
                border:
                  '1px solid rgba(255,255,255,.1)',
                borderRadius: 14,
                padding: '12px 14px',
                backdropFilter: 'blur(8px)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  color: 'rgba(255,255,255,.35)',
                }}
              >
                답변 시간
              </div>

              <svg
                width={100}
                height={100}
                viewBox="0 0 100 100"
              >
                <circle
                  cx={50}
                  cy={50}
                  r={r}
                  fill="none"
                  stroke="#1e2540"
                  strokeWidth={8}
                />

                <circle
                  cx={50}
                  cy={50}
                  r={r}
                  fill="none"
                  stroke={timerColor}
                  strokeWidth={8}
                  strokeLinecap="round"
                  strokeDasharray={circ}
                  strokeDashoffset={
                    circ * (pct / 100)
                  }
                  transform="rotate(-90 50 50)"
                  style={{
                    transition:
                      'stroke-dashoffset .9s, stroke .3s',
                  }}
                />

                <text
                  x={50}
                  y={54}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill={timerColor}
                  fontSize={18}
                  fontWeight={700}
                  fontFamily="monospace"
                >
                  {fmt(remaining)}
                </text>
              </svg>

              <div
                style={{
                  fontSize: 11,
                  color: 'rgba(255,255,255,.3)',
                }}
              >
                총 {fmt(totalSec)}
              </div>
            </div>
          </div>

          {/* ================================================= */}
          {/* 면접자 카메라 */}
          {/* ================================================= */}
          <div
            style={{
              position: 'absolute',
              bottom: 20,
              right: 20,
              zIndex: 10,
              width: 440,
              height: 320,
            }}
          >
            <div
              style={{
                width: '100%',
                height: '100%',
                borderRadius: 14,
                overflow: 'hidden',
                position: 'relative',

                border: micActive
                  ? '2.5px solid #22c55e'
                  : '2px solid rgba(255,255,255,.12)',

                boxShadow: micActive
                  ? '0 0 16px rgba(34,197,94,.4)'
                  : '0 4px 20px rgba(0,0,0,.5)',

                transition:
                  'border-color .15s, box-shadow .15s',

                background: '#111827',
              }}
            >
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                onLoadedMetadata={(e) => {
                  console.log(
                    '[Camera] metadata:',
                    e.currentTarget.videoWidth,
                    'x',
                    e.currentTarget.videoHeight
                  )
                }}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  display: 'block',

                  // 실제 거울처럼 보이게
                  transform: 'scaleX(-1)',
                }}
              />

              <div
                style={{
                  position: 'absolute',
                  top: 6,
                  left: 8,
                  fontSize: 11,
                  color: 'rgba(255,255,255,.5)',
                  background:
                    'rgba(0,0,0,.4)',
                  padding: '2px 7px',
                  borderRadius: 99,
                }}
              >
                📹 나
              </div>

              {faceStatus === 'waiting' && (
                <div className="face-badge waiting">
                  <span className="face-dot" />
                  분석 대기
                </div>
              )}

              {faceStatus === 'detecting' && (
                <div className="face-badge detecting">
                  <span className="face-dot" />
                  분석 중...
                </div>
              )}

              {faceStatus === 'detected' && (
                <div className="face-badge detected">
                  <span className="face-dot" />
                  얼굴 인식됨
                </div>
              )}

              {faceStatus === 'lost' && (
                <div className="face-badge lost">
                  <span className="face-dot" />
                  얼굴 없음
                </div>
              )}
            </div>
          </div>

          {/* ================================================= */}
          {/* MediaPipe 분석 결과 */}
          {/* ================================================= */}
          <div
            style={{
              position: 'absolute',
              left: 20,
              bottom: 20,
              width: 230,
              background:
                'rgba(17,20,34,.88)',
              border:
                '1px solid rgba(255,255,255,.1)',
              borderRadius: 12,
              padding: 14,
              backdropFilter: 'blur(8px)',
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: '#fff',
                marginBottom: 10,
              }}
            >
              📊 실시간 분석
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: 7,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color:
                    'rgba(255,255,255,.45)',
                }}
              >
                얼굴
              </span>

              <span
                style={{
                  fontSize: 11,
                  color:
                    faceStatus === 'detected'
                      ? '#10b981'
                      : '#f59e0b',
                }}
              >
                {faceStatus === 'detected'
                  ? '감지됨'
                  : '확인 중'}
              </span>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: 7,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color:
                    'rgba(255,255,255,.45)',
                }}
              >
                눈맞춤
              </span>

              <span
                style={{
                  fontSize: 11,
                  color: '#10b981',
                }}
              >
                {analysis?.eye_contact_score != null
                  ? Number(
                      analysis.eye_contact_score
                    ).toFixed(2)
                  : '—'}
              </span>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: 7,
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color:
                    'rgba(255,255,255,.45)',
                }}
              >
                깜빡임
              </span>

              <span
                style={{
                  fontSize: 11,
                  color: '#10b981',
                }}
              >
                {analysis?.blink_score != null
                  ? Number(
                      analysis.blink_score
                    ).toFixed(2)
                  : '—'}
              </span>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  color:
                    'rgba(255,255,255,.45)',
                }}
              >
                표정
              </span>

              <span
                style={{
                  fontSize: 11,
                  color: '#10b981',
                }}
              >
                {analysis?.expression_score != null
                  ? Number(
                      analysis.expression_score
                    ).toFixed(2)
                  : '—'}
              </span>
            </div>
          </div>

          {/* ================================================= */}
          {/* 답변 입력 */}
          {/* ================================================= */}
          <div
            style={{
              position: 'absolute',
              bottom: 20,
              left: '50%',
              transform:
                'translateX(-50%)',
              zIndex: 10,
              width: '38%',
              maxWidth: 620,
            }}
          >
            <div
              className="fade-up"
              key={qIndex}
            >
              <textarea
                value={answer}
                onChange={(e) =>
                  setAnswer(e.target.value)
                }
                placeholder="답변을 입력하거나 말씀해 주세요..."
                style={{
                  width: '100%',
                  background:
                    'rgba(17,20,34,.9)',
                  border:
                    '1.5px solid rgba(255,255,255,.15)',
                  borderRadius: 12,
                  padding: '14px 16px',
                  color: '#fff',
                  fontSize: 14,
                  resize: 'none',
                  minHeight: 80,
                  fontFamily: 'inherit',
                  backdropFilter: 'blur(8px)',
                  boxSizing: 'border-box',
                }}
              />

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  marginTop: 10,
                }}
              >
                <button
                  onClick={handleNext}
                  style={{
                    background: '#10b981',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 10,
                    padding: '11px 32px',
                    fontSize: 14,
                    fontWeight: 700,
                    cursor: 'pointer',
                    fontFamily: 'inherit',
                  }}
                >
                  {qIndex + 1 >= QUESTIONS.length
                    ? '면접 종료 →'
                    : '다음 질문 →'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ====================================================== */}
      {/* 결과 */}
      {/* ====================================================== */}
      {phase === 'result' && (
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: '32px 40px',
          }}
        >
          <div
            style={{
              maxWidth: 700,
              margin: '0 auto',
            }}
          >
            <div
              style={{
                textAlign: 'center',
                marginBottom: 32,
              }}
            >
              <div
                style={{
                  fontSize: 48,
                  marginBottom: 12,
                }}
              >
                ✅
              </div>

              <div
                style={{
                  fontSize: 22,
                  fontWeight: 800,
                  color: '#fff',
                }}
              >
                실전 면접 완료
              </div>

              <div
                style={{
                  fontSize: 14,
                  color:
                    'rgba(255,255,255,.4)',
                  marginTop: 8,
                }}
              >
                {QUESTIONS.length}개 질문 · 총{' '}
                {fmt(totalSec)}
              </div>
            </div>

            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color:
                  'rgba(255,255,255,.4)',
                marginBottom: 12,
                textTransform: 'uppercase',
                letterSpacing: '.05em',
              }}
            >
              답변 요약
            </div>

            {answers.map((item, i) => (
              <div
                key={i}
                className="ri-result-item"
              >
                <div className="ri-result-q">
                  Q{i + 1}. {item.q}
                </div>

                <div className="ri-result-a">
                  {item.a || '(답변 없음)'}
                </div>
              </div>
            ))}

            <div
              style={{
                display: 'flex',
                gap: 12,
                marginTop: 24,
                justifyContent: 'center',
              }}
            >
              <button
                onClick={handleExit}
                style={{
                  background:
                    'transparent',
                  color:
                    'rgba(255,255,255,.6)',
                  border:
                    '1.5px solid rgba(255,255,255,.15)',
                  borderRadius: 10,
                  padding: '12px 24px',
                  fontSize: 14,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                목록으로
              </button>

              <button
                onClick={() =>
                  navigate(
                    `/resume/${resumeId}/history`
                  )
                }
                style={{
                  background: '#4f6ef7',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 10,
                  padding: '12px 28px',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                기록 보기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ====================================================== */}
      {/* 나가기 확인 */}
      {/* ====================================================== */}
      {exitConfirm && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background:
              'rgba(0,0,0,.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 600,
          }}
        >
          <div
            style={{
              background: '#111422',
              borderRadius: 14,
              padding: '28px 32px',
              minWidth: 300,
              textAlign: 'center',
              border:
                '1px solid rgba(255,255,255,.1)',
            }}
          >
            <div
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: '#fff',
                marginBottom: 10,
              }}
            >
              면접을 종료하시겠습니까?
            </div>

            <div
              style={{
                fontSize: 13,
                color:
                  'rgba(255,255,255,.4)',
                marginBottom: 24,
              }}
            >
              진행 중인 내용은 저장되지 않습니다.
            </div>

            <div
              style={{
                display: 'flex',
                gap: 10,
                justifyContent: 'center',
              }}
            >
              <button
                onClick={() =>
                  setExitConfirm(false)
                }
                style={{
                  background:
                    'rgba(255,255,255,.07)',
                  border:
                    '1px solid rgba(255,255,255,.15)',
                  borderRadius: 8,
                  padding: '10px 22px',
                  color:
                    'rgba(255,255,255,.6)',
                  cursor: 'pointer',
                  fontSize: 14,
                }}
              >
                계속
              </button>

              <button
                onClick={handleExit}
                style={{
                  background: '#ef4444',
                  border: 'none',
                  borderRadius: 8,
                  padding: '10px 22px',
                  color: '#fff',
                  fontWeight: 700,
                  cursor: 'pointer',
                  fontSize: 14,
                }}
              >
                종료
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}