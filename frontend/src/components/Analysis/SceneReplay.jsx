import { useEffect, useState } from 'react'
import { analysisAPI } from '@/services/api'

// 분석 결과의 '감점 장면' — 면접 중 1초에 2장씩 분석하던 작은 사진 가운데 시선 · 자세 점수가 깎인 순간을
// 앞뒤 몇 장으로 이어 움직이는 이미지처럼 보여 준다 (서버: services/vision/scenes.py, 본인만 · 30일 보관).

const REASON_STYLE = {
  away:        { icon: '👀', color: '#f59e0b', bg: '#FFFBEB' },
  no_face:     { icon: '🚫', color: '#ef4444', bg: '#FEF2F2' },
  posture:     { icon: '🧍', color: '#8b5cf6', bg: '#F5F3FF' },
  eyes_closed: { icon: '😌', color: '#0ea5e9', bg: '#F0F9FF' },
}
const FRAME_MS = 450     // 실제로는 0.5초 간격으로 찍힌 사진 — 거의 실제 속도로

const fmtTime = (sec) => {
  if (sec == null) return ''
  const s = Math.max(0, Math.round(sec))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function Flipbook({ frames, label }) {
  const [i, setI] = useState(0)
  const [playing, setPlaying] = useState(true)
  useEffect(() => {
    if (!playing || frames.length < 2) return
    const t = setInterval(() => setI((x) => (x + 1) % frames.length), FRAME_MS)
    return () => clearInterval(t)
  }, [playing, frames.length])
  return (
    <div style={{ position: 'relative', borderRadius: 10, overflow: 'hidden', background: '#111827', aspectRatio: '4 / 3', cursor: 'pointer' }}
         onClick={() => setPlaying((p) => !p)} title={playing ? '눌러서 멈추기' : '눌러서 다시 보기'}>
      {/* 면접 화면처럼 좌우 반전 (거울 모드) */}
      <img src={frames[i]} alt={label} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: 'scaleX(-1)' }} />
      {!playing && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,.35)', color: '#fff', fontSize: 28 }}>▶</div>
      )}
      <div style={{ position: 'absolute', left: 8, right: 8, bottom: 6, display: 'flex', gap: 3 }}>
        {frames.map((_, k) => (
          <span key={k} style={{ flex: 1, height: 3, borderRadius: 99, background: k <= i ? 'rgba(255,255,255,.9)' : 'rgba(255,255,255,.3)' }} />
        ))}
      </div>
    </div>
  )
}

export default function SceneReplay({ interviewId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    analysisAPI.scenes(interviewId)
      .then(({ data }) => { if (alive) setData(data) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [interviewId])

  if (error || !data) return null
  const scenes = data.scenes || []
  // 예전 면접 · 카메라 영상이 없던 면접은 칸 자체를 숨긴다
  if (!data.mode && !data.purged && scenes.length === 0) return null

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
        <h3 style={{ fontWeight: 600, fontSize: 14 }}>🎞 감점 장면</h3>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>본인만 볼 수 있고 {data.retention_days || 30}일 뒤 자동 삭제돼요</span>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
        시선 · 자세 점수가 깎인 순간입니다. 사진을 누르면 멈추거나 다시 볼 수 있어요.
      </p>

      {data.purged && <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>보관 기간({data.retention_days || 30}일)이 지나 사진이 삭제됐어요. 점수와 분석 결과는 그대로 남아 있어요.</p>}
      {!data.purged && data.mode === 'off' && <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>이 면접은 감점 장면 저장을 끄고 진행했어요. 면접 시작 전 환경 설정 화면에서 켤 수 있어요.</p>}
      {!data.purged && data.mode !== 'off' && scenes.length === 0 && <p style={{ fontSize: 13, color: '#047857' }}>감점된 장면이 없어요. 정면을 잘 보고 바른 자세를 유지했어요 👍</p>}

      {scenes.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14 }}>
          {scenes.map((s) => {
            const st = REASON_STYLE[s.reason] || REASON_STYLE.away
            return (
              <div key={s.id} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 10, background: '#fff' }}>
                <Flipbook frames={s.frames} label={s.label} />
                <div style={{ marginTop: 10, display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px', borderRadius: 99, fontSize: 12, fontWeight: 700, color: st.color, background: st.bg }}>
                  {st.icon} {s.label}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6, lineHeight: 1.6 }}>
                  {s.question_order != null ? `Q${s.question_order} 답변 중 · ` : ''}{fmtTime(s.at_sec)}{s.duration_sec ? ` · ${s.duration_sec}초 동안` : ''}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {[s.eye_score != null && `눈맞춤 ${Math.round(s.eye_score)}점`, s.expression_score != null && `표정 ${Math.round(s.expression_score)}점`].filter(Boolean).join(' · ')}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
