// 마이크 설정 (설정 > 마이크) — 쓸 마이크만 이 브라우저에 저장 (장치 ID는 브라우저마다 다르다).
// 음량 조절 · 소음 제거는 일부러 두지 않는다: 녹음은 음성 모델이 학습한 것과 같은 원음이어야 해서
// services/websocket.js recordingAudioConstraints가 브라우저 음성 처리를 모두 끈다.
const KEY = 'mic_settings'

export function loadMicSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || '{}')
    return { deviceId: typeof s.deviceId === 'string' ? s.deviceId : '' }
  } catch {
    return { deviceId: '' }
  }
}

export function saveMicSettings(patch) {
  const next = { ...loadMicSettings(), ...patch }
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* 이번 화면에만 적용 */ }
  return next
}
