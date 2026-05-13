import { useEffect } from 'react'                            // 마운트 시 작업 실행
import { useNavigate } from 'react-router-dom'              // 페이지 네비게이션
import { useAuthStore } from '@/store/authStore'            // 사용자 정보
import { useResumeStore } from '@/store/resumeStore'        // 자기소개서 데이터

export default function DashboardPage() {
  const { user } = useAuthStore()                           // 로그인한 사용자 정보
  const { resumes } = useResumeStore()                      // 저장된 자기소개서 목록
  const navigate = useNavigate()

  // 통계 계산 — 재렌더링될 때마다 계산
  const practiceCount = resumes.reduce((acc, r) =>
    acc + (r.interviewRecords?.filter(rec => rec.type === 'practice').length || 0), 0)  // 연습 면접 총 횟수
  const realCount = resumes.reduce((acc, r) =>
    acc + (r.interviewRecords?.filter(rec => rec.type === 'real').length || 0), 0)       // 실전 면접 총 횟수
  const totalCount = practiceCount + realCount                                           // 총 면접 횟수

  return (
    <div>
      {/* 인사말 */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ fontSize: 22, fontWeight: 700 }}>안녕하세요, {user?.username}님 👋</h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>오늘도 면접 준비 열심히 해봐요!</p>
      </div>

      {/* 통계 카드 3열 */}
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

      {/* 빠른 시작 버튼 1 */}
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

      {/* 빠른 시작 버튼 2 */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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

      {/* 최근 자기소개서 목록 */}
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

