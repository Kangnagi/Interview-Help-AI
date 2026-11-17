// 카메라 설정 (설정 > 카메라) — 이 브라우저에 저장. 카메라 장치 ID는 브라우저마다 달라서 계정이 아니라 브라우저에 둔다.
// 밝기 · 대비 · 좌우 반전은 화면에 보이는 내 모습에만 적용한다 (CSS filter/transform).
// AI 분석(useVisionStream)은 video 원본 프레임을 canvas에 그리므로 이 설정과 관계없이 같은 결과가 나온다.
const KEY = 'camera_settings'

export const CAMERA_DEFAULTS = { deviceId: '', brightness: 100, contrast: 100, mirror: true }

const clamp = (v, lo, hi, d) => (Number.isFinite(+v) ? Math.min(hi, Math.max(lo, +v)) : d)

export function loadCameraSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) || '{}')
    return {
      deviceId: typeof s.deviceId === 'string' ? s.deviceId : '',
      brightness: clamp(s.brightness, 50, 150, 100),
      contrast: clamp(s.contrast, 50, 150, 100),
      mirror: s.mirror !== false,
    }
  } catch {
    return { ...CAMERA_DEFAULTS }
  }
}

export function saveCameraSettings(patch) {
  const next = { ...loadCameraSettings(), ...patch }
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* 저장 공간 문제 — 이번 화면에만 적용 */ }
  return next
}

// <video style>에 넣을 값 — 밝기 · 대비 · 좌우 반전
export function cameraVideoStyle(s = loadCameraSettings()) {
  return {
    filter: s.brightness === 100 && s.contrast === 100 ? undefined : `brightness(${s.brightness}%) contrast(${s.contrast}%)`,
    transform: s.mirror ? 'scaleX(-1)' : 'none',
  }
}
