import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useResumeStore } from '@/store/resumeStore'
import TutorialModal from '@/components/Common/TutorialModal'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts'
import { interviewAPI, statsAPI } from '@/services/api'

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

const SCORE_LINES = [
  { key: 'total_score',       name: '종합',   color: '#3658ed', dash: '' },
  { key: 'content_score',     name: '내용',   color: '#10b981', dash: '5 3' },
  { key: 'speech_score',      name: '말하기', color: '#f59e0b', dash: '2 2' },
  { key: 'posture_score',     name: '자세',   color: '#8b5cf6', dash: '8 3' },
  { key: 'eye_contact_score', name: '시선',   color: '#ef4444', dash: '4 2' },
]

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { resumes } = useResumeStore()
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [histLoading, setHistLoading] = useState(true)
  const [stats, setStats] = useState(null)
  const [showTutorial, setShowTutorial] = useState(false)

  useEffect(() => {
    if (user && !localStorage.getItem(`tutorial_done_${user.id}`)) {
      setShowTutorial(true)
    }
  }, [user])

  useEffect(() => {
    ;(async () => {
      try {
        const [ivRes, stRes] = await Promise.all([
          interviewAPI.list(),
          statsAPI.dashboard(),
        ])
        setHistory(ivRes.data)
        setStats(stRes.data)
      } catch (e) {
        console.error('데이터 조회 실패', e)
      } finally {
        setHistLoading(false)
      }
    })()
  }, [])

  const completed = history.filter(iv => iv.status?.toLowerCase() === 'completed')
  const scored    = completed.filter(iv => iv.total_score != null)
  const avgScore  = stats?.averages?.total ?? (
    scored.length ? (scored.reduce((a, b) => a + b.total_score, 0) / scored.length).toFixed(1) : null
  )
  const bestScore = scored.length ? Math.max(...scored.map(iv => iv.total_score)).toFixed(0) : null

  const trendData = stats?.trend ?? []

  const radarData = stats?.averages ? [
    { subject: '내용',   score: stats.averages.content     ?? 0 },
    { subject: '말하기', score: stats.averages.speech      ?? 0 },
    { subject: '자세',   score: stats.averages.posture     ?? 0 },
    { subject: '시선',   score: stats.averages.eye_contact ?? 0 },
    { subject: '종합',   score: stats.averages.total       ?? 0 },
  ] : []

  const recentCompleted = [...scored]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5)

  return (
    <div>
      {showTutorial && (
        <TutorialModal userId={user?.id} onClose={() => setShowTutorial(false)} />
      )}

      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>안녕하세요, {user?.username}님 👋</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>오늘도 면접 준비 열심히 해봐요!</p>
      </div>

      {/* 상단 지표 카드 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, marginBottom: 28 }}>
        {[
          { label: '자기소개서',  value: resumes.length,                   color: 'var(--primary)', icon: '📄' },
          { label: '전체 면접',   value: history.length,                   color: '#6b7280',        icon: '📋' },
          { label: '완료된 면접', value: completed.length,                 color: '#10b981',        icon: '✅' },
          { label: '평균 점수',   value: avgScore ? `${avgScore}점` : '—', color: '#f59e0b',        icon: '📊' },
        ].map(({ label, value, color, icon }) => (
          <div key={label} className="card" style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 26 }}>{icon}</p>
            <p style={{ fontSize: 28, fontWeight: 700, color, marginTop: 4, lineHeight: 1 }}>{value}</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 6 }}>{label}</p>
          </div>
        ))}
      </div>

      {/* 점수 추이 + 레이더 차트 */}
      {trendData.length > 1 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 16, marginBottom: 24 }}>
          {/* 다항목 꺾은선 차트 */}
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <h3 style={{ fontWeight: 600, fontSize: 16 }}>📈 항목별 점수 추이</h3>
                {bestScore && (
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                    최고 종합 점수: <strong style={{ color: scoreColor(Number(bestScore)) }}>{bestScore}점</strong>
                  </p>
                )}
              </div>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>
                전체 보기
              </button>
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="date" axisLine={false} tickLine={false}
                  tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} dy={8} />
                <YAxis domain={[0, 100]} axisLine={false} tickLine={false}
                  tick={{ fontSize: 11, fill: 'var(--text-secondary)' }} />
                <Tooltip
                  contentStyle={{ borderRadius: 'var(--radius-md)', border: 'none', boxShadow: 'var(--shadow-md)', fontSize: 12 }}
                  formatter={(v, name) => [`${v}점`, name]}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                {SCORE_LINES.map(({ key, name, color, dash }) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    name={name}
                    stroke={color}
                    strokeWidth={key === 'total_score' ? 3 : 2}
                    strokeDasharray={dash || undefined}
                    dot={{ r: key === 'total_score' ? 5 : 3, fill: color, strokeWidth: 2, stroke: '#fff' }}
                    activeDot={{ r: 7 }}
                    animationDuration={1000}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* 레이더(방사형) 차트 */}
          <div className="card" style={{ minWidth: 240 }}>
            <h3 style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>🎯 역량 균형</h3>
            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>전체 평균</p>
            <ResponsiveContainer width={220} height={200}>
              <RadarChart data={radarData} margin={{ top: 0, right: 20, left: 20, bottom: 0 }}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} axisLine={false} />
                <Radar name="평균" dataKey="score" stroke="#4f6ef7" fill="#4f6ef7" fillOpacity={0.25} strokeWidth={2} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 세부 항목 평균 바 */}
      {stats?.averages && (
        <div className="card" style={{ marginBottom: 24 }}>
          <h3 style={{ fontWeight: 600, fontSize: 16, marginBottom: 16 }}>📊 항목별 평균 점수</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[
              { label: '내용 분석',   value: stats.averages.content,     color: '#10b981' },
              { label: '말하기 (음성)', value: stats.averages.speech,    color: '#f59e0b' },
              { label: '자세 분석',   value: stats.averages.posture,     color: '#8b5cf6' },
              { label: '시선 접촉',   value: stats.averages.eye_contact, color: '#ef4444' },
              { label: '종합',        value: stats.averages.total,       color: '#4f6ef7' },
            ].map(({ label, value, color }) => (
              <div key={label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 5 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
                  <span style={{ fontWeight: 600, color: scoreColor(value) }}>
                    {value != null ? `${value}점` : '—'}
                    {value != null && (
                      <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6, fontSize: 11 }}>
                        {scoreGrade(value)}
                      </span>
                    )}
                  </span>
                </div>
                <div style={{ background: 'var(--border)', borderRadius: 6, height: 8, overflow: 'hidden' }}>
                  <div style={{
                    width: `${value ?? 0}%`, height: '100%',
                    background: color, borderRadius: 6,
                    transition: 'width 0.8s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 최근 면접 결과 */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: 16 }}>🎯 최근 면접 결과</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 3 }}>분석이 완료된 면접 기록입니다</p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>전체 이력</button>
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

      {/* 바로가기 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: 15 }}>자기소개서 작성</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>새 자기소개서를 등록하세요</p>
          </div>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/resume/new')}>✏️ 작성</button>
        </div>
        <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: 15 }}>면접 이력 관리</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>기록 조회 및 삭제</p>
          </div>
          <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>📋 이력 보기</button>
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
