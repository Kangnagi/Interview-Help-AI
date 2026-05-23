import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useResumeStore } from '@/store/resumeStore'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { interviewAPI } from '@/services/api'

const CATEGORY_LABEL = {
  general: '일반', technical: '기술', behavioral: '인성', self_intro: '자기소개',
}

function scoreColor(s) {
  if (s == null) return 'var(--text-muted)'
  return s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444'
}

function scoreGrade(s) {
  if (s == null) return ''
  return s >= 80 ? '우수' : s >= 60 ? '보통' : '개선 필요'
}

function fmtDate(d) {
  return new Date(d).toLocaleString('ko-KR', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { resumes } = useResumeStore()
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [histLoading, setHistLoading] = useState(true)

  useEffect(() => {
    ;(async () => {
      try {
        const { data } = await interviewAPI.list()
        setHistory(data)
      } catch (e) {
        console.error('면접 이력 조회 실패', e)
      } finally {
        setHistLoading(false)
      }
    })()
  }, [])

  const completed  = history.filter(iv => iv.status?.toLowerCase() === 'completed')
  const scored     = completed.filter(iv => iv.total_score != null)
  const avgScore   = scored.length
    ? (scored.reduce((a, b) => a + b.total_score, 0) / scored.length).toFixed(1)
    : null
  const bestScore  = scored.length
    ? Math.max(...scored.map(iv => iv.total_score)).toFixed(0)
    : null

  const trendList = [...scored].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
  const trendData = trendList.map((iv, idx) => ({
    name: `${idx + 1}회`,
    score: Math.round(iv.total_score),
  }))

  const recentCompleted = [...scored]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5)

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>안녕하세요, {user?.username}님 👋</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>오늘도 면접 준비 열심히 해봐요!</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 28 }}>
        {[
          { label: '자기소개서',   value: resumes.length,                   color: 'var(--primary)', icon: '📄' },
          { label: '전체 면접',    value: history.length,                   color: '#6b7280',        icon: '📋' },
          { label: '완료된 면접',  value: completed.length,                 color: '#10b981',        icon: '✅' },
          { label: '평균 점수',    value: avgScore ? `${avgScore}점` : '—', color: '#f59e0b',        icon: '📊' },
        ].map(({ label, value, color, icon }) => (
          <div key={label} className="card" style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 26 }}>{icon}</p>
            <p style={{ fontSize: 28, fontWeight: 700, color, marginTop: 4, lineHeight: 1 }}>{value}</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>{label}</p>
          </div>
        ))}
      </div>

      {trendData.length > 1 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div>
              <h3 style={{ fontWeight: 600, fontSize: 16 }}>📈 면접 점수 추이</h3>
              {bestScore && (
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  최고 점수: <strong style={{ color: scoreColor(Number(bestScore)) }}>{bestScore}점</strong>
                </p>
              )}
            </div>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>
              전체 보기
            </button>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} dy={10} />
              <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
              <Tooltip
                contentStyle={{ borderRadius: 'var(--radius-md)', border: 'none', boxShadow: 'var(--shadow-md)', fontSize: 13 }}
                formatter={(v) => [`${v}점`, '종합 점수']}
              />
              <Line
                type="monotone" dataKey="score" stroke="var(--primary)" strokeWidth={3}
                dot={{ r: 5, fill: 'var(--primary)', strokeWidth: 2, stroke: '#fff' }}
                activeDot={{ r: 7 }} animationDuration={1200}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: 16 }}>🎯 최근 면접 결과</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 3 }}>
              분석이 완료된 면접 기록입니다
            </p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>
            전체 이력
          </button>
        </div>

        {histLoading ? (
          <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-secondary)', fontSize: 14 }}>
            불러오는 중...
          </div>
        ) : recentCompleted.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '36px 0' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🎓</div>
            <p style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>아직 완료된 면접이 없습니다</p>
            <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>
              자기소개서를 등록하고 첫 AI 면접을 시작해보세요
            </p>
            <button className="btn btn-primary btn-sm" style={{ marginTop: 16 }} onClick={() => navigate('/resume')}>
              면접 시작하기
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {recentCompleted.map((iv, i) => (
              <div
                key={iv.id}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '14px 0', gap: 12,
                  borderBottom: i < recentCompleted.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>{iv.title}</span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 99,
                      background: 'rgba(79,110,247,.1)', color: 'var(--primary)',
                    }}>
                      {CATEGORY_LABEL[iv.category] || '일반'}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0 }}>
                    {fmtDate(iv.created_at)}&nbsp;·&nbsp;{iv.total_questions}문항
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: scoreColor(iv.total_score), lineHeight: 1 }}>
                      {Math.round(iv.total_score)}점
                    </div>
                    <div style={{ fontSize: 11, color: scoreColor(iv.total_score), marginTop: 2, fontWeight: 600 }}>
                      {scoreGrade(iv.total_score)}
                    </div>
                  </div>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => navigate(`/analysis/${iv.id}`)}
                    style={{ padding: '7px 16px', fontSize: 13, fontWeight: 600 }}
                  >
                    분석 결과
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: 15 }}>자기소개서 작성</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
              새 자기소개서를 등록하세요
            </p>
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/resume/new')}>
            ✏️ 작성
          </button>
        </div>

        <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: 15 }}>면접 이력 관리</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
              기록 조회 및 삭제
            </p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>
            📋 이력 보기
          </button>
        </div>
      </div>

      {resumes.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontWeight: 600, fontSize: 15 }}>최근 자기소개서</h3>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/resume')}>전체 보기</button>
          </div>
          {resumes.slice(0, 3).map((r, i) => (
            <div
              key={r.id}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '11px 0', cursor: 'pointer',
                borderBottom: i < Math.min(resumes.length, 3) - 1 ? '1px solid var(--border)' : 'none',
              }}
              onClick={() => navigate('/resume')}
            >
              <div>
                <p style={{ fontWeight: 500, fontSize: 14 }}>{r.title}</p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  {r.companyName} · {r.jobTitle}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
