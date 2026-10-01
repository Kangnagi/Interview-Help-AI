import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { adminAPI } from '@/services/adminAPI'

// 채점 기준 — 모델 학습(선생님 채점)에 쓴 구간과 같다. 누르면 그 구간의 대표 점수가 들어간다.
const RUBRIC = [
  { range: '0~10',   score: 5,  desc: '무의미 · 무관 · "모르겠습니다"만' },
  { range: '11~30',  score: 20, desc: '경험 없음을 솔직히 말함 · 한 문장 수준' },
  { range: '31~50',  score: 42, desc: '일반론 · 포부 · 용어 나열 (사례 · 방법 없음)' },
  { range: '51~65',  score: 58, desc: '사례 · 방법 언급, 구체성 · 근거 부족' },
  { range: '66~80',  score: 73, desc: '구체적 상황 · 행동 · 결과 / 설계형은 단계 · 근거' },
  { range: '81~100', score: 88, desc: '+ 수치 결과 · 트레이드오프 · 직무 연결 탁월' },
]
const TABS = [
  { key: 'pending',  label: '검토 대기' },
  { key: 'reviewed', label: '검토 완료' },
  { key: 'skipped',  label: '건너뜀' },
]
const RATING_LABEL = { too_high: '너무 높아요', ok: '적절해요', too_low: '너무 낮아요' }
const PRIORITY_LABEL = { 2: '사용자 이의', 1: '중간 점수대', 0: '' }

const scoreColor = (s) => (s >= 80 ? 'var(--secondary, #22c55e)' : s >= 60 ? 'var(--warning, #f59e0b)' : 'var(--danger, #ef4444)')
const box = { background: 'var(--bg-secondary, rgba(0,0,0,.04))', borderRadius: 8, padding: '10px 14px', fontSize: 13, lineHeight: 1.7 }
const label = { fontSize: 11, fontWeight: 700, color: 'var(--text-muted, #6B7280)', marginBottom: 4 }

function Stat({ title, value, sub }) {
  return (
    <div className="card" style={{ padding: '12px 16px', flex: '1 1 140px', minWidth: 140 }}>
      <div style={{ fontSize: 12, color: 'var(--text-muted, #6B7280)' }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 800 }}>{value ?? '-'}</div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-muted, #6B7280)' }}>{sub}</div>}
    </div>
  )
}

export default function AdminReviewPage() {
  const [allowed, setAllowed] = useState(null)        // null = 확인 중
  const [stats, setStats] = useState(null)
  const [tab, setTab] = useState('pending')
  const [queue, setQueue] = useState({ total: 0, items: [] })
  const [selectedId, setSelectedId] = useState(null)
  const [item, setItem] = useState(null)
  const [form, setForm] = useState({ human_score: '', human_feedback: '', human_tip: '', note: '' })
  const [saving, setSaving] = useState(false)

  const loadStats = useCallback(() => adminAPI.stats().then((r) => setStats(r.data)).catch(() => {}), [])
  const loadQueue = useCallback((t = tab) =>
    adminAPI.queue(t).then((r) => {
      setQueue(r.data)
      return r.data
    }), [tab])

  useEffect(() => {
    adminAPI.me().then((r) => setAllowed(r.data.is_admin)).catch(() => setAllowed(false))
  }, [])

  useEffect(() => {
    if (!allowed) return
    loadStats()
    loadQueue(tab).then((d) => setSelectedId(d.items[0]?.question_id ?? null))
  }, [allowed, tab]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selectedId) { setItem(null); return }
    adminAPI.item(selectedId).then((r) => {
      const d = r.data
      setItem(d)
      setForm({
        human_score: d.human_score ?? (d.ai_score != null ? Math.round(d.ai_score) : ''),
        human_feedback: d.human_feedback ?? d.ai_feedback ?? '',
        human_tip: d.human_tip ?? d.ai_tip ?? '',
        note: d.note ?? '',
      })
    }).catch(() => toast.error('답변을 불러오지 못했어요'))
  }, [selectedId])

  const save = async (status) => {
    if (status === 'reviewed' && (form.human_score === '' || form.human_score == null)) {
      toast.error('점수를 입력하세요')
      return
    }
    setSaving(true)
    try {
      await adminAPI.save(selectedId, {
        status,
        human_score: form.human_score === '' ? null : Number(form.human_score),
        human_feedback: form.human_feedback,
        human_tip: form.human_tip,
        note: form.note,
      })
      toast.success(status === 'reviewed' ? '저장했어요' : '건너뛰었어요')
      const idx = queue.items.findIndex((q) => q.question_id === selectedId)
      const data = await loadQueue(tab)
      loadStats()
      // 검토 대기 탭에서는 방금 처리한 답변이 빠지므로 같은 위치의 다음 답변으로 이동
      const next = tab === 'pending' ? data.items[Math.min(idx, data.items.length - 1)] : data.items[idx]
      setSelectedId(next?.question_id ?? null)
    } catch (e) {
      toast.error(e.response?.data?.detail || '저장하지 못했어요')
    } finally {
      setSaving(false)
    }
  }

  const doExport = async () => {
    try {
      const res = await adminAPI.export()
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `human_reviews_${new Date().toISOString().slice(0, 10)}.jsonl`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('내보내기에 실패했어요')
    }
  }

  if (allowed === null) return <div style={{ padding: 24 }}>확인 중…</div>
  if (!allowed) return <div className="card" style={{ padding: 24 }}>관리자만 사용할 수 있는 화면입니다.</div>

  const reviewedTotal = stats ? stats.reviewed + stats.skipped : 0
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 800 }}>관리자 검토</h2>
          <p style={{ fontSize: 13, color: 'var(--text-muted, #6B7280)' }}>
            학습 활용에 동의한 사용자의 답변만 보입니다. 사람이 정한 점수는 다음 재학습의 정답 라벨이 됩니다.
          </p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={doExport}>⬇ 학습 데이터 내보내기 (JSONL)</button>
      </div>

      {stats && (
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
          <Stat title="동의한 사용자" value={stats.consenting_users} />
          <Stat title="검토 대기" value={stats.pending} sub={`우선 검토 ${stats.pending_priority}개`} />
          <Stat title="검토 완료" value={stats.reviewed} sub={`건너뜀 ${stats.skipped}개 · 진행 ${stats.eligible_answers ? Math.round((reviewedTotal / stats.eligible_answers) * 100) : 0}%`} />
          <Stat title="사람 점수 vs AI 점수" value={stats.mean_abs_diff != null ? `${stats.mean_abs_diff}점` : '-'} sub="평균 차이 (작을수록 AI가 정확)" />
          <div className="card" style={{ padding: '12px 16px', flex: '2 1 260px' }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted, #6B7280)', marginBottom: 4 }}>모델별 사용자 평가</div>
            {stats.ratings_by_model.length === 0 && <div style={{ fontSize: 12 }}>아직 평가가 없어요</div>}
            {stats.ratings_by_model.map((m) => (
              <div key={m.model_version} style={{ fontSize: 12, lineHeight: 1.7 }}>
                <b>{m.model_version}</b> · {m.total}건 — 높음 {m.too_high} / 적절 {m.ok} / 낮음 {m.too_low} · 👍 {m.helpful} 👎 {m.not_helpful}
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {TABS.map((t) => (
          <button key={t.key} className={`btn btn-sm ${tab === t.key ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        {/* 목록 */}
        <div className="card" style={{ flex: '1 1 300px', maxWidth: 420, padding: 0, maxHeight: 720, overflowY: 'auto' }}>
          <div style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-muted, #6B7280)', borderBottom: '1px solid var(--border, #E5E7EB)' }}>
            {queue.total}개{queue.total > queue.items.length ? ` 중 ${queue.items.length}개 표시` : ''}
          </div>
          {queue.items.length === 0 && <div style={{ padding: 16, fontSize: 13 }}>검토할 답변이 없어요</div>}
          {queue.items.map((q) => (
            <div key={q.question_id} onClick={() => setSelectedId(q.question_id)}
                 style={{ padding: '10px 14px', cursor: 'pointer', borderBottom: '1px solid var(--border, #E5E7EB)',
                          background: q.question_id === selectedId ? 'rgba(79,110,247,.08)' : 'transparent' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.question_text}</span>
                <span style={{ fontSize: 13, fontWeight: 800, color: scoreColor(q.ai_score), flexShrink: 0 }}>
                  {Math.round(q.ai_score)}{q.human_score != null && ` → ${q.human_score}`}
                </span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted, #6B7280)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.answer_preview}</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 4, fontSize: 11 }}>
                {PRIORITY_LABEL[q.priority] && <span style={{ color: q.priority === 2 ? 'var(--danger, #ef4444)' : 'var(--warning, #f59e0b)' }}>● {PRIORITY_LABEL[q.priority]}</span>}
                {q.user_rating && <span>사용자: {RATING_LABEL[q.user_rating]}</span>}
                {q.user_helpful === false && <span>👎</span>}
              </div>
            </div>
          ))}
        </div>

        {/* 상세 · 검토 입력 */}
        <div className="card" style={{ flex: '2 1 420px', padding: 20 }}>
          {!item ? <div style={{ fontSize: 13 }}>왼쪽에서 답변을 선택하세요</div> : (
            <>
              <div style={label}>질문</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{item.question_text}</div>
              <div style={label}>답변</div>
              <div style={{ ...box, marginBottom: 12, whiteSpace: 'pre-wrap' }}>{item.answer_text}</div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'baseline', marginBottom: 6, flexWrap: 'wrap' }}>
                <div style={label}>AI 채점</div>
                <span style={{ fontSize: 18, fontWeight: 800, color: scoreColor(item.ai_score) }}>{Math.round(item.ai_score)}점</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted, #6B7280)' }}>{item.model_version || '모델 기록 없음'}</span>
                {item.user_rating && <span style={{ fontSize: 12 }}>· 사용자 평가: <b>{RATING_LABEL[item.user_rating]}</b></span>}
                {item.user_helpful != null && <span style={{ fontSize: 12 }}>· 피드백 {item.user_helpful ? '👍' : '👎'}</span>}
              </div>
              {item.user_comment && <div style={{ fontSize: 12, marginBottom: 8 }}>사용자 의견: {item.user_comment}</div>}

              <div style={{ ...label, marginTop: 12 }}>사람 점수 — 채점 기준을 눌러 대표 점수를 넣고 미세 조정하세요</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                {RUBRIC.map((r) => (
                  <button key={r.range} type="button" title={r.desc} className="btn btn-outline btn-sm"
                          style={{ fontSize: 12 }} onClick={() => setForm({ ...form, human_score: r.score })}>
                    {r.range} · {r.desc}
                  </button>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <input type="range" min="0" max="100" value={form.human_score === '' ? 0 : form.human_score}
                       onChange={(e) => setForm({ ...form, human_score: Number(e.target.value) })} style={{ flex: 1 }} />
                <input type="number" min="0" max="100" value={form.human_score}
                       onChange={(e) => setForm({ ...form, human_score: e.target.value === '' ? '' : Math.max(0, Math.min(100, Number(e.target.value))) })}
                       style={{ width: 70, padding: '4px 8px' }} />
                <span style={{ fontSize: 13 }}>점</span>
              </div>

              <div style={label}>피드백 (형식: 1. 잘한 점 / 2. 아쉬운 점 / 3. 모범 답변 방향 — 틀린 내용만 고치세요)</div>
              <textarea rows={5} value={form.human_feedback} onChange={(e) => setForm({ ...form, human_feedback: e.target.value })}
                        style={{ width: '100%', padding: 8, fontSize: 13, marginBottom: 10, boxSizing: 'border-box' }} />
              <div style={label}>팁 (한 문장{!item.ai_tip && ' — 예전 답변이라 AI 팁이 없어요. 입력해야 학습 데이터로 내보내져요'})</div>
              <input value={form.human_tip} onChange={(e) => setForm({ ...form, human_tip: e.target.value })}
                     style={{ width: '100%', padding: 8, fontSize: 13, marginBottom: 10, boxSizing: 'border-box' }} />
              <div style={label}>메모 (학습에는 쓰지 않음)</div>
              <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })}
                     style={{ width: '100%', padding: 8, fontSize: 13, marginBottom: 16, boxSizing: 'border-box' }} />

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button className="btn btn-primary" disabled={saving} onClick={() => save('reviewed')}>저장하고 다음</button>
                <button className="btn btn-outline" disabled={saving} onClick={() => save('skipped')}
                        title="장난 답변, 개인정보가 들어간 답변 등 학습에 쓰기 부적절한 경우">건너뛰기 (학습 제외)</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
