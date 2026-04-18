import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useInterviewStore } from '@/store/interviewStore'

const STATUS_BADGE = {
  pending:     { cls: 'badge-amber', label: '대기중' },
  in_progress: { cls: 'badge-blue',  label: '진행중' },
  completed:   { cls: 'badge-green', label: '완료' },
  cancelled:   { cls: 'badge-red',   label: '취소' },
}

const CATEGORY_LABEL = {
  general:    '일반',
  technical:  '기술',
  behavioral: '인성',
  self_intro: '자기소개',
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { interviews, fetchInterviews, loading } = useInterviewStore()
  const navigate = useNavigate()

  useEffect(() => { fetchInterviews() }, [])

  const completed = interviews.filter((i) => i.status === 'completed')
  const avgScore  = completed.length ? '—' : '—'  // 분석 후 채움

  return (
    <div>
      {/* 인사말 */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>안녕하세요, {user?.username}님 👋</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>오늘도 면접 준비 열심히 해봐요!</p>
      </div>

      {/* 통계 카드 */}
      <div className="grid-3" style={{ marginBottom: 28 }}>
        {[
          { label: '총 면접 횟수',  value: interviews.length,  color: 'var(--primary)' },
          { label: '완료된 면접',   value: completed.length,   color: 'var(--secondary)' },
          { label: '평균 점수',     value: avgScore,            color: 'var(--warning)' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card" style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 32, fontWeight: 700, color }}>{value}</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>{label}</p>
          </div>
        ))}
      </div>

      {/* 빠른 시작 */}
      <div className="card" style={{ marginBottom: 28, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontWeight: 600, fontSize: 16 }}>새 면접 시작하기</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            AI가 실시간으로 피드백을 제공합니다
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/interview/setup')}>
          🎤 면접 시작
        </button>
      </div>

      {/* 최근 면접 목록 */}
      <div className="card">
        <div className="flex justify-between items-center" style={{ marginBottom: 16 }}>
          <h3 style={{ fontWeight: 600, fontSize: 16 }}>최근 면접</h3>
          <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>전체 보기</button>
        </div>

        {loading && <div className="text-center text-muted" style={{ padding: 24 }}>불러오는 중...</div>}

        {!loading && interviews.length === 0 && (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-secondary)' }}>
            <p style={{ fontSize: 32, marginBottom: 8 }}>🎤</p>
            <p>아직 면접 기록이 없습니다</p>
            <button
              className="btn btn-primary btn-sm"
              style={{ marginTop: 12 }}
              onClick={() => navigate('/interview/setup')}
            >
              첫 면접 시작하기
            </button>
          </div>
        )}

        {!loading && interviews.slice(0, 5).map((iv) => {
          const badge = STATUS_BADGE[iv.status] || STATUS_BADGE.pending
          return (
            <div
              key={iv.id}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '12px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
              onClick={() => iv.status === 'completed'
                ? navigate(`/interview/${iv.id}/result`)
                : navigate(`/interview/${iv.id}`)}
            >
              <div>
                <p style={{ fontWeight: 500 }}>{iv.title}</p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  {CATEGORY_LABEL[iv.category]} · {new Date(iv.created_at).toLocaleDateString('ko')}
                </p>
              </div>
              <span className={`badge ${badge.cls}`}>{badge.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
