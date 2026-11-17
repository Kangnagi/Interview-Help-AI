// 마이크 설정 (설정 > 마이크) — 쓸 마이크와 녹음 음량을 이 브라우저에 저장 (장치 ID는 브라우저마다 다르다).
// 녹음 음량은 브라우저 안에서 소리를 키우거나 줄여 녹음에 넣는다 (웹에서는 PC 마이크 음량 자체를 바꿀 수 없음).
//  - 100%면 아무 처리도 하지 않는다 (예전과 똑같은 원음 녹음)
//  - 음성 인식(Web Speech API)은 브라우저가 마이크를 따로 받으므로 이 설정과 관계없다
//  - 목소리 점수 모델 · 침묵 분석은 음량을 맞춘 뒤 계산하므로 점수는 거의 그대로다 (너무 키워 소리가 깨지면 달라질 수 있음)
const KEY = 'mic_settings'
export const MIC_GAIN_MIN = 50
export const MIC_GAIN_MAX = 200

export function loadMicSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || '{}')
    const gain = Number.isFinite(+s.gain) ? Math.min(MIC_GAIN_MAX, Math.max(MIC_GAIN_MIN, Math.round(+s.gain))) : 100
    return { deviceId: typeof s.deviceId === 'string' ? s.deviceId : '', gain }
  } catch {
    return { deviceId: '', gain: 100 }
  }
}

export function saveMicSettings(patch) {
  const next = { ...loadMicSettings(), ...patch }
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* 이번 화면에만 적용 */ }
  return next
}

/**
 * 녹음할 스트림에 녹음 음량을 적용한다 → { stream, close }.
 * 음량이 100%이거나 소리 처리를 쓸 수 없으면 원래 스트림을 그대로 돌려준다 (close는 아무것도 안 함).
 * close()는 소리 처리만 끝낸다 — 원래 마이크 스트림은 부르는 쪽이 지금처럼 정리한다.
 */
export function withMicGain(stream, gainPct = loadMicSettings().gain) {
  const plain = { stream, close: () => {} }
  if (!stream || gainPct === 100) return plain
  const AC = window.AudioContext || window.webkitAudioContext
  if (!AC) return plain
  let ctx = null
  try {
    ctx = new AC()
    // 사용자 조작 전이라 소리 처리가 멈춘 상태로 만들어지면 녹음이 무음이 되므로 원음으로 녹음한다
    if (ctx.state !== 'running') { ctx.close(); return plain }
    const gain = ctx.createGain()
    gain.gain.value = gainPct / 100
    const dest = ctx.createMediaStreamDestination()
    ctx.createMediaStreamSource(stream).connect(gain).connect(dest)
    return { stream: dest.stream, close: () => { if (ctx.state !== 'closed') ctx.close() } }
  } catch {
    try { ctx?.close() } catch { /* 이미 닫힘 */ }
    return plain
  }
}
