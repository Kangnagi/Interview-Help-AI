import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'

export default function ResumeHistoryPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const resume = useResumeStore((s) => s.getResume(id))

  if (!resume) return (
    <div style={{ textAlign: 'center', padding: '80px 0' }}>
      <p>자기소개서를 찾을 수 없습니다.</p>
      <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/resume')}>목록으로</button>
    </div>
  )

  const records = resume.interviewRecords || []
  const fmt = (iso) => new Date(iso).toLocaleString('ko-KR')
  const dur = (sec) => {
    const m = Math.floor(sec / 60), s = sec % 60
    return `${m}분 ${s}초`
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <style>{`
        .rh-head { display:flex; align-items:center; gap:12px; margin-bottom:24px; }
        .rh-badge { background:var(--primary-light); color:var(--primary); font-size:12px; font-weight:600; padding:3px 10px; border-radius:99px; }
        .rh-card { background:#fff; border-radius:var(--radius-lg); border:1px solid var(--border); padding:20px; margin-bottom:14px; }
        .rh-card-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
        .rh-type { display:flex; align-items:center; gap:6px; font-weight:600; font-size:15px; }
        .rh-date { font-size:13px; color:var(--text-muted); }
        .rh-q { background:#f9fafb; border-radius:8px; padding:12px; margin-top:8px; font-size:14px; }
        .rh-q-label { font-size:12px; font-weight:600; color:var(--text-muted); margin-bottom:4px; }
        .rh-empty { text-align:center; padding:60px 0; color:var(--text-muted); }
      `}</style>

      <div className="rh-head">
        <button onClick={() => navigate('/resume')} style={{ background: '#f3f4f6', border: 'none', borderRadius: 8, padding: '8px 14px', cursor: 'pointer', fontSize: 14 }}>← 목록으로</button>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700 }}>{resume.title}</h2>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{resume.companyName} · {resume.jobTitle}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
        <button className="btn btn-primary btn-sm" onClick={() => navigate(`/interview/practice/${id}`)}>🎓 연습 면접 시작</button>
        <button className="btn btn-outline btn-sm" onClick={() => navigate(`/interview/real/${id}`)}>🎯 실전 면접 시작</button>
        <button className="btn btn-outline btn-sm" onClick={() => navigate(`/resume/${id}/edit`)}>✏️ 자기소개서 수정</button>
      </div>

      <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14, color: 'var(--text-secondary)' }}>📋 면접 기록 ({records.length}건)</h3>

      {records.length === 0 ? (
        <div className="rh-empty">
          <div style={{ fontSize: 48, marginBottom: 12 }}>🎤</div>
          <p>아직 면접 기록이 없습니다.</p>
        </div>
      ) : (
        records.map((rec) => (
          <div key={rec.id} className="rh-card">
            <div className="rh-card-head">
              <div className="rh-type">
                {rec.type === 'practice' ? '🎓 연습 면접' : '🎯 실전 면접'}
                {rec.score != null && (
                  <span style={{ fontSize: 13, color: '#10b981', fontWeight: 600 }}>점수 {rec.score}점</span>
                )}
              </div>
              <div>
                <span className="rh-date">{fmt(rec.date)}</span>
                {rec.duration > 0 && <span className="rh-date" style={{ marginLeft: 10 }}>⏱ {dur(rec.duration)}</span>}
              </div>
            </div>
            {rec.questions?.length > 0 && (
              <div>
                <div className="rh-q-label">면접 질문 ({rec.questions.length}개)</div>
                {rec.questions.slice(0, 3).map((q, i) => (
                  <div key={i} className="rh-q">Q{i + 1}. {q.question || q}</div>
                ))}
                {rec.questions.length > 3 && (
                  <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>외 {rec.questions.length - 3}개</div>
                )}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}
