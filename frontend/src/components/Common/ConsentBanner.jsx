import { useEffect, useState } from 'react'
import { feedbackAPI } from '@/services/feedbackAPI'

const THEMES = {
  light: { bg: 'rgba(79,110,247,.06)', border: 'rgba(79,110,247,.25)', text: 'var(--text-secondary, #374151)', muted: 'var(--text-muted, #6B7280)' },
  dark:  { bg: 'rgba(79,110,247,.08)', border: 'rgba(79,110,247,.25)', text: 'rgba(255,255,255,.8)', muted: 'rgba(255,255,255,.45)' },
}

/**
 * AI 학습 활용 동의 (선택) — 아직 선택하지 않은 사용자에게 결과 화면에서 한 번 묻는다.
 * 선택한 뒤에는 한 줄 상태 표시와 "변경" 버튼만 남는다. 동의하지 않아도 모든 기능을 그대로 쓸 수 있다.
 */
export default function ConsentBanner({ theme = 'light' }) {
  const t = THEMES[theme] || THEMES.light
  const [consent, setConsent] = useState(undefined)   // undefined = 불러오는 중, null = 아직 선택 안 함
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    feedbackAPI.getConsent()
      .then((res) => setConsent(res.data.training_consent))
      .catch(() => setConsent(undefined))              // 조회 실패 시 배너를 띄우지 않는다
  }, [])

  const choose = async (value) => {
    setSaving(true)
    try {
      const res = await feedbackAPI.setConsent(value)
      setConsent(res.data.training_consent)
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  if (consent === undefined) return null

  const btn = (primary) => ({
    padding: '6px 14px', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer',
    border: primary ? 'none' : `1px solid ${t.border}`,
    background: primary ? '#4f6ef7' : 'transparent', color: primary ? '#fff' : t.text,
  })

  if (consent !== null && !editing) {
    return (
      <div style={{ fontSize: 12, color: t.muted, marginBottom: 12 }}>
        AI 품질 개선을 위한 데이터 활용: <b>{consent ? '동의함' : '동의하지 않음'}</b>
        <button type="button" onClick={() => setEditing(true)}
                style={{ marginLeft: 8, fontSize: 12, color: '#4f6ef7', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
          변경
        </button>
      </div>
    )
  }

  return (
    <div style={{ background: t.bg, border: `1px solid ${t.border}`, borderRadius: 12, padding: '14px 16px', marginBottom: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: t.text, marginBottom: 6 }}>AI 채점 품질 개선에 참여하시겠어요? (선택)</div>
      <div style={{ fontSize: 12.5, color: t.muted, lineHeight: 1.7, marginBottom: 10 }}>
        동의하시면 면접 답변(텍스트·음성)과 아래에서 남기신 평가를 AI 채점·피드백 모델을 개선하는 학습에 활용합니다.
        외부 서비스로 보내지 않고 이 서비스의 서버 안에서만 사용하며, 언제든지 철회할 수 있고 철회하면 이후 학습에서 제외됩니다.
        동의하지 않아도 모든 기능을 그대로 이용할 수 있습니다.
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button type="button" disabled={saving} style={btn(true)} onClick={() => choose(true)}>동의합니다</button>
        <button type="button" disabled={saving} style={btn(false)} onClick={() => choose(false)}>동의하지 않습니다</button>
      </div>
    </div>
  )
}
