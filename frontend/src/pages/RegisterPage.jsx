import { useState } from 'react'                              // 로컬 상태 관리
import { Link, useNavigate } from 'react-router-dom'          // 라우팅
import { useAuthStore } from '@/store/authStore'              // 회원가입 상태 관리
import toast from 'react-hot-toast'                           // 토스트 알림
import { PolicyModal } from '@/pages/PolicyPage'             // 약관 '보기' 카드

// 필수 동의 3가지 — 서버(routers/auth.py register)도 셋 다 true인지 확인한다
const AGREE_ITEMS = [
  { key: 'agree_terms',   label: '이용약관에 동의합니다', doc: 'terms' },
  { key: 'agree_privacy', label: '개인정보 수집 및 이용에 동의합니다', doc: 'privacy' },
  { key: 'over_14',       label: '만 14세 이상입니다' },
]

export default function RegisterPage() {
  // 폼 상태: 모든 입력값을 하나의 객체로 관리
  const [form, setForm] = useState({ email: '', username: '', password: '', confirm: '' })
  const [agree, setAgree] = useState({ agree_terms: false, agree_privacy: false, over_14: false })
  const allAgreed = AGREE_ITEMS.every((it) => agree[it.key])
  const [viewing, setViewing] = useState(null)                 // '보기'로 연 약관 항목 (카드로 띄움)
  const { register, loading, error } = useAuthStore()         // Zustand 스토어: register 함수, loading/error 상태
  const navigate = useNavigate()                              // 페이지 네비게이션

  // 입력값 업데이트 헬퍼 함수
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    // 비밀번호 일치 여부 확인
    if (form.password !== form.confirm) return toast.error('비밀번호가 일치하지 않습니다')
    // 서버와 같은 기준 (schemas.UserCreate: 8~128자) — 예전엔 가입 때만 1글자 비밀번호도 됐다
    if (form.password.length < 8) return toast.error('비밀번호는 8자 이상이어야 합니다')
    if (!form.username.trim()) return toast.error('이름을 입력해주세요')
    if (!allAgreed) return toast.error('필수 항목에 모두 동의해주세요')
    const ok = await register(form.email, form.username, form.password, agree)  // 회원가입 시도
    if (ok) {
      toast.success('회원가입 완료! 로그인 해주세요')
      navigate('/login')                                       // 로그인 페이지로 이동
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.box}>
        <h1 style={styles.title}>회원가입</h1>
        <p style={styles.sub}>내일의 면접에 오신 것을 환영합니다</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          {/* 입력 필드 배열을 맵으로 순회 — DRY(Don't Repeat Yourself) 원칙 */}
          {[
            { key: 'email',    label: '이메일',    type: 'email',    placeholder: 'example@email.com', max: 254 },
            { key: 'username', label: '이름',      type: 'text',     placeholder: '홍길동', max: 30 },
            { key: 'password', label: '비밀번호',  type: 'password', placeholder: '8자 이상', max: 128, min: 8 },
            { key: 'confirm',  label: '비밀번호 확인', type: 'password', placeholder: '••••••••', max: 128 },
          ].map(({ key, label, type, placeholder, max, min }) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <label style={styles.label}>{label}</label>
              <input
                type={type}
                value={form[key]}
                onChange={set(key)}                           // 입력값 상태 업데이트
                placeholder={placeholder}
                maxLength={max}
                minLength={min}
                required
                style={styles.input}
              />
            </div>
          ))}

          {/* 필수 동의 — 전체 동의 + 항목별 (약관 내용은 화면 위 카드로 띄워 입력값이 그대로 남게) */}
          <div style={styles.agreeBox}>
            <label style={{ ...styles.agreeRow, fontWeight: 600, paddingBottom: 8, borderBottom: '1px solid var(--border)' }}>
              <input type="checkbox" checked={allAgreed}
                     onChange={(e) => setAgree(Object.fromEntries(AGREE_ITEMS.map((it) => [it.key, e.target.checked])))} />
              전체 동의
            </label>
            {AGREE_ITEMS.map((it) => (
              <div key={it.key} style={styles.agreeRow}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, cursor: 'pointer' }}>
                  <input type="checkbox" checked={agree[it.key]}
                         onChange={(e) => setAgree((a) => ({ ...a, [it.key]: e.target.checked }))} />
                  <span><span style={{ color: 'var(--primary)' }}>(필수)</span> {it.label}</span>
                </label>
                {it.doc && <button type="button" onClick={() => setViewing(it)} style={styles.agreeLink}>보기</button>}
              </div>
            ))}
          </div>

          {error && <p style={styles.error}>{error}</p>}      {/* 에러 메시지 표시 */}

          <button type="submit" className="btn btn-primary btn-lg w-full" style={{ marginTop: 4 }} disabled={loading || !allAgreed}>
            {loading ? '처리 중...' : '회원가입'}              {/* 로딩 중이면 다른 텍스트 표시 */}
          </button>
        </form>

        <p style={styles.foot}>
          이미 계정이 있으신가요?{' '}
          <Link to="/login" style={{ color: 'var(--primary)' }}>로그인</Link>
        </p>
      </div>
      {viewing && (
        <PolicyModal doc={viewing.doc} onClose={() => setViewing(null)}
                     onAgree={() => setAgree((a) => ({ ...a, [viewing.key]: true }))} />
      )}
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
  agreeBox:  { border: '1.5px solid var(--border)', borderRadius: 'var(--radius-md)', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 },
  agreeRow:  { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' },
  agreeLink: { fontSize: 12, color: 'var(--text-muted, #6B7280)', textDecoration: 'underline', flexShrink: 0, background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'inherit' },
}

