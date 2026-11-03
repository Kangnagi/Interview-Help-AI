import { useEffect, useState } from 'react'
import { feedbackAPI, loadRatings } from '@/services/feedbackAPI'

// 테마별 색상 — 결과 화면이 밝은 테마(AnalysisPage)와 어두운 테마(InterviewResultPage) 두 가지라 나눠 둔다
const THEMES = {
  light: { text: 'var(--text-muted, #6B7280)', border: 'var(--border, #E5E7EB)', active: 'var(--primary, #4f6ef7)', activeText: '#fff', bg: 'transparent' },
  dark:  { text: 'rgba(255,255,255,.45)', border: 'rgba(255,255,255,.12)', active: '#4f6ef7', activeText: '#fff', bg: 'rgba(255,255,255,.03)' },
}

const SCORE_OPTIONS = [
  { value: 'too_high', label: '너무 높아요' },
  { value: 'ok',       label: '적절해요' },
  { value: 'too_low',  label: '너무 낮아요' },
]

/**
 * 질문별 AI 채점 평가 버튼 — "점수가 적절한가요?" + "피드백이 도움이 됐나요?"
 * 누르는 즉시 저장되고, 다시 누르면 바뀐다. 이 평가는 모델이 틀리기 쉬운 답변을 골라 재학습하는 데 쓰인다.
 */
export default function AnswerRating({ interviewId, questionId, theme = 'light' }) {
  const t = THEMES[theme] || THEMES.light
  const [rating, setRating] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    loadRatings(interviewId).then((map) => { if (alive && map[questionId]) setRating(map[questionId]) })
    return () => { alive = false }
  }, [interviewId, questionId])

  const save = async (patch) => {
    const prev = rating
    setRating({ ...rating, ...patch })   // 먼저 화면에 반영하고, 실패하면 되돌린다
    setSaving(true)
    setError('')
    try {
      await feedbackAPI.rate(interviewId, questionId, patch)
    } catch {
      setRating(prev)
      setError('저장하지 못했어요. 잠시 후 다시 눌러 주세요.')
    } finally {
      setSaving(false)
    }
  }

  const chip = (selected) => ({
    padding: '4px 10px', borderRadius: 99, fontSize: 12, cursor: saving ? 'wait' : 'pointer',
    border: `1px solid ${selected ? t.active : t.border}`,
    background: selected ? t.active : t.bg, color: selected ? t.activeText : t.text,
    transition: 'all .15s',
  })

  return (
    <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, fontSize: 12, color: t.text }}>
      <span style={{ marginRight: 2 }}>AI 점수가 적절한가요?</span>
      {SCORE_OPTIONS.map((o) => (
        <button key={o.value} type="button" disabled={saving} style={chip(rating.score_rating === o.value)}
                onClick={() => save({ score_rating: o.value })}>
          {o.label}
        </button>
      ))}
      <span style={{ margin: '0 2px 0 10px' }}>피드백이 도움이 됐나요?</span>
      <button type="button" disabled={saving} style={chip(rating.feedback_helpful === true)}
              onClick={() => save({ feedback_helpful: true })} aria-label="도움이 됐어요">👍</button>
      <button type="button" disabled={saving} style={chip(rating.feedback_helpful === false)}
              onClick={() => save({ feedback_helpful: false })} aria-label="도움이 안 됐어요">👎</button>
      {error && <span style={{ color: 'var(--danger, #ef4444)', marginLeft: 6 }}>{error}</span>}
    </div>
  )
}
