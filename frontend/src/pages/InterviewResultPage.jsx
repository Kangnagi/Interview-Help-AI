import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { analysisAPI } from '@/services/api'
import AnswerRating from '@/components/Common/AnswerRating'
import ConsentBanner from '@/components/Common/ConsentBanner'

const scoreColor = (s) => s >= 80 ? '#22c55e' : s >= 60 ? '#f59e0b' : '#ef4444'
const scoreBg    = (s) => s >= 80 ? 'rgba(34,197,94,.15)' : s >= 60 ? 'rgba(245,158,11,.15)' : 'rgba(239,68,68,.15)'

function ScoreBar({ score }) {
  const s = score || 0
  return (
    <div style={{ height: 6, background: 'rgba(255,255,255,.08)', borderRadius: 3, overflow: 'hidden', marginTop: 6 }}>
      <div style={{ height: '100%', width: `${s}%`, background: scoreColor(s), borderRadius: 3, transition: 'width 1s ease' }} />
    </div>
  )
}

function ScoreCard({ label, score }) {
  const s = Math.round(score) || 0
  return (
    <div style={{ background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 12, padding: '14px 16px' }}>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,.45)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: scoreColor(s) }}>{s}<span style={{ fontSize: 13, fontWeight: 400, color: 'rgba(255,255,255,.35)', marginLeft: 2 }}>점</span></div>
      <ScoreBar score={s} />
    </div>
  )
}

export default function InterviewResultPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)
  const [error, setError] = useState(null)
  const [openQ, setOpenQ] = useState(null)

  useEffect(() => {
    let mounted = true
    let timer = null

    const fetch = async () => {
      try {
        const { data } = await analysisAPI.get(id)
        if (!mounted) return
        if (!data.total_score) {
          setPolling(true)
          timer = setTimeout(fetch, 3000)
        } else {
          setPolling(false)
          setResult(data)
          setLoading(false)
        }
      } catch (err) {
        if (!mounted) return
        setError(err.response?.data?.detail || '분석 결과를 불러오지 못했습니다.')
        setLoading(false)
      }
    }

    fetch()
    return () => { mounted = false; clearTimeout(timer) }
  }, [id])

  if (loading) return (
    <div style={{ minHeight: '100vh', background: '#0a0d1a', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#fff', gap: 16 }}>
      <div style={{ width: 40, height: 40, border: '3px solid rgba(255,255,255,.15)', borderTopColor: '#4f6ef7', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{ fontSize: 15, color: 'rgba(255,255,255,.5)' }}>
        {polling ? 'AI 분석 진행 중입니다... (잠시만 기다려 주세요)' : '결과를 불러오는 중...'}
      </div>
    </div>
  )

  if (error) return (
    <div style={{ minHeight: '100vh', background: '#0a0d1a', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#fff', gap: 16 }}>
      <div style={{ fontSize: 14, color: '#ef4444' }}>{error}</div>
      <button onClick={() => navigate(-1)} style={{ background: 'rgba(255,255,255,.08)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 8, padding: '10px 24px', color: '#fff', cursor: 'pointer' }}>돌아가기</button>
    </div>
  )

  if (!result) return null

  const total = Math.round(result.total_score || 0)
  const qFeedbacks = result.question_feedbacks || []

  return (
    <div style={{ minHeight: '100vh', background: '#0a0d1a', fontFamily: 'inherit', color: '#fff' }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:none; } }
        .fade-up { animation: fadeUp .4s ease forwards; }
        .q-card { background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.08); border-radius: 14px; margin-bottom: 12px; overflow: hidden; }
        .q-header { display:flex; align-items:center; justify-content:space-between; padding: 16px 20px; cursor:pointer; gap:12px; }
        .q-header:hover { background: rgba(255,255,255,.04); }
        .q-body { padding: 0 20px 20px; }
      `}</style>

      <div style={{ maxWidth: 820, margin: '0 auto', padding: '32px 20px' }}>

        {/* 헤더 */}
        <div className="fade-up" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#4f6ef7', letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: 4 }}>Interview Analysis</div>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>면접 분석 결과</h1>
          </div>
          <button onClick={() => navigate('/resume')} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 10, padding: '9px 20px', color: 'rgba(255,255,255,.6)', fontSize: 13, cursor: 'pointer' }}>← 목록으로</button>
        </div>

        {/* 종합 점수 */}
        <div className="fade-up" style={{ background: 'linear-gradient(135deg, rgba(79,110,247,.15), rgba(16,185,129,.1))', border: '1px solid rgba(79,110,247,.25)', borderRadius: 18, padding: '28px 32px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 28 }}>
            <div style={{ textAlign: 'center', flexShrink: 0 }}>
              <div style={{ width: 100, height: 100, borderRadius: '50%', background: `conic-gradient(${scoreColor(total)} ${total}%, rgba(255,255,255,.08) 0)`, display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
                <div style={{ width: 80, height: 80, borderRadius: '50%', background: '#0d1024', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontSize: 26, fontWeight: 800, color: scoreColor(total), lineHeight: 1 }}>{total}</span>
                  <span style={{ fontSize: 11, color: 'rgba(255,255,255,.4)' }}>/ 100</span>
                </div>
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'rgba(255,255,255,.4)' }}>종합 점수</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,.35)', marginBottom: 8 }}>AI 면접관 총평</div>
              <p style={{ margin: 0, fontSize: 14, lineHeight: 1.8, color: 'rgba(255,255,255,.8)' }}>
                {result.feedback_summary || '분석이 아직 완료되지 않았습니다.'}
              </p>
            </div>
          </div>
        </div>

        {/* 영역별 점수 */}
        <div className="fade-up" style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,.35)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '.08em' }}>영역별 점수</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
            <ScoreCard label="내용 적절성" score={result.content_score} />
            <ScoreCard label="질문 관련성" score={result.relevance_score} />
            <ScoreCard label="명확성 · 논리" score={result.clarity_score} />
            <ScoreCard label="발화 품질" score={result.speech_score} />
            <ScoreCard label="자세" score={result.posture_score} />
            <ScoreCard label="눈맞춤" score={result.eye_contact_score} />
          </div>
        </div>

        {/* 강점 & 개선점 */}
        {((result.strengths?.length > 0) || (result.improvements?.length > 0)) && (
          <div className="fade-up" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
            {/* 강점 */}
            <div style={{ background: 'rgba(34,197,94,.07)', border: '1px solid rgba(34,197,94,.2)', borderRadius: 14, padding: '20px 22px' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#22c55e', marginBottom: 14 }}>✨ 강점</div>
              {result.strengths?.length > 0 ? (
                <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {result.strengths.map((s, i) => (
                    <li key={i} style={{ display: 'flex', gap: 8, fontSize: 13, color: 'rgba(255,255,255,.8)', lineHeight: 1.6 }}>
                      <span style={{ color: '#22c55e', flexShrink: 0, marginTop: 2 }}>•</span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ fontSize: 13, color: 'rgba(255,255,255,.3)' }}>분석 중...</div>
              )}
            </div>
            {/* 개선점 */}
            <div style={{ background: 'rgba(245,158,11,.07)', border: '1px solid rgba(245,158,11,.2)', borderRadius: 14, padding: '20px 22px' }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#f59e0b', marginBottom: 14 }}>📈 개선점</div>
              {result.improvements?.length > 0 ? (
                <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {result.improvements.map((imp, i) => (
                    <li key={i} style={{ display: 'flex', gap: 8, fontSize: 13, color: 'rgba(255,255,255,.8)', lineHeight: 1.6 }}>
                      <span style={{ color: '#f59e0b', flexShrink: 0, marginTop: 2 }}>•</span>
                      <span>{imp}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div style={{ fontSize: 13, color: 'rgba(255,255,255,.3)' }}>분석 중...</div>
              )}
            </div>
          </div>
        )}

        {/* 질문별 상세 피드백 */}
        {qFeedbacks.length > 0 && (
          <div className="fade-up">
            <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,.35)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '.08em' }}>질문별 상세 피드백</div>
            <ConsentBanner theme="dark" />
            {qFeedbacks.map((q) => {
              const isOpen = openQ === q.id
              const score = Math.round(q.ai_score || 0)
              return (
                <div key={q.id} className="q-card">
                  <div className="q-header" onClick={() => setOpenQ(isOpen ? null : q.id)}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#4f6ef7', flexShrink: 0, marginTop: 2 }}>Q{q.order}</span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: 'rgba(255,255,255,.85)', lineHeight: 1.5 }}>{q.question_text}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      {score > 0 && (
                        <div style={{ padding: '3px 10px', borderRadius: 99, background: scoreBg(score), color: scoreColor(score), fontSize: 12, fontWeight: 700 }}>{score}점</div>
                      )}
                      <span style={{ color: 'rgba(255,255,255,.25)', fontSize: 12, transition: 'transform .2s', transform: isOpen ? 'rotate(180deg)' : 'none' }}>▼</span>
                    </div>
                  </div>
                  {isOpen && (
                    <div className="q-body">
                      {/* 답변 */}
                      <div style={{ background: 'rgba(255,255,255,.04)', borderRadius: 8, padding: '12px 14px', marginBottom: 12 }}>
                        <div style={{ fontSize: 11, color: 'rgba(255,255,255,.3)', marginBottom: 5 }}>내 답변</div>
                        <div style={{ fontSize: 13, color: 'rgba(255,255,255,.65)', lineHeight: 1.7 }}>{q.answer_text || '(답변 없음)'}</div>
                      </div>
                      {/* 피드백 */}
                      {q.ai_feedback && (
                        <div style={{ background: 'rgba(79,110,247,.08)', border: '1px solid rgba(79,110,247,.2)', borderRadius: 8, padding: '12px 14px' }}>
                          <div style={{ fontSize: 11, color: '#6d85f8', marginBottom: 6 }}>AI 피드백</div>
                          <div style={{ fontSize: 13, color: 'rgba(255,255,255,.75)', lineHeight: 1.75, whiteSpace: 'pre-line' }}>{q.ai_feedback}</div>
                        </div>
                      )}
                      {q.ai_score != null && <AnswerRating interviewId={id} questionId={q.id} theme="dark" />}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

      </div>
    </div>
  )
}
