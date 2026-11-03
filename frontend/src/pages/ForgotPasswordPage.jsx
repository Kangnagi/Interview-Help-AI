import { useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { authAPI } from '@/services/api'

export default function ForgotPasswordPage() {
  const [email, setEmail]     = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent]       = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      await authAPI.requestPasswordReset({ email })
      setSent(true)
    } catch {
      toast.error('요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <h1 style={styles.title}>비밀번호 찾기</h1>

        {sent ? (
          <div style={{ textAlign: 'center' }}>
            <p style={styles.sub}>
              <strong>{email}</strong>으로 재설정 링크를 보냈습니다.<br />
              받은 편지함(스팸 폴더 포함)을 확인해주세요.
            </p>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 8 }}>
              링크는 <strong>30분</strong> 동안 유효합니다.
            </p>
            <button
              onClick={() => { setSent(false); setEmail('') }}
              style={styles.retryBtn}
            >
              다른 이메일로 재시도
            </button>
          </div>
        ) : (
          <>
            <p style={styles.sub}>가입 시 사용한 이메일을 입력하시면 재설정 링크를 보내드립니다.</p>
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
              <button
                type="submit"
                className="btn btn-primary btn-lg w-full"
                disabled={loading}
              >
                {loading ? '전송 중...' : '재설정 링크 보내기'}
              </button>
            </form>
          </>
        )}

        <p style={styles.foot}>
          <Link to="/login" style={{ color: 'var(--primary)' }}>로그인으로 돌아가기</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page:     { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-page)' },
  box:      { width: 400, background: '#fff', borderRadius: 'var(--radius-lg)', padding: 40, boxShadow: 'var(--shadow-lg)' },
  title:    { fontSize: 24, fontWeight: 700, textAlign: 'center', marginBottom: 8 },
  sub:      { textAlign: 'center', color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14, lineHeight: 1.6 },
  form:     { display: 'flex', flexDirection: 'column', gap: 12 },
  label:    { fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' },
  input:    { width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)', border: '1.5px solid var(--border)', fontSize: 14 },
  foot:     { textAlign: 'center', marginTop: 20, fontSize: 14 },
  retryBtn: { marginTop: 16, background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: 14, textDecoration: 'underline' },
}
