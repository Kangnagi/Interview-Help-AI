import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { CAMERA_DEFAULTS, cameraVideoStyle, loadCameraSettings, saveCameraSettings } from '@/utils/cameraSettings'

/**
 * 설정 > 카메라 — 실제 미리보기, 쓸 카메라, 밝기 · 대비 · 좌우 반전.
 * 저장하면 면접 전 환경 설정(처음 고르는 카메라)과 면접 화면(내 모습)에 적용된다.
 * 이 탭이 닫히면(다른 탭 · 설정 창 닫기) 카메라를 끈다.
 */
export default function CameraSettingsTab() {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [form, setForm] = useState(loadCameraSettings)
  const [cameras, setCameras] = useState([])
  const [status, setStatus] = useState('loading')   // loading | ok | denied | notfound | busy | unavailable | other

  // 카메라 목록 (권한을 한 번 받아야 장치 이름이 보인다)
  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('unavailable'); return }
    let cancelled = false
    ;(async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        s.getTracks().forEach((t) => t.stop())
      } catch (err) {
        if (!cancelled) setStatus(errorKind(err))
        return
      }
      const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput')
      if (cancelled) return
      setCameras(cams)
      if (!cams.length) { setStatus('notfound'); return }
      // 저장한 카메라가 지금 없으면(다른 PC, 뽑힘) 첫 카메라로
      setForm((f) => (cams.some((c) => c.deviceId === f.deviceId) ? f : { ...f, deviceId: cams[0].deviceId }))
    })()
    return () => { cancelled = true }
  }, [])

  // 고른 카메라로 미리보기
  useEffect(() => {
    if (!form.deviceId) return
    let cancelled = false
    setStatus('loading')
    navigator.mediaDevices.getUserMedia({ video: { deviceId: { exact: form.deviceId } }, audio: false })
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return }
        streamRef.current?.getTracks().forEach((t) => t.stop())
        streamRef.current = s
        if (videoRef.current) videoRef.current.srcObject = s
        setStatus('ok')
      })
      .catch((err) => { if (!cancelled) setStatus(errorKind(err)) })
    return () => { cancelled = true }
  }, [form.deviceId])

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), [])   // 탭을 벗어나면 카메라 끄기

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const save = () => {
    saveCameraSettings(form)
    toast.success('카메라 설정을 저장했습니다. 다음 면접부터 적용됩니다')
  }
  const reset = () => setForm((f) => ({ ...CAMERA_DEFAULTS, deviceId: f.deviceId }))

  return (
    <>
      <div className="sm-section-title">📷 카메라 설정</div>

      <div className="sm-cam-preview">
        <video ref={videoRef} autoPlay muted playsInline style={{ ...cameraVideoStyle(form), display: status === 'ok' ? 'block' : 'none' }} />
        {status !== 'ok' && <div className="sm-cam-msg">{STATUS_TEXT[status]}</div>}
      </div>

      <div className="sm-group">
        <div className="sm-label"><span>사용할 카메라</span></div>
        <select className="sm-input" value={form.deviceId} onChange={(e) => set('deviceId', e.target.value)} disabled={!cameras.length}>
          {!cameras.length && <option value="">카메라 없음</option>}
          {cameras.map((c, i) => <option key={c.deviceId} value={c.deviceId}>{c.label || `카메라 ${i + 1}`}</option>)}
        </select>
      </div>

      <div className="sm-group">
        <div className="sm-label"><span>밝기</span><span style={{ color: 'var(--primary)' }}>{form.brightness}%</span></div>
        <input type="range" className="sm-slider" min={50} max={150} value={form.brightness} onChange={(e) => set('brightness', +e.target.value)} />
      </div>
      <div className="sm-group">
        <div className="sm-label"><span>대비</span><span style={{ color: 'var(--primary)' }}>{form.contrast}%</span></div>
        <input type="range" className="sm-slider" min={50} max={150} value={form.contrast} onChange={(e) => set('contrast', +e.target.value)} />
      </div>
      <div className="sm-group">
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input type="checkbox" checked={form.mirror} onChange={(e) => set('mirror', e.target.checked)} />
          거울처럼 좌우 반전해서 보기
        </label>
      </div>

      <p className="sm-cam-note">
        밝기, 대비, 좌우 반전은 화면에 보이는 내 모습에만 적용됩니다. AI 분석에는 카메라 원본 화면을 사용하므로 점수에는 영향을 주지 않습니다.
      </p>

      <div style={{ display: 'flex', gap: 8 }}>
        <button className="sm-save-btn" onClick={save}>저장</button>
        <button type="button" className="sm-reset-btn" onClick={reset}>기본값으로</button>
      </div>
    </>
  )
}

function errorKind(err) {
  if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') return 'denied'
  if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') return 'notfound'
  if (err?.name === 'NotReadableError' || err?.name === 'TrackStartError') return 'busy'
  return 'other'
}

const STATUS_TEXT = {
  loading: '카메라를 연결하는 중입니다...',
  denied: '카메라 권한이 꺼져 있습니다. 주소창 왼쪽의 자물쇠 아이콘에서 카메라를 허용해 주세요.',
  notfound: '연결된 카메라를 찾지 못했습니다.',
  busy: '다른 프로그램이 카메라를 쓰고 있습니다. 그 프로그램을 닫고 다시 열어 주세요.',
  unavailable: '이 브라우저에서는 카메라를 쓸 수 없습니다. https 주소인지 확인해 주세요.',
  other: '카메라를 열지 못했습니다. 잠시 후 다시 시도해 주세요.',
}
