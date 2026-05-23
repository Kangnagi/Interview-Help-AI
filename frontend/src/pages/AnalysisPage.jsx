import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useInterviewStore } from '@/store/interviewStore'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'

export default function AnalysisPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { fetchAnalysis, analysis, loading, resetAnalysis } = useInterviewStore()
  const [polling, setPolling] = useState(true)

  // Clear stale analysis from a previous interview on mount
  useEffect(() => {
    resetAnalysis()
  }, [id])

  useEffect(() => {
    let count = 0
    const timer = setInterval(async () => {
      const data = await fetchAnalysis(id)
      count++
      if (data || count > 20) {
        clearInterval(timer)
        setPolling(false)
      }
    }, 3000)
    return () => clearInterval(timer)
  }, [id])

  if (loading || (polling && !analysis)) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <div className="spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ color: 'var(--text-secondary)' }}>AI가 면접을 분석하고 있습니다...</p>
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 8 }}>최대 60초 소요될 수 있습니다</p>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <p>분석 결과를 불러올 수 없습니다</p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 12 }}>
          <button className="btn btn-outline btn-sm" onClick={() => window.location.reload()}>다시 시도</button>
          <button className="btn btn-outline btn-sm" onClick={() => navigate('/dashboard')}>대시보드로</button>
        </div>
      </div>
    )
  }

  const radarData = [
    { subject: '내용 충실도', score: analysis.content_score    ?? 0 },
    { subject: '질문 관련성', score: analysis.relevance_score  ?? 0 },
    { subject: '명확성',     score: analysis.clarity_score    ?? 0 },
    { subject: '음성 품질',  score: analysis.speech_score     ?? 0 },
    { subject: '자세',       score: analysis.posture_score    ?? 0 },
    { subject: '눈맞춤',     score: analysis.eye_contact_score ?? 0 },
  ]

  const totalColor = analysis.total_score >= 80 ? 'var(--secondary)' : analysis.total_score >= 60 ? 'var(--warning)' : 'var(--danger)'
  const answeredQuestions = (analysis.question_feedbacks || []).filter((q) => q.answer_text)

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div className="flex justify-between items-center" style={{ marginBottom: 28 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700 }}>면접 분석 결과</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: 4, fontSize: 14 }}>AI 기반 종합 평가</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/dashboard')}>← 대시보드</button>
      </div>

      {/* 종합 점수 */}
      <div className="card" style={{ textAlign: 'center', marginBottom: 20, padding: 36 }}>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>종합 점수</p>
        <p style={{ fontSize: 64, fontWeight: 800, color: totalColor, lineHeight: 1 }}>
          {analysis.total_score?.toFixed(0) ?? '—'}
        </p>
        <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>/ 100점</p>
        {analysis.feedback_summary && (
          <p style={{ marginTop: 16, color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.7 }}>
            {analysis.feedback_summary}
          </p>
        )}
      </div>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        {/* 레이더 차트 */}
        <div className="card">
          <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>영역별 점수</h3>
          <ResponsiveContainer width="100%" height={240}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
              <Radar name="점수" dataKey="score" stroke="#4F6EF7" fill="#4F6EF7" fillOpacity={0.25} />
              <Tooltip formatter={(v) => [`${v.toFixed(1)}점`]} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* 세부 점수 */}
        <div className="card">
          <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>세부 항목</h3>
          {radarData.map(({ subject, score }) => (
            <div key={subject} style={{ marginBottom: 12 }}>
              <div className="flex justify-between" style={{ marginBottom: 4 }}>
                <span style={{ fontSize: 13 }}>{subject}</span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{score.toFixed(0)}점</span>
              </div>
              <div style={{ height: 6, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{ width: `${score}%`, height: '100%', background: 'var(--primary)', transition: 'width 1s', borderRadius: 99 }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 강점 / 개선점 */}
      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card" style={{ border: '1px solid #D1FAE5', background: '#F0FDF4' }}>
          <h3 style={{ fontWeight: 600, fontSize: 14, color: '#065F46', marginBottom: 12 }}>✅ 강점</h3>
          {(analysis.strengths || []).map((s, i) => (
            <p key={i} style={{ fontSize: 13, color: '#047857', marginBottom: 6, lineHeight: 1.6 }}>· {s}</p>
          ))}
          {!analysis.strengths?.length && <p style={{ fontSize: 13, color: '#9CA3AF' }}>분석 중...</p>}
        </div>
        <div className="card" style={{ border: '1px solid #FED7AA', background: '#FFF7ED' }}>
          <h3 style={{ fontWeight: 600, fontSize: 14, color: '#92400E', marginBottom: 12 }}>📈 개선점</h3>
          {(analysis.improvements || []).map((s, i) => (
            <p key={i} style={{ fontSize: 13, color: '#B45309', marginBottom: 6, lineHeight: 1.6 }}>· {s}</p>
          ))}
          {!analysis.improvements?.length && <p style={{ fontSize: 13, color: '#9CA3AF' }}>분석 중...</p>}
        </div>
      </div>

      {/* 질문별 상세 분석 */}
      {answeredQuestions.length > 0 && (
        <div className="card" style={{ marginBottom: 20 }}>
          <h3 style={{ fontWeight: 600, fontSize: 14, marginBottom: 20 }}>📝 질문별 상세 분석</h3>
          {answeredQuestions.map((q, i) => {
            const scoreColor = q.ai_score >= 80 ? 'var(--secondary)' : q.ai_score >= 60 ? 'var(--warning)' : 'var(--danger)'
            const isLast = i === answeredQuestions.length - 1
            return (
              <div
                key={q.id}
                style={{
                  marginBottom: isLast ? 0 : 24,
                  paddingBottom: isLast ? 0 : 24,
                  borderBottom: isLast ? 'none' : '1px solid var(--border)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10, gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--primary)', marginRight: 8 }}>Q{q.order}</span>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{q.question_text}</span>
                  </div>
                  {q.ai_score != null && (
                    <span style={{ fontSize: 17, fontWeight: 800, color: scoreColor, flexShrink: 0 }}>
                      {Math.round(q.ai_score)}점
                    </span>
                  )}
                </div>

                {q.answer_text && (
                  <div style={{ background: 'var(--bg-secondary, rgba(0,0,0,.04))', borderRadius: 8, padding: '10px 14px', marginBottom: 10 }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 5 }}>내 답변</div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{q.answer_text}</div>
                  </div>
                )}

                {q.ai_feedback ? (
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, paddingLeft: 2 }}>
                    💬 {q.ai_feedback}
                  </div>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>피드백 없음</div>
                )}

                {q.ai_score != null && (
                  <div style={{ marginTop: 10, height: 5, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
                    <div style={{ width: `${q.ai_score}%`, height: '100%', background: scoreColor, borderRadius: 99, transition: 'width 1.2s' }} />
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <button className="btn btn-primary w-full btn-lg" onClick={() => navigate('/resume')}>
        🎤 다시 면접하기
      </button>
    </div>
  )
}
