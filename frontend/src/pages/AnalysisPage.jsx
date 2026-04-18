import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useInterviewStore } from '@/store/interviewStore'
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip } from 'recharts'

export default function AnalysisPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { fetchAnalysis, analysis, loading } = useInterviewStore()
  const [polling, setPolling] = useState(true)

  useEffect(() => {
    let count = 0
    const timer = setInterval(async () => {
      const data = await fetchAnalysis(id)
      count++
      if (data || count > 10) {
        clearInterval(timer)
        setPolling(false)
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [id])

  if (loading || polling && !analysis) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <div className="spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ color: 'var(--text-secondary)' }}>AI가 면접을 분석하고 있습니다...</p>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <p>분석 결과를 불러올 수 없습니다</p>
        <button className="btn btn-outline btn-sm" style={{ marginTop: 12 }} onClick={() => navigate('/dashboard')}>
          대시보드로
        </button>
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

      <button className="btn btn-primary w-full btn-lg" onClick={() => navigate('/interview/setup')}>
        🎤 다시 면접하기
      </button>
    </div>
  )
}
