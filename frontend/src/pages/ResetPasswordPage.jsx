import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { authAPI } from '@/services/api'

export default function ResetPasswordPage() {
  const [searchParams]          = useSearchParams()
  const token                   = searchParams.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm]   = useState('')
  const [loading, setLoading]   = useState(false)
  const [done, setDone]         = useState(false)
  const navigate                = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password.length < 8) {
      toast.error('비밀번호는 최소 8자 이상이어야 합니다.')
      return
    }
    if (password !== confirm) {
      toast.error('비밀번호가 일치하지 않습니다.')
      return
    }
    setLoading(true)
    try {
      await authAPI.confirmPasswordReset({ token, new_password: password })
      setDone(true)
      toast.success('비밀번호가 변경되었습니다!')
      setTimeout(() => navigate('/login'), 2500)
    } catch (err) {
      const msg = err.response?.data?.detail || '링크가 만료되었거나 유효하지 않습니다.'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div style={styles.page}>
        <div style={styles.box}>
          <p style={{ textAlign: 'center', color: 'var(--danger)' }}>
            유효하지 않은 링크입니다.
          </p>
          <p style={styles.foot}>
            <Link to="/forgot-password" style={{ color: 'var(--primary)' }}>다시 요청하기</Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <h1 style={styles.title}>새 비밀번호 설정</h1>

        {done ? (
          <p style={{ textAlign: 'center', color: 'var(--success, #16a34a)', lineHeight: 1.6 }}>
            비밀번호가 성공적으로 변경되었습니다.<br />잠시 후 로그인 페이지로 이동합니다.
          </p>
        ) : (
          <form onSubmit={handleSubmit} style={styles.form}>
            <label style={styles.label}>새 비밀번호</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8자 이상 입력"
              required
              minLength={8}
              style={styles.input}
            />

            <label style={styles.label}>비밀번호 확인</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="비밀번호 재입력"
              required
              style={styles.input}
            />

            <button
              type="submit"
              className="btn btn-primary btn-lg w-full"
              disabled={loading}
            >
              {loading ? '변경 중...' : '비밀번호 변경'}
            </button>
          </form>
        )}

        <p style={styles.foot}>
          <Link to="/login" style={{ color: 'var(--primary)' }}>로그인으로 돌아가기</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page:  { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-page)' },
  box:   { width: 400, background: '#fff', borderRadius: 'var(--radius-lg)', padding: 40, boxShadow: 'var(--shadow-lg)' },
  title: { fontSize: 24, fontWeight: 700, textAlign: 'center', marginBottom: 24 },
  form:  { display: 'flex', flexDirection: 'column', gap: 12 },
  label: { fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' },
  input: { width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)', border: '1.5px solid var(--border)', fontSize: 14 },
  foot:  { textAlign: 'center', marginTop: 20, fontSize: 14 },
}
