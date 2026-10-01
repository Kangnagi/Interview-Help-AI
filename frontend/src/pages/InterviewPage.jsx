import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useInterviewStore } from '@/store/interviewStore'
import { interviewWS } from '@/services/websocket'
import toast from 'react-hot-toast'

export default function InterviewPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const frameTimer = useRef(null)

  // 면접 전체 얼굴 분석 데이터를 저장
  const faceAnalysisRef = useRef({
    startedAt: null,
    timeline: [],
  })

  const {
    questions,
    loadQuestions,
    currentQuestionIdx,
    nextQuestion,
    submitAnswer,
    finishInterview,
    startAnalysis,
  } = useInterviewStore()

  const [answer, setAnswer] = useState('')
  const [recording, setRecording] = useState(false)
  const [timeLeft, setTimeLeft] = useState(120)
  const [camReady, setCamReady] = useState(false)
  const [feedback, setFeedback] = useState(null)
  const [wsReady, setWsReady] = useState(false)

  const currentQ = questions[currentQuestionIdx]
  const isLast = currentQuestionIdx === questions.length - 1

  // ============================================================
  // 얼굴 분석 결과 자동 수집
  // ============================================================
  const recordFaceAnalysis = useCallback((result) => {
    if (!result) return

    const session = faceAnalysisRef.current

    if (!session.startedAt) {
      session.startedAt = Date.now()
    }

    const elapsed = (Date.now() - session.startedAt) / 1000

    const faceDetected =
      result.face_detected ??
      result.faceDetected ??
      false

    const landmarkDetected =
      result.landmark_detected ??
      result.landmarkDetected ??
      faceDetected

    const landmarkCount =
      result.landmark_count ??
      result.landmarkCount ??
      0

    const blinkScore =
      result.blink_score ??
      result.blinkScore ??
      0

    const expressionScore =
      result.expression_score ??
      result.expressionScore ??
      0

    session.timeline.push({
      time_sec: Number(elapsed.toFixed(1)),
      face_detected: Boolean(faceDetected),
      landmark_detected: Boolean(landmarkDetected),
      landmark_count: Number(landmarkCount),
      blink_score: Number(blinkScore),
      expression_score: Number(expressionScore),
    })
  }, [])

  // ============================================================
  // 카메라 + WebSocket 초기화
  // ============================================================
  useEffect(() => {
    let mounted = true

    const initializeInterview = async () => {
      try {
        // 이전 면접 데이터가 남아 있지 않도록 초기화
        faceAnalysisRef.current = {
          startedAt: null,
          timeline: [],
        }

        await loadQuestions(id)

        // --------------------------------------------------------
        // 1. 카메라 / 마이크 연결
        // --------------------------------------------------------
        const stream =
          await navigator.mediaDevices.getUserMedia({
            video: {
              width: { ideal: 1280 },
              height: { ideal: 720 },
              facingMode: 'user',
            },
            audio: true,
          })

        if (!mounted) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        streamRef.current = stream

        if (videoRef.current) {
          videoRef.current.srcObject = stream

          try {
            await videoRef.current.play()
          } catch (error) {
            console.warn(
              '[Camera] video.play() 실패:',
              error
            )
          }
        }

        setCamReady(true)
        console.log('[Camera] 카메라 연결 성공')

        // --------------------------------------------------------
        // 2. WebSocket 분석 결과 수신
        // --------------------------------------------------------
        interviewWS.onFrameAnalysis = (result) => {
          console.log('[MediaPipe] 분석 결과:', result)

          if (!mounted) return

          setFeedback(result)
          recordFaceAnalysis(result)
        }

        interviewWS.onStatusChange = (status) => {
          console.log('[WS] 상태:', status)
        }

        // --------------------------------------------------------
        // 3. WebSocket 연결
        // --------------------------------------------------------
        interviewWS.connect(id)
      } catch (error) {
        console.error('[Interview] 초기화 실패:', error)

        toast.error(
          '카메라 또는 마이크를 사용할 수 없습니다.'
        )
      }
    }

    initializeInterview()

    return () => {
      mounted = false

      if (frameTimer.current) {
        clearInterval(frameTimer.current)
        frameTimer.current = null
      }

      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) => track.stop())

        streamRef.current = null
      }

      interviewWS.stop()

      setCamReady(false)
      setWsReady(false)
    }
  }, [id, loadQuestions, recordFaceAnalysis])

  // ============================================================
  // WebSocket 연결 상태 감시
  // ============================================================
  useEffect(() => {
    const timer = setInterval(() => {
      setWsReady(Boolean(interviewWS.isConnected))
    }, 300)

    return () => clearInterval(timer)
  }, [])

  // ============================================================
  // 실시간 카메라 프레임 전송
  // ============================================================
  useEffect(() => {
    if (!camReady || !wsReady) {
      return
    }

    console.log(
      '[MediaPipe] 실시간 프레임 전송 시작'
    )

    if (frameTimer.current) {
      clearInterval(frameTimer.current)
    }

    // 200ms마다 1프레임 = 초당 약 5프레임
    frameTimer.current = setInterval(() => {
      if (!videoRef.current) {
        return
      }

      if (
        !videoRef.current.videoWidth ||
        !videoRef.current.videoHeight
      ) {
        console.warn(
          '[MediaPipe] 비디오 프레임 준비 안됨'
        )
        return
      }

      interviewWS.sendFrame(videoRef.current)
    }, 200)

    return () => {
      if (frameTimer.current) {
        clearInterval(frameTimer.current)
        frameTimer.current = null
      }

      console.log(
        '[MediaPipe] 프레임 전송 중지'
      )
    }
  }, [camReady, wsReady])

  // ============================================================
  // 면접 답변 타이머
  // ============================================================
  useEffect(() => {
    if (!recording) {
      return
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer)
          setRecording(false)
          return 0
        }

        return prev - 1
      })
    }, 1000)

    return () => {
      clearInterval(timer)
    }
  }, [recording])

  // ============================================================
  // 답변 시작
  // ============================================================
  const handleRecord = () => {
    setRecording(true)
    setTimeLeft(120)

    toast('답변을 시작하세요!', {
      icon: '🎤',
    })
  }

  // ============================================================
  // 다음 질문
  // ============================================================
  const handleNext = useCallback(
    async () => {
      if (!currentQ) {
        toast.error(
          '현재 질문을 불러오지 못했습니다.'
        )
        return
      }

      if (!answer.trim()) {
        toast.error(
          '답변을 입력해주세요'
        )
        return
      }

      try {
        await submitAnswer(
          id,
          currentQ.id,
          answer
        )

        setAnswer('')
        setRecording(false)
        setTimeLeft(120)

        // --------------------------------------------------------
        // 마지막 질문
        // --------------------------------------------------------
        if (isLast) {
          // 면접 종료 직전까지 수집된 얼굴 분석 결과 저장
          const timeline = [
            ...faceAnalysisRef.current.timeline,
          ]

          if (timeline.length > 0) {
            const faceDetectedCount =
              timeline.filter(
                (item) => item.face_detected
              ).length

            const landmarkDetectedCount =
              timeline.filter(
                (item) => item.landmark_detected
              ).length

            const average = (key) => {
              const values = timeline
                .map((item) => Number(item[key]))
                .filter((value) =>
                  Number.isFinite(value)
                )

              if (values.length === 0) {
                return 0
              }

              return (
                values.reduce(
                  (sum, value) => sum + value,
                  0
                ) / values.length
              )
            }

            const faceAnalysis = {
              interview_id: Number(id),
              saved_at: new Date().toISOString(),

              face_analysis: {
                sample_count: timeline.length,

                face_detection_rate:
                  (faceDetectedCount /
                    timeline.length) *
                  100,

                landmark_detection_rate:
                  (landmarkDetectedCount /
                    timeline.length) *
                  100,

                average_blink:
                  average('blink_score'),

                average_expression:
                  average('expression_score'),

                timeline,
              },
            }

            localStorage.setItem(
              `faceAnalysis:${id}`,
              JSON.stringify(faceAnalysis)
            )

            console.log(
              '[FaceAnalysis] 최종 저장:',
              faceAnalysis
            )
          } else {
            console.warn(
              '[FaceAnalysis] 저장할 분석 결과가 없습니다.'
            )
          }

          // 기존 면접 종료 처리
          await finishInterview(id)
          await startAnalysis(id)

          toast.success(
            '면접이 완료되었습니다! 분석 중...'
          )

          navigate(
            `/interview/${id}/result`
          )

          return
        }

        // --------------------------------------------------------
        // 다음 질문
        // --------------------------------------------------------
        nextQuestion()

        toast.success(
          '다음 질문으로 이동합니다'
        )
      } catch (error) {
        console.error(
          '[Interview] 답변 저장 실패:',
          error
        )

        toast.error(
          '답변 저장 중 오류가 발생했습니다.'
        )
      }
    },
    [
      answer,
      currentQ,
      isLast,
      id,
      submitAnswer,
      finishInterview,
      startAnalysis,
      navigate,
      nextQuestion,
    ]
  )

  // ============================================================
  // 시간 표시
  // ============================================================
  const formatTime = (seconds) => {
    return (
      `${String(
        Math.floor(seconds / 60)
      ).padStart(2, '0')}:` +
      `${String(
        seconds % 60
      ).padStart(2, '0')}`
    )
  }

  const progress =
    questions.length > 0
      ? (
          (currentQuestionIdx + 1) /
          questions.length
        ) * 100
      : 0

  // ============================================================
  // MediaPipe 값
  // ============================================================
  const faceDetected =
    feedback?.face_detected ?? false

  const eyeContactScore =
    feedback?.eye_contact_score ?? null

  const blinkScore =
    feedback?.blink_score ?? null

  const expressionScore =
    feedback?.expression_score ?? null

  // ============================================================
  // 점수 표시
  //
  // MediaPipe의 blink/expression 값은 현재
  // 백엔드에서 0~100 기준으로 반환되는 것을 그대로 표시한다.
  // eye_contact는 현재 구현상 실제 계산값이 아닐 수 있으므로
  // 값이 들어온 경우 그대로 표시한다.
  // ============================================================
  const formatScore = (value) => {
    if (
      value === null ||
      value === undefined
    ) {
      return '—'
    }

    if (typeof value !== 'number') {
      return String(value)
    }

    return `${Math.round(value)}%`
  }

  // ============================================================
  // 화면
  // ============================================================
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns:
          '1fr 340px',
        gap: 20,
        height:
          'calc(100vh - 120px)',
      }}
    >

      {/* ======================================================
          왼쪽
      ======================================================= */}

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >

        {/* 진행 상황 */}

        <div
          className="card"
          style={{
            padding: '14px 20px',
          }}
        >
          <div
            className="flex justify-between items-center"
            style={{
              marginBottom: 8,
            }}
          >
            <span
              style={{
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              질문 {currentQuestionIdx + 1}
              {' / '}
              {questions.length}
            </span>

            {recording && (
              <span
                style={{
                  fontSize: 13,
                  color:
                    timeLeft < 30
                      ? 'var(--danger)'
                      : 'var(--text-secondary)',
                  fontWeight: 500,
                }}
              >
                ⏱ {formatTime(timeLeft)}
              </span>
            )}
          </div>

          <div
            style={{
              height: 6,
              background:
                'var(--border)',
              borderRadius: 99,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: `${progress}%`,
                height: '100%',
                background:
                  'var(--primary)',
                transition:
                  'width .4s',
              }}
            />
          </div>
        </div>

        {/* ==================================================
            카메라
        =================================================== */}

        <div
          style={{
            background: '#111',
            borderRadius:
              'var(--radius-lg)',
            overflow: 'hidden',
            aspectRatio: '16/9',
            position: 'relative',
          }}
        >

          <video
            ref={videoRef}
            autoPlay
            muted
            playsInline
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              transform:
                'scaleX(-1)',
            }}
          />

          {!camReady && (
            <div
              style={{
                position: 'absolute',
                inset: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent:
                  'center',
                color: '#fff',
              }}
            >
              카메라 연결 중...
            </div>
          )}

          {camReady && !wsReady && (
            <div
              style={{
                position: 'absolute',
                top: 12,
                right: 12,
                background:
                  'rgba(234, 179, 8, .9)',
                color: '#111',
                borderRadius: 99,
                padding:
                  '4px 10px',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              AI 연결 중...
            </div>
          )}

          {camReady && wsReady && (
            <div
              style={{
                position: 'absolute',
                top: 12,
                right: 12,
                background:
                  'rgba(16, 185, 129, .9)',
                color: '#fff',
                borderRadius: 99,
                padding:
                  '4px 10px',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              ● AI 분석 연결됨
            </div>
          )}

          {recording && (
            <div
              style={{
                position: 'absolute',
                top: 12,
                left: 12,
                background:
                  'rgba(239,68,68,.85)',
                color: '#fff',
                borderRadius: 99,
                padding:
                  '3px 10px',
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              ● REC
            </div>
          )}

        </div>

        {/* 질문 */}

        {currentQ && (
          <div className="card">

            <p
              style={{
                fontSize: 12,
                color:
                  'var(--text-secondary)',
                marginBottom: 6,
              }}
            >
              Q{currentQ.order}.
            </p>

            <p
              style={{
                fontSize: 17,
                fontWeight: 600,
                lineHeight: 1.6,
              }}
            >
              {currentQ.question_text}
            </p>

          </div>
        )}

        {/* 답변 */}

        <div
          className="card"
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
          }}
        >

          <div
            className="flex justify-between items-center"
            style={{
              marginBottom: 10,
            }}
          >

            <p
              style={{
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              답변 입력
            </p>

            <span
              style={{
                fontSize: 12,
                color:
                  'var(--text-secondary)',
              }}
            >
              {answer.length}자
            </span>

          </div>

          <textarea
            value={answer}
            onChange={(e) =>
              setAnswer(e.target.value)
            }
            placeholder="답변을 입력하거나 말씀하세요"
            style={{
              flex: 1,
              minHeight: 120,
              resize: 'none',
              border:
                '1.5px solid var(--border)',
              borderRadius:
                'var(--radius-md)',
              padding: 12,
              fontSize: 14,
              lineHeight: 1.6,
              width: '100%',
            }}
          />

          <div
            className="flex gap-8"
            style={{
              marginTop: 12,
            }}
          >

            {!recording && (
              <button
                className="btn btn-outline"
                onClick={handleRecord}
              >
                🎤 답변 시작
              </button>
            )}

            <button
              className="btn btn-primary w-full"
              onClick={handleNext}
            >
              {isLast
                ? '✅ 면접 종료'
                : '다음 질문 →'}
            </button>

          </div>

        </div>

      </div>

      {/* ======================================================
          오른쪽
      ======================================================= */}

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >

        {/* ==================================================
            실시간 분석
        =================================================== */}

        <div className="card">

          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              marginBottom: 16,
            }}
          >
            📊 실시간 분석
          </h3>

          <p
            style={{
              fontSize: 12,
              color:
                'var(--text-secondary)',
              marginBottom: 16,
            }}
          >
            {!camReady
              ? '카메라 연결 중...'
              : !wsReady
              ? 'AI 서버 연결 중...'
              : 'MediaPipe가 실시간으로 분석하고 있습니다.'}
          </p>

          {/* 얼굴 */}

          <div
            style={{
              display: 'flex',
              justifyContent:
                'space-between',
              alignItems: 'center',
              padding: '10px 0',
              borderBottom:
                '1px solid var(--border)',
            }}
          >

            <span
              style={{
                fontSize: 13,
                color:
                  'var(--text-secondary)',
              }}
            >
              얼굴
            </span>

            <span
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: faceDetected
                  ? 'var(--secondary)'
                  : 'var(--warning)',
              }}
            >
              {!feedback
                ? '확인 중'
                : faceDetected
                ? '✅ 감지됨'
                : '⚠️ 감지 안됨'}
            </span>

          </div>

          {/* 눈맞춤 */}

          <div
            style={{
              display: 'flex',
              justifyContent:
                'space-between',
              alignItems: 'center',
              padding: '10px 0',
              borderBottom:
                '1px solid var(--border)',
            }}
          >

            <span
              style={{
                fontSize: 13,
                color:
                  'var(--text-secondary)',
              }}
            >
              눈맞춤
            </span>

            <span
              style={{
                fontSize: 13,
                fontWeight: 500,
                color:
                  eyeContactScore !== null
                    ? 'var(--secondary)'
                    : 'var(--text-secondary)',
              }}
            >
              {formatScore(
                eyeContactScore
              )}
            </span>

          </div>

          {/* 깜빡임 */}

          <div
            style={{
              display: 'flex',
              justifyContent:
                'space-between',
              alignItems: 'center',
              padding: '10px 0',
              borderBottom:
                '1px solid var(--border)',
            }}
          >

            <span
              style={{
                fontSize: 13,
                color:
                  'var(--text-secondary)',
              }}
            >
              눈 깜빡임
            </span>

            <span
              style={{
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {formatScore(
                blinkScore
              )}
            </span>

          </div>

          {/* 표정 */}

          <div
            style={{
              display: 'flex',
              justifyContent:
                'space-between',
              alignItems: 'center',
              padding: '10px 0',
            }}
          >

            <span
              style={{
                fontSize: 13,
                color:
                  'var(--text-secondary)',
              }}
            >
              표정
            </span>

            <span
              style={{
                fontSize: 13,
                fontWeight: 500,
              }}
            >
              {formatScore(
                expressionScore
              )}
            </span>

          </div>

        </div>

        {/* ==================================================
            면접 팁
        =================================================== */}

        <div className="card">

          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              marginBottom: 12,
            }}
          >
            💡 면접 팁
          </h3>

          {[
            '카메라를 정면으로 바라보세요',
            '천천히 또렷하게 말하세요',
            '구체적인 사례를 들어 답변하세요',
            '자신감 있는 자세를 유지하세요',
          ].map((tip, i) => (
            <p
              key={i}
              style={{
                fontSize: 12,
                color:
                  'var(--text-secondary)',
                marginBottom: 8,
                lineHeight: 1.6,
              }}
            >
              · {tip}
            </p>
          ))}

        </div>

        {/* ==================================================
            상태
        =================================================== */}

        <div
          className="card"
          style={{
            background:
              'var(--primary-light)',
            border:
              '1px solid #C7D3FC',
          }}
        >

          <p
            style={{
              fontSize: 12,
              color: '#3A57E8',
              fontWeight: 500,
              marginBottom: 4,
            }}
          >
            🔬 AI 분석 상태
          </p>

          <p
            style={{
              fontSize: 12,
              color: '#4F6EF7',
              lineHeight: 1.7,
            }}
          >
            카메라:{' '}
            {camReady
              ? '연결됨'
              : '연결 중'}
            <br />

            WebSocket:{' '}
            {wsReady
              ? '연결됨'
              : '연결 중'}
            <br />

            MediaPipe:{' '}
            {feedback
              ? '분석 중'
              : '대기 중'}
          </p>

        </div>

      </div>

    </div>
  )
}
