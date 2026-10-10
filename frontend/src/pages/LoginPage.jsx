import { useState } from 'react'                              // 로컬 상태 관리
import { Link, useNavigate, useSearchParams } from 'react-router-dom'   // 라우팅 · 만료 안내(?expired=1&next=…)
import { useAuthStore } from '@/store/authStore'              // 로그인 상태 관리
import toast from 'react-hot-toast'                           // 토스트 알림

export default function LoginPage() {
  const [email, setEmail]       = useState('')                 // 이메일 입력값
  const [password, setPassword] = useState('')                 // 비밀번호 입력값
  const { login, loading, error } = useAuthStore()             // Zustand 스토어: login 함수, loading/error 상태
  const navigate = useNavigate()                               // 페이지 네비게이션
  const [params] = useSearchParams()
  const expired = params.get('expired') === '1'                // 로그인 만료로 넘어온 경우 (services/api.js 401 처리)
  const nextRaw = params.get('next') || ''
  const next = nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/dashboard'   // 사이트 안 경로로만 돌아감

  const handleSubmit = async (e) => {
    e.preventDefault()                                         // 폼 기본 제출 동작 방지
    const ok = await login(email, password)                   // 로그인 시도
    if (ok) {
      toast.success('로그인 성공!')                             // 성공 토스트
      navigate(next, { replace: true })                        // 만료로 왔으면 보던 화면, 아니면 대시보드
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <h1 style={styles.title}>내일의 <span style={{ color: 'var(--primary)' }}>면접</span></h1>
        <p style={styles.sub}>계정에 로그인하세요</p>
        {expired && (
          <p role="status" style={styles.notice}>로그인이 만료되었습니다. 다시 로그인하면 보던 화면으로 돌아갑니다.</p>
        )}

        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>이메일</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}         // 입력값 상태 업데이트
            placeholder="example@email.com"
            required
            style={styles.input}
          />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={styles.label}>비밀번호</label>
            <Link to="/forgot-password" style={{ fontSize: 12, color: 'var(--primary)' }}>비밀번호를 잊으셨나요?</Link>
          </div>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            style={styles.input}
          />

          {error && <p style={styles.error}>{error}</p>}      {/* 에러 메시지 표시 */}

          <button type="submit" className="btn btn-primary btn-lg w-full" disabled={loading}>
            {loading ? '로그인 중...' : '로그인'}              {/* 로딩 중이면 다른 텍스트 표시 */}
          </button>
        </form>

        <p style={styles.foot}>
          계정이 없으신가요?{' '}
          <Link to="/register" style={{ color: 'var(--primary)' }}>회원가입</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page:  { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-page)' },
  box:   { width: 400, background: '#fff', borderRadius: 'var(--radius-lg)', padding: 40, boxShadow: 'var(--shadow-lg)' },
  title: { fontSize: 26, fontWeight: 700, textAlign: 'center', marginBottom: 6 },
  sub:   { textAlign: 'center', color: 'var(--text-secondary)', marginBottom: 28, fontSize: 14 },
  form:  { display: 'flex', flexDirection: 'column', gap: 12 },
  label: { fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' },
  input: { width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)', border: '1.5px solid var(--border)', fontSize: 14 },
  error: { color: 'var(--danger)', fontSize: 13, textAlign: 'center' },
  notice: { background: 'var(--primary-light)', color: 'var(--primary-dark)', fontSize: 13, lineHeight: 1.6, padding: '10px 14px', borderRadius: 8, margin: '-12px 0 20px', textAlign: 'center' },
  foot:  { textAlign: 'center', marginTop: 20, fontSize: 14, color: 'var(--text-secondary)' },
}

