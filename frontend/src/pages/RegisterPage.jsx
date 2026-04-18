import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import toast from 'react-hot-toast'

export default function RegisterPage() {
  const [form, setForm] = useState({ email: '', username: '', password: '', confirm: '' })
  const { register, loading, error } = useAuthStore()
  const navigate = useNavigate()

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (form.password !== form.confirm) return toast.error('비밀번호가 일치하지 않습니다')
    const ok = await register(form.email, form.username, form.password)
    if (ok) {
      toast.success('회원가입 완료! 로그인 해주세요')
      navigate('/login')
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <h1 style={styles.title}>회원가입</h1>
        <p style={styles.sub}>AI 면접 도우미에 오신 것을 환영합니다</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          {[
            { key: 'email',    label: '이메일',    type: 'email',    placeholder: 'example@email.com' },
            { key: 'username', label: '이름',      type: 'text',     placeholder: '홍길동' },
            { key: 'password', label: '비밀번호',  type: 'password', placeholder: '8자 이상' },
            { key: 'confirm',  label: '비밀번호 확인', type: 'password', placeholder: '••••••••' },
          ].map(({ key, label, type, placeholder }) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={styles.label}>{label}</label>
              <input
                type={type}
                value={form[key]}
                onChange={set(key)}
                placeholder={placeholder}
                required
                style={styles.input}
              />
            </div>
          ))}

          {error && <p style={styles.error}>{error}</p>}

          <button type="submit" className="btn btn-primary btn-lg w-full" style={{ marginTop: 4 }} disabled={loading}>
            {loading ? '처리 중...' : '회원가입'}
          </button>
        </form>

        <p style={styles.foot}>
          이미 계정이 있으신가요?{' '}
          <Link to="/login" style={{ color: 'var(--primary)' }}>로그인</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page:  { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-page)' },
  box:   { width: 420, background: '#fff', borderRadius: 'var(--radius-lg)', padding: 40, boxShadow: 'var(--shadow-lg)' },
  title: { fontSize: 24, fontWeight: 700, textAlign: 'center', marginBottom: 6 },
  sub:   { textAlign: 'center', color: 'var(--text-secondary)', marginBottom: 24, fontSize: 14 },
  form:  { display: 'flex', flexDirection: 'column', gap: 14 },
  label: { fontSize: 13, fontWeight: 500 },
  input: { padding: '10px 14px', borderRadius: 'var(--radius-md)', border: '1.5px solid var(--border)', fontSize: 14 },
  error: { color: 'var(--danger)', fontSize: 13, textAlign: 'center' },
  foot:  { textAlign: 'center', marginTop: 20, fontSize: 14, color: 'var(--text-secondary)' },
}
