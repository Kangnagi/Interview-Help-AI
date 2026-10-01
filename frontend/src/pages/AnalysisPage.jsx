import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useInterviewStore } from '@/store/interviewStore'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from 'recharts'


function getFaceAnalysis(analysis) {
  const face = analysis?.face_analysis || analysis?.faceAnalysis || {}
  const timeline = face.timeline || analysis?.face_analysis_timeline || analysis?.faceAnalysisTimeline || face.data || []

  const rows = Array.isArray(timeline) ? timeline.map((item, index) => ({
    time: Number(item.time_sec ?? item.time ?? item.elapsed_sec ?? index),
    face: Number(item.face_detected ?? item.faceDetected ?? item.face ?? 0),
    landmark: Number(item.landmark_detected ?? item.landmarkDetected ?? item.landmark ?? 0),
    landmarkCount: Number(item.landmark_count ?? item.landmarkCount ?? 0),
    blink: Number(item.blink_score ?? item.blinkScore ?? 0),
    expression: Number(item.expression_score ?? item.expressionScore ?? 0),
  })) : []

  const avg = (key) => {
    const values = rows.map(x => Number(x[key])).filter(Number.isFinite)
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
  }

  const rate = (key) => {
    if (!rows.length) return null
    return rows.filter(x => Number(x[key]) > 0).length / rows.length * 100
  }

  return {
    timeline: rows,
    faceRate: face.face_detection_rate ?? face.faceDetectionRate ?? rate('face'),
    landmarkRate: face.landmark_detection_rate ?? face.landmarkDetectionRate ?? rate('landmark'),
    avgBlink: face.average_blink ?? face.avg_blink ?? face.averageBlink ?? avg('blink'),
    avgExpression: face.average_expression ?? face.avg_expression ?? face.averageExpression ?? avg('expression'),
    available: rows.length > 0 || Object.keys(face).length > 0
  }
}

function FaceAnalysisSection({ analysis }) {
  const face = getFaceAnalysis(analysis)

  if (!face.available) {
    return (
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 8 }}>👤 얼굴 분석 결과</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.7 }}>
          이 면접에는 얼굴 분석 데이터가 아직 저장되지 않았습니다.
        </p>
      </div>
    )
  }

  const value = (v, suffix = '') =>
    v == null || !Number.isFinite(Number(v)) ? '—' : `${Number(v).toFixed(1)}${suffix}`

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>👤 얼굴 분석 결과</h3>
      <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 18 }}>
        면접 중 웹캠 프레임을 기반으로 측정한 결과입니다.
      </p>

      <div className="grid-2" style={{ gap: 12, marginBottom: 20 }}>
        {[
          ['얼굴 검출률', face.faceRate, '%'],
          ['랜드마크 검출률', face.landmarkRate, '%'],
          ['평균 눈 깜빡임', face.avgBlink, ''],
          ['평균 표정 점수', face.avgExpression, ''],
        ].map(([label, v, suffix]) => (
          <div key={label} style={{ padding: '16px 18px', border: '1px solid var(--border)', borderRadius: 10 }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 6 }}>{label}</p>
            <p style={{ fontSize: 25, fontWeight: 750 }}>{value(v, suffix)}</p>
          </div>
        ))}
      </div>

      {face.timeline.length > 0 && (
        <>
          <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>얼굴 인식 안정성</h4>
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={face.timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} tickFormatter={v => `${Number(v).toFixed(0)}초`} />
              <YAxis domain={[0, 1]} ticks={[0, 1]} tickFormatter={v => v ? '검출' : '미검출'} tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [Number(v) > 0 ? '검출됨' : '미검출']} labelFormatter={v => `${Number(v).toFixed(1)}초`} />
              <Legend />
              <Line type="stepAfter" dataKey="face" name="얼굴" dot={false} strokeWidth={2} />
              <Line type="stepAfter" dataKey="landmark" name="랜드마크" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <h4 style={{ fontSize: 14, fontWeight: 600, margin: '22px 0 10px' }}>눈 깜빡임 · 표정 변화</h4>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={face.timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} tickFormatter={v => `${Number(v).toFixed(0)}초`} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v, name) => [`${Number(v).toFixed(1)}점`, name]} labelFormatter={v => `${Number(v).toFixed(1)}초`} />
              <Legend />
              <Line type="monotone" dataKey="blink" name="눈 깜빡임" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="expression" name="표정" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>

          <h4 style={{ fontSize: 14, fontWeight: 600, margin: '22px 0 10px' }}>랜드마크 검출 개수</h4>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={face.timeline}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} tickFormatter={v => `${Number(v).toFixed(0)}초`} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [`${Number(v).toFixed(0)}개`, '랜드마크']} />
              <Line type="monotone" dataKey="landmarkCount" name="랜드마크" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}


export default function AnalysisPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const {
    fetchAnalysis,
    analysis,
  } = useInterviewStore()

  const [polling, setPolling] = useState(true)
  const [attempt, setAttempt] = useState(0)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    let timer = null
    let count = 0

    const poll = async () => {
      if (cancelled) return

      count++
      setAttempt(count)

      console.log(
        `[AnalysisPage] 분석 결과 확인 ${count}/60`
      )

      try {
        const data = await fetchAnalysis(id)

        if (cancelled) return

        console.log(
          '[AnalysisPage] 서버 응답:',
          data
        )

        // 분석 결과가 존재하면 완료
        if (data) {
          console.log(
            '[AnalysisPage] 🎉 분석 완료!',
            data
          )

          setPolling(false)
          return
        }

        // 아직 결과가 없으면 2초 후 다시 확인
        if (count < 60) {
          timer = setTimeout(poll, 2000)
        } else {
          console.error(
            '[AnalysisPage] 분석 시간 초과'
          )

          setError(
            '분석 시간이 너무 오래 걸리고 있습니다.'
          )

          setPolling(false)
        }

      } catch (err) {
        console.error(
          '[AnalysisPage] 분석 조회 오류:',
          err
        )

        if (!cancelled) {
          setError(
            '분석 결과를 확인하는 중 오류가 발생했습니다.'
          )
          setPolling(false)
        }
      }
    }

    // 첫 번째 조회는 즉시 실행
    poll()

    return () => {
      cancelled = true

      if (timer) {
        clearTimeout(timer)
      }
    }
  }, [id, fetchAnalysis])

  // ─────────────────────────────────────────────
  // 분석 대기 화면
  // ─────────────────────────────────────────────

  if (polling && !analysis) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: '80px 0',
        }}
      >
        <div
          className="spinner"
          style={{
            margin: '0 auto 16px',
          }}
        />

        <h3
          style={{
            fontSize: 18,
            fontWeight: 600,
            marginBottom: 8,
          }}
        >
          AI가 면접을 분석하고 있습니다
        </h3>

        <p
          style={{
            color: 'var(--text-secondary)',
            fontSize: 14,
          }}
        >
          잠시만 기다려주세요...
        </p>

        <p
          style={{
            color: 'var(--text-secondary)',
            fontSize: 12,
            marginTop: 12,
          }}
        >
          분석 확인 중 {attempt} / 60
        </p>
      </div>
    )
  }

  // ─────────────────────────────────────────────
  // 분석 실패
  // ─────────────────────────────────────────────

  if (!analysis) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: '80px 0',
        }}
      >
        <h3
          style={{
            fontSize: 18,
            fontWeight: 600,
            marginBottom: 12,
          }}
        >
          분석 결과를 불러오지 못했습니다
        </h3>

        <p
          style={{
            color: 'var(--text-secondary)',
            fontSize: 13,
          }}
        >
          {error ||
            '백엔드 분석 파이프라인을 확인해주세요.'}
        </p>

        <div
          style={{
            marginTop: 20,
            display: 'flex',
            justifyContent: 'center',
            gap: 10,
          }}
        >
          <button
            className="btn btn-primary btn-sm"
            onClick={() => window.location.reload()}
          >
            다시 확인
          </button>

          <button
            className="btn btn-outline btn-sm"
            onClick={() =>
              navigate('/dashboard')
            }
          >
            대시보드로
          </button>
        </div>
      </div>
    )
  }

  // ─────────────────────────────────────────────
  // 분석 결과
  // ─────────────────────────────────────────────

  const radarData = [
    {
      subject: '내용 충실도',
      score: analysis.content_score ?? 0,
    },
    {
      subject: '질문 관련성',
      score: analysis.relevance_score ?? 0,
    },
    {
      subject: '명확성',
      score: analysis.clarity_score ?? 0,
    },
    {
      subject: '음성 품질',
      score: analysis.speech_score ?? 0,
    },
    {
      subject: '자세',
      score: analysis.posture_score ?? 0,
    },
    {
      subject: '눈맞춤',
      score: analysis.eye_contact_score ?? 0,
    },
  ]

  const totalScore =
    analysis.total_score ?? 0

  const totalColor =
    totalScore >= 80
      ? 'var(--secondary)'
      : totalScore >= 60
        ? 'var(--warning)'
        : 'var(--danger)'

  return (
    <div
      style={{
        maxWidth: 800,
        margin: '0 auto',
      }}
    >
      {/* 제목 */}
      <div
        className="flex justify-between items-center"
        style={{ marginBottom: 28 }}
      >
        <div>
          <h2
            style={{
              fontSize: 22,
              fontWeight: 700,
            }}
          >
            면접 분석 결과
          </h2>

          <p
            style={{
              color: 'var(--text-secondary)',
              marginTop: 4,
              fontSize: 14,
            }}
          >
            AI 기반 종합 평가
          </p>
        </div>

        <button
          className="btn btn-outline btn-sm"
          onClick={() =>
            navigate('/dashboard')
          }
        >
          ← 대시보드
        </button>
      </div>

      {/* 종합 점수 */}
      <div
        className="card"
        style={{
          textAlign: 'center',
          marginBottom: 20,
          padding: 36,
        }}
      >
        <p
          style={{
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginBottom: 8,
          }}
        >
          종합 점수
        </p>

        <p
          style={{
            fontSize: 64,
            fontWeight: 800,
            color: totalColor,
            lineHeight: 1,
          }}
        >
          {analysis.total_score != null
            ? Number(
                analysis.total_score
              ).toFixed(0)
            : '—'}
        </p>

        <p
          style={{
            fontSize: 14,
            color: 'var(--text-secondary)',
            marginTop: 4,
          }}
        >
          / 100점
        </p>

        {analysis.feedback_summary && (
          <p
            style={{
              marginTop: 16,
              color: 'var(--text-secondary)',
              fontSize: 14,
              lineHeight: 1.7,
            }}
          >
            {analysis.feedback_summary}
          </p>
        )}
      </div>

      {/* 영역별 점수 */}
      <div
        className="grid-2"
        style={{ marginBottom: 20 }}
      >
        <div className="card">
          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              marginBottom: 16,
            }}
          >
            영역별 점수
          </h3>

          <ResponsiveContainer
            width="100%"
            height={240}
          >
            <RadarChart data={radarData}>
              <PolarGrid />

              <PolarAngleAxis
                dataKey="subject"
                tick={{ fontSize: 11 }}
              />

              <Radar
                name="점수"
                dataKey="score"
                stroke="#4F6EF7"
                fill="#4F6EF7"
                fillOpacity={0.25}
              />

              <Tooltip
                formatter={(v) => [
                  `${Number(v).toFixed(1)}점`,
                ]}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* 세부 점수 */}
        <div className="card">
          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              marginBottom: 16,
            }}
          >
            세부 항목
          </h3>

          {radarData.map(
            ({ subject, score }) => (
              <div
                key={subject}
                style={{
                  marginBottom: 12,
                }}
              >
                <div
                  className="flex justify-between"
                  style={{
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: 13,
                    }}
                  >
                    {subject}
                  </span>

                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                    }}
                  >
                    {Number(score).toFixed(0)}
                    점
                  </span>
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
                      width: `${Math.min(
                        100,
                        Math.max(0, score)
                      )}%`,
                      height: '100%',
                      background:
                        'var(--primary)',
                      transition:
                        'width 1s',
                      borderRadius: 99,
                    }}
                  />
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* 얼굴 분석 */}
      <FaceAnalysisSection analysis={analysis} />

      {/* 강점 / 개선점 */}
      <div
        className="grid-2"
        style={{ marginBottom: 20 }}
      >
        <div
          className="card"
          style={{
            border: '1px solid #D1FAE5',
            background: '#F0FDF4',
          }}
        >
          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: '#065F46',
              marginBottom: 12,
            }}
          >
            ✅ 강점
          </h3>

          {(analysis.strengths || []).map(
            (s, i) => (
              <p
                key={i}
                style={{
                  fontSize: 13,
                  color: '#047857',
                  marginBottom: 6,
                  lineHeight: 1.6,
                }}
              >
                · {s}
              </p>
            )
          )}

          {!analysis.strengths?.length && (
            <p
              style={{
                fontSize: 13,
                color: '#9CA3AF',
              }}
            >
              분석된 강점이 없습니다.
            </p>
          )}
        </div>

        <div
          className="card"
          style={{
            border: '1px solid #FED7AA',
            background: '#FFF7ED',
          }}
        >
          <h3
            style={{
              fontWeight: 600,
              fontSize: 14,
              color: '#92400E',
              marginBottom: 12,
            }}
          >
            📈 개선점
          </h3>

          {(analysis.improvements || []).map(
            (s, i) => (
              <p
                key={i}
                style={{
                  fontSize: 13,
                  color: '#B45309',
                  marginBottom: 6,
                  lineHeight: 1.6,
                }}
              >
                · {s}
              </p>
            )
          )}

          {!analysis.improvements?.length && (
            <p
              style={{
                fontSize: 13,
                color: '#9CA3AF',
              }}
            >
              분석된 개선점이 없습니다.
            </p>
          )}
        </div>
      </div>

      <button
        className="btn btn-primary w-full btn-lg"
        onClick={() =>
          navigate('/interview/setup')
        }
      >
        🎤 다시 면접하기
      </button>
    </div>
  )
}