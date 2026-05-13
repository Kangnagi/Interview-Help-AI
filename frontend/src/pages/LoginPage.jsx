import { useState } from 'react'                              // 로컬 상태 관리
import { Link, useNavigate } from 'react-router-dom'          // 라우팅
import { useAuthStore } from '@/store/authStore'              // 로그인 상태 관리
import toast from 'react-hot-toast'                           // 토스트 알림

export default function LoginPage() {
  const [email, setEmail]       = useState('')                 // 이메일 입력값
  const [password, setPassword] = useState('')                 // 비밀번호 입력값
  const { login, loading, error } = useAuthStore()             // Zustand 스토어: login 함수, loading/error 상태
  const navigate = useNavigate()                               // 페이지 네비게이션

  const handleSubmit = async (e) => {
    e.preventDefault()                                         // 폼 기본 제출 동작 방지
    const ok = await login(email, password)                   // 로그인 시도
    if (ok) {
      toast.success('로그인 성공!')                             // 성공 토스트
      navigate('/dashboard')                                   // 대시보드로 이동
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <h1 style={styles.title}>AI <span style={{ color: 'var(--primary)' }}>면접</span> 도우미</h1>
        <p style={styles.sub}>계정에 로그인하세요</p>

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

          <label style={styles.label}>비밀번호</label>
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
  foot:  { textAlign: 'center', marginTop: 20, fontSize: 14, color: 'var(--text-secondary)' },
}

