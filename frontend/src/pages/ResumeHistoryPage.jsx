import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import { interviewAPI, analysisAPI } from '@/services/api'

export default function ResumeHistoryPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const resume = useResumeStore((s) => s.getResume(id))

  const [backendRecords, setBackendRecords] = useState([])
  const [scoreMap, setScoreMap] = useState({})
  const [loadingScores, setLoadingScores] = useState(false)

  useEffect(() => {
    interviewAPI.list()
      .then(({ data }) => {
        const related = data
          .filter((iv) => iv.resume_ref_id === id)
          .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        setBackendRecords(related)

        const completed = related.filter((iv) => iv.status === 'completed')
        if (completed.length === 0) return
        setLoadingScores(true)
        Promise.allSettled(
          completed.map((iv) => analysisAPI.get(iv.id).then(({ data: a }) => ({ id: iv.id, score: a.total_score })))
        ).then((results) => {
          const map = {}
          results.forEach((r) => { if (r.status === 'fulfilled') map[r.value.id] = r.value.score })
          setScoreMap(map)
          setLoadingScores(false)
        })
      })
      .catch(() => {})
  }, [id])

  if (!resume) return (
    <div style={{ textAlign: 'center', padding: '80px 0' }}>
      <p>자기소개서를 찾을 수 없습니다.</p>
      <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/resume')}>목록으로</button>
    </div>
  )

  // localStorage 기록 (구버전 데이터 포함 표시)
  const localRecords = resume.interviewRecords || resume.interviewHistory || []

  const fmt = (iso) => new Date(iso).toLocaleString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  const dur = (sec) => {
    if (!sec) return ''
    const m = Math.floor(sec / 60), s = sec % 60
    return `${m}분 ${s}초`
  }

  const typeLabel = (type) => type === 'real' ? { icon: '🎯', text: '실전 면접', color: '#f59e0b' } : { icon: '🎓', text: '연습 면접', color: '#4f6ef7' }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <style>{`
        .rh-head { display:flex; align-items:center; gap:12px; margin-bottom:24px; }
        .rh-card { background:#fff; border-radius:var(--radius-lg); border:1px solid var(--border); padding:20px; margin-bottom:14px; }
        .rh-card-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
        .rh-type { display:flex; align-items:center; gap:6px; font-weight:600; font-size:15px; }
        .rh-date { font-size:13px; color:var(--text-muted); }
        .rh-q { background:#f9fafb; border-radius:8px; padding:10px 12px; margin-top:6px; font-size:13px; color:var(--text-secondary); }
        .rh-empty { text-align:center; padding:60px 0; color:var(--text-muted); }
      `}</style>

      <div className="rh-head">
        <button onClick={() => navigate('/resume')} style={{ background: '#f3f4f6', border: 'none', borderRadius: 8, padding: '8px 14px', cursor: 'pointer', fontSize: 14 }}>← 목록으로</button>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>{resume.title}</h2>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{resume.companyName} · {resume.jobTitle}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 28 }}>
        <button className="btn btn-primary btn-sm" onClick={() => navigate(`/interview/practice/${id}`)}>🎓 연습 면접 시작</button>
        <button className="btn btn-outline btn-sm" onClick={() => navigate(`/interview/real/${id}`)}>🎯 실전 면접 시작</button>
        <button className="btn btn-outline btn-sm" onClick={() => navigate(`/resume/${id}/edit`)}>✏️ 자기소개서 수정</button>
      </div>

      {backendRecords.length > 0 && (
        <section style={{ marginBottom: 32 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14, color: 'var(--text-secondary)' }}>
            📊 AI 분석 면접 기록 ({backendRecords.length}건)
          </h3>
          {backendRecords.map((iv) => {
            const tl = typeLabel(iv.interview_type)
            const score = scoreMap[iv.id]
            return (
              <div key={iv.id} className="rh-card">
                <div className="rh-card-head">
                  <div className="rh-type">
                    <span style={{ color: tl.color }}>{tl.icon} {tl.text}</span>
                    {iv.status === 'completed' && (
                      score != null
                        ? <span style={{ fontSize: 13, color: '#10b981', fontWeight: 700, marginLeft: 8 }}>{score.toFixed(0)}점</span>
                        : loadingScores
                          ? <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 8 }}>점수 로딩 중...</span>
                          : null
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="rh-date">{fmt(iv.created_at)}</span>
                    {iv.status === 'completed' && (
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => navigate(`/interview/${iv.id}/result`)}
                        style={{ fontSize: 11 }}
                      >
                        📊 분석 보기
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {iv.total_questions}개 질문
                  {iv.status === 'completed' ? ' · 분석 완료' : iv.status === 'in_progress' ? ' · 진행 중' : ' · 분석 대기'}
                </div>
              </div>
            )
          })}
        </section>
      )}

      {localRecords.length > 0 && (
        <section>
          <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14, color: 'var(--text-secondary)' }}>
            📋 이전 면접 기록 ({localRecords.length}건)
          </h3>
          {localRecords.map((rec) => {
            const tl = typeLabel(rec.type)
            return (
              <div key={rec.id} className="rh-card">
                <div className="rh-card-head">
                  <div className="rh-type">
                    <span style={{ color: tl.color }}>{tl.icon} {tl.text}</span>
                    {rec.score != null && (
                      <span style={{ fontSize: 13, color: '#10b981', fontWeight: 600, marginLeft: 8 }}>점수 {rec.score}점</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="rh-date">{fmt(rec.createdAt || rec.date)}</span>
                    {rec.duration > 0 && <span className="rh-date">⏱ {dur(rec.duration)}</span>}
                    {rec.interviewId && (
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => navigate(`/interview/${rec.interviewId}/result`)}
                        style={{ fontSize: 11 }}
                      >
                        📊 분석 보기
                      </button>
                    )}
                  </div>
                </div>
                {rec.questions?.length > 0 && (
                  <div>
                    {rec.questions.slice(0, 3).map((q, i) => (
                      <div key={i} className="rh-q">Q{i + 1}. {q.question || q}</div>
                    ))}
                    {rec.questions.length > 3 && (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>외 {rec.questions.length - 3}개</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </section>
      )}

      {backendRecords.length === 0 && localRecords.length === 0 && (
        <div className="rh-empty">
          <div style={{ fontSize: 48, marginBottom: 12 }}>🎤</div>
          <p>아직 면접 기록이 없습니다.</p>
          <p style={{ fontSize: 13, marginTop: 8 }}>위 버튼을 눌러 첫 번째 면접을 시작해보세요!</p>
        </div>
      )}
    </div>
  )
}
