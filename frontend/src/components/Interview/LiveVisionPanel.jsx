import { useState } from 'react'

// 화면 왼쪽 아래 '실시간 분석' — 영상 담당 upload-my-code 브랜치(2bf38eb8) 실전 면접 화면의 패널을 옮김.
// 서버(MediaPipe)가 프레임마다(1초에 2장) 돌려주는 실제 측정값을 최근 몇 장 평균으로 보여 준다 (한두 장에 숫자가 튀지 않게).
// 눈맞춤 평균은 면접 후 분석 결과의 '시선' 점수와 같은 계산이다 (core/vision_buffer.py).

const STORAGE_KEY = 'live_vision_panel_open'

const avg = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)

export function summarizeVision(recent) {
  const known = recent.filter((r) => r && r.face_detected != null)
  if (known.length === 0) return null
  const faced = known.filter((r) => r.face_detected)
  const posed = known.filter((r) => r.pose_detected)
  return {
    face: faced.length === 0 ? 'lost' : faced.length < known.length / 2 ? 'unstable' : 'detected',
    // 얼굴이 안 보인 프레임은 0점 (분석 결과와 같은 방식)
    eye: avg(known.map((r) => (r.face_detected ? (r.eye_contact_score ?? (r.eye_contact ? 100 : 0)) : 0))),
    blink: avg(faced.map((r) => r.blink_score).filter((v) => v != null)),
    expression: avg(faced.map((r) => r.expression_score).filter((v) => v != null)),
    posture: posed.length ? (posed.filter((r) => r.posture_ok).length / posed.length) * 100 : null,
  }
}

const STYLE = (
  <style>{`
        .lv-panel { position:absolute; left:20px; bottom:20px; width:210px; background:rgba(17,20,34,.88); border:1px solid rgba(255,255,255,.1);
                    border-radius:12px; padding:12px 14px; backdrop-filter:blur(8px); z-index:10; color:#fff; font-family:inherit; }
        .lv-closed { width:auto; padding:8px 12px; font-size:12px; font-weight:700; cursor:pointer; }
        @media (max-width: 1180px) { .lv-panel { bottom:auto; top:20px; } }
      `}</style>
)

const color = (v) => (v == null ? 'rgba(255,255,255,.35)' : v >= 70 ? '#10b981' : v >= 40 ? '#f59e0b' : '#ef4444')

function Row({ label, value, hint }) {
  return (
    <div style={{ marginBottom: 8 }} title={hint}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
        <span style={{ color: 'rgba(255,255,255,.5)' }}>{label}</span>
        <span style={{ color: color(value), fontWeight: 700 }}>{value == null ? '—' : `${Math.round(value)}점`}</span>
      </div>
      <div style={{ height: 4, borderRadius: 99, background: 'rgba(255,255,255,.08)', overflow: 'hidden' }}>
        <div style={{ width: `${value == null ? 0 : Math.max(2, Math.min(100, value))}%`, height: '100%', background: color(value), transition: 'width .4s, background .4s' }} />
      </div>
    </div>
  )
}

export default function LiveVisionPanel({ recent }) {
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(STORAGE_KEY) !== '0' } catch { return true }
  })
  const toggle = () => {
    setOpen((o) => {
      try { localStorage.setItem(STORAGE_KEY, o ? '0' : '1') } catch { /* 저장 못 해도 이번 화면에선 동작 */ }
      return !o
    })
  }
  const s = summarizeVision(recent)
  const faceText = !s ? '확인 중' : s.face === 'detected' ? '감지됨' : s.face === 'unstable' ? '자주 벗어남' : '얼굴 없음'
  const faceColor = !s ? '#f59e0b' : s.face === 'detected' ? '#10b981' : s.face === 'unstable' ? '#f59e0b' : '#ef4444'

  if (!open) {
    return (
      <>{STYLE}<button className="lv-panel lv-closed" onClick={toggle} title="실시간 분석 보기">📊 실시간 분석</button></>
    )
  }
  return (
    <div className="lv-panel">
      {STYLE}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ fontSize: 12, fontWeight: 700 }}>📊 실시간 분석</span>
        <button onClick={toggle} title="숨기기" style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,.45)', cursor: 'pointer', fontSize: 13, padding: 0 }}>✕</button>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 9 }}>
        <span style={{ color: 'rgba(255,255,255,.5)' }}>얼굴</span>
        <span style={{ color: faceColor, fontWeight: 700 }}>{faceText}</span>
      </div>
      <Row label="눈맞춤" value={s?.eye} hint="눈동자가 가운데(카메라 쪽)에 있을수록 높음 — 분석 결과의 시선 점수와 같은 계산" />
      <Row label="깜빡임" value={s?.blink} hint="눈을 뜨고 있는 정도 — 눈을 감고 있으면 낮음" />
      <Row label="표정" value={s?.expression} hint="기본 50점, 미소가 클수록 높음" />
      <Row label="자세" value={s?.posture} hint="어깨가 수평인 프레임 비율 — 어깨가 화면에 보여야 측정" />
      <div style={{ fontSize: 10, color: 'rgba(255,255,255,.3)', marginTop: 2 }}>최근 3초 평균 · ✕로 숨길 수 있어요</div>
    </div>
  )
}
