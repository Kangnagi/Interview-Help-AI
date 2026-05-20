import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { useResumeStore } from '@/store/resumeStore'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import axios from 'axios'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const { resumes } = useResumeStore()
  const navigate = useNavigate()
  const [history, setHistory] = useState([])

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = localStorage.getItem('auth_token') || localStorage.getItem('token') || ''
        const headers = token ? { Authorization: `Bearer ${token}` } : {}
        const { data } = await axios.get('/api/v1/interviews', { headers })
        setHistory(data)
      } catch (e) {
        console.error('면접 이력 조회 실패', e)
      }
    }
    fetchHistory()
  }, [])

  const practiceCount = history.filter(iv => iv.title?.includes('연습')).length || 0
  const realCount = history.filter(iv => iv.title?.includes('실전')).length || 0

  // 분석이 완료되어 점수가 있는 이력만 생성일(과거->최신) 순서로 정렬
  const completedInterviews = history
    .filter(iv => iv.status?.toLowerCase() === 'completed' && iv.total_score)
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))

  const trendData = completedInterviews.map((iv, idx) => ({ name: `${idx + 1}회차`, score: iv.total_score }))

  return (
    <div>
      {/* 인사말 */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>안녕하세요, {user?.username}님 👋</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>오늘도 면접 준비 열심히 해봐요!</p>
      </div>

      {/* 통계 카드 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 28 }}>
        {[
          { label: '작성한 자기소개서', value: resumes.length,  color: 'var(--primary)', icon: '📄' },
          { label: '연습 면접 횟수',    value: practiceCount,   color: 'var(--secondary)', icon: '🎓' },
          { label: '실전 면접 횟수',    value: realCount,        color: 'var(--warning)', icon: '🎯' },
        ].map(({ label, value, color, icon }) => (
          <div key={label} className="card" style={{ textAlign: 'center' }}>
            <p style={{ fontSize: 28 }}>{icon}</p>
            <p style={{ fontSize: 32, fontWeight: 700, color, marginTop: 4 }}>{value}</p>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>{label}</p>
          </div>
        ))}
      </div>

      {/* 성장 추이 그래프 */}
      {completedInterviews.length > 0 && (
        <div className="card" style={{ marginBottom: 28 }}>
          <h3 style={{ fontWeight: 600, fontSize: 16, marginBottom: 16 }}>📈 최근 면접 점수 추이</h3>
          <div style={{ width: '100%', height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} dy={10} />
                <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: 'var(--text-secondary)' }} />
                <Tooltip
                  contentStyle={{ borderRadius: 'var(--radius-md)', border: 'none', boxShadow: 'var(--shadow-md)', fontSize: 13 }}
                  formatter={(value) => [`${value}점`, '종합 점수']}
                />
                <Line type="monotone" dataKey="score" stroke="var(--primary)" strokeWidth={3} dot={{ r: 5, fill: 'var(--primary)', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 7 }} animationDuration={1500} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 빠른 시작 */}
      <div className="card" style={{ marginBottom: 20, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h3 style={{ fontWeight: 600, fontSize: 16 }}>자기소개서 작성하기</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            자기소개서를 등록하고 AI 면접을 시작하세요
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/resume/new')}>
          ✏️ 작성하기
        </button>
      </div>

      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
        <div>
          <h3 style={{ fontWeight: 600, fontSize: 16 }}>면접 시작하기</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            등록된 자기소개서로 AI 면접을 진행하세요
          </p>
        </div>
        <button className="btn btn-outline" onClick={() => navigate('/resume')}>
          📄 자기소개서 목록
        </button>
      </div>

      {/* 면접 기록 전체보기 링크 */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
        <div>
          <h3 style={{ fontWeight: 600, fontSize: 16 }}>면접 이력 및 결과 보기</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 4 }}>
            지금까지 진행한 모든 면접의 상세 분석 결과를 다시 확인하세요
          </p>
        </div>
        <button className="btn btn-outline" onClick={() => navigate('/history')}>
          📊 전체 이력 보기
        </button>
      </div>

      {/* 최근 면접 기록 목록 */}
      {completedInterviews.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontWeight: 600, fontSize: 16 }}>최근 면접 기록</h3>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/history')}>전체 보기</button>
          </div>
          {[...completedInterviews].reverse().slice(0, 5).map((iv) => (
            <div key={iv.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <p style={{ fontWeight: 500 }}>{iv.title}</p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{new Date(iv.created_at).toLocaleString('ko-KR', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' })} · {iv.total_questions}문항</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--primary)' }}>{iv.total_score}점</span>
                <button className="btn btn-primary btn-sm" onClick={() => navigate(`/interview/${iv.id}/result`)} style={{ padding: '6px 14px', fontSize: 13, fontWeight: 600 }}>결과 보기</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 최근 자기소개서 */}
      {resumes.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontWeight: 600, fontSize: 16 }}>최근 자기소개서</h3>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/resume')}>전체 보기</button>
          </div>
          {resumes.slice(0, 3).map((r) => (
            <div
              key={r.id}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
              onClick={() => navigate('/resume')}
            >
              <div>
                <p style={{ fontWeight: 500 }}>{r.title}</p>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                  {r.companyName} · {r.jobTitle}
                </p>
              </div>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                면접 {r.interviewRecords?.length || 0}회
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
