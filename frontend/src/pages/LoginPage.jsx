import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    const ok = await login(email, password)
    if (ok) {
      toast.success('로그인 성공!')
      navigate('/dashboard')
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
            onChange={(e) => setEmail(e.target.value)}
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

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" className="btn btn-primary btn-lg w-full" disabled={loading}>
            {loading ? '로그인 중...' : '로그인'}
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
