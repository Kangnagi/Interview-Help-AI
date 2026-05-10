import { useState, useEffect, useRef } from 'react'

export default function InterviewSetup({ resumeInfo, onReady }) {
  const videoRef = useRef(null)
  const camStreamRef = useRef(null)
  const rafRef = useRef(null)
  const micCleanupRef = useRef(null)

  const [cameras, setCameras] = useState([])
  const [mics, setMics] = useState([])
  const [selCam, setSelCam] = useState('')
  const [selMic, setSelMic] = useState('')
  const [micLevel, setMicLevel] = useState(0)
  const [bars, setBars] = useState(Array(16).fill(2))
  const [camOk, setCamOk] = useState(false)
  const [micOk, setMicOk] = useState(false)

  // 1) Request permission & enumerate devices
  useEffect(() => {
    async function init() {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        s.getTracks().forEach((t) => t.stop())
      } catch {}
      const devs = await navigator.mediaDevices.enumerateDevices()
      const cams = devs.filter((d) => d.kind === 'videoinput')
      const allMics = devs.filter((d) => d.kind === 'audioinput')
      setCameras(cams)
      setMics(allMics)
      if (cams[0]) setSelCam(cams[0].deviceId)
      if (allMics[0]) setSelMic(allMics[0].deviceId)
    }
    init()
    return () => {
      cancelAnimationFrame(rafRef.current)
      camStreamRef.current?.getTracks().forEach((t) => t.stop())
      micCleanupRef.current?.()
    }
  }, [])

  // 2) Camera preview
  useEffect(() => {
    if (!selCam) return
    let cancelled = false
    const constraints = { video: { deviceId: { exact: selCam } }, audio: false }
    navigator.mediaDevices.getUserMedia(constraints)
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return }
        camStreamRef.current?.getTracks().forEach((t) => t.stop())
        camStreamRef.current = s
        if (videoRef.current) videoRef.current.srcObject = s
        setCamOk(true)
      })
      .catch(() => setCamOk(false))
    return () => { cancelled = true }
  }, [selCam])

  // 3) Mic level meter
  useEffect(() => {
    if (!selMic) return
    let cancelled = false
    let cleanup = null

    navigator.mediaDevices.getUserMedia({ audio: { deviceId: { exact: selMic } }, video: false })
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return }
        const ctx = new (window.AudioContext || window.webkitAudioContext)()
        if (ctx.state === 'suspended') ctx.resume()
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 1024
        analyser.smoothingTimeConstant = 0.7
        ctx.createMediaStreamSource(s).connect(analyser)
        const data = new Uint8Array(analyser.frequencyBinCount)
        let fc = 0
        const tick = () => {
          fc++
          if (fc % 2 === 0) {
            analyser.getByteFrequencyData(data)
            const avg = data.slice(0, 80).reduce((a, b) => a + b, 0) / 80
            const level = Math.min(100, avg * 3)
            setMicLevel(level)
            if (avg > 8) setMicOk(true)
            const newBars = Array.from({ length: 16 }, (_, i) => {
              const idx = Math.floor((i / 16) * 60)
              return Math.max(2, (data[idx] / 255) * 100)
            })
            setBars(newBars)
          }
          rafRef.current = requestAnimationFrame(tick)
        }
        tick()
        cleanup = () => {
          cancelAnimationFrame(rafRef.current)
          ctx.close()
          s.getTracks().forEach((t) => t.stop())
        }
        micCleanupRef.current = cleanup
      })
      .catch(() => {})

    return () => {
      cancelled = true
      cleanup?.()
      micCleanupRef.current = null
    }
  }, [selMic])

  const handleReady = () => {
    cancelAnimationFrame(rafRef.current)
    micCleanupRef.current?.()
    camStreamRef.current?.getTracks().forEach((t) => t.stop())
    onReady({ cameraId: selCam, micId: selMic })
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: '#0a0d1a',
      display: 'flex', flexDirection: 'column', zIndex: 500, fontFamily: 'inherit',
    }}>
      <style>{`
        .setup-select {
          width: 100%; background: #1e2235;
          border: 1px solid rgba(255,255,255,.12); border-radius: 8px;
          padding: 9px 12px; color: #fff; font-size: 13px; outline: none;
          appearance: none; cursor: pointer;
        }
        .setup-select:focus { border-color: #4f6ef7; }
        .setup-bar { border-radius: 3px 3px 0 0; transition: height .06s ease, background .15s; }
        @keyframes mic-ring { 0%,100%{box-shadow:0 0 0 0 rgba(16,185,129,.5)} 60%{box-shadow:0 0 0 12px rgba(16,185,129,0)} }
        .mic-ring { animation: mic-ring 1.4s infinite; }
      `}</style>

      {/* Header */}
      <div style={{
        padding: '14px 28px', borderBottom: '1px solid rgba(255,255,255,.06)',
        background: '#111422', display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0,
      }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: 'rgba(79,110,247,.15)', border: '1.5px solid rgba(79,110,247,.3)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
        }}>⚙️</div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>면접 전 환경 설정</div>
          {resumeInfo && (
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,.3)', marginTop: 2 }}>
              {[resumeInfo.companyName, resumeInfo.jobTitle].filter(Boolean).join(' · ')}
            </div>
          )}
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 12, color: 'rgba(255,255,255,.2)', textAlign: 'right', lineHeight: 1.6 }}>
          카메라와 마이크를 확인하고<br />준비가 되면 시작하세요
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* Camera side */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', gap: 14,
          padding: '20px 16px 20px 28px', borderRight: '1px solid rgba(255,255,255,.04)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,.4)', letterSpacing: '.06em', textTransform: 'uppercase' }}>
            📹 카메라 미리보기
          </div>
          <div style={{
            flex: 1, position: 'relative', borderRadius: 14, overflow: 'hidden',
            background: '#0f1117',
            border: `2px solid ${camOk ? 'rgba(16,185,129,.5)' : 'rgba(255,255,255,.06)'}`,
            transition: 'border-color .4s', minHeight: 0,
          }}>
            <video
              ref={videoRef} autoPlay muted playsInline
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: 'scaleX(-1)' }}
            />
            {!camOk && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 10,
              }}>
                <span style={{ fontSize: 36, opacity: .25 }}>📷</span>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,.25)' }}>카메라를 연결하는 중...</span>
              </div>
            )}
            {camOk && (
              <div style={{
                position: 'absolute', top: 10, right: 10,
                background: 'rgba(16,185,129,.85)', borderRadius: 99,
                padding: '4px 12px', fontSize: 11, fontWeight: 700, color: '#fff',
              }}>✅ 정상</div>
            )}
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'rgba(255,255,255,.3)', display: 'block', marginBottom: 7 }}>카메라 선택</label>
            <select className="setup-select" value={selCam} onChange={(e) => setSelCam(e.target.value)}>
              {cameras.length === 0 && <option value="">카메라를 찾을 수 없습니다</option>}
              {cameras.map((c, i) => (
                <option key={c.deviceId} value={c.deviceId}>{c.label || `카메라 ${i + 1}`}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Mic side */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', gap: 14,
          padding: '20px 28px 20px 16px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,.4)', letterSpacing: '.06em', textTransform: 'uppercase' }}>
            🎤 마이크 테스트
          </div>
          <div style={{
            flex: 1, background: '#111422', borderRadius: 14,
            border: '1px solid rgba(255,255,255,.05)',
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 18, padding: 28, minHeight: 0,
          }}>
            {/* Mic icon */}
            <div
              className={micOk && micLevel > 10 ? 'mic-ring' : ''}
              style={{
                width: 68, height: 68, borderRadius: '50%',
                background: micOk ? 'rgba(16,185,129,.12)' : 'rgba(255,255,255,.04)',
                border: `2px solid ${micOk ? 'rgba(16,185,129,.5)' : 'rgba(255,255,255,.08)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 30, transition: 'all .4s',
              }}
            >🎤</div>

            {/* Equalizer bars */}
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 56 }}>
              {bars.map((h, i) => (
                <div
                  key={i}
                  className="setup-bar"
                  style={{
                    width: 10,
                    height: `${Math.max(3, h * 0.56)}px`,
                    background: h > 70
                      ? '#ef4444'
                      : h > 35
                      ? '#f59e0b'
                      : micOk ? '#10b981' : 'rgba(79,110,247,.4)',
                  }}
                />
              ))}
            </div>

            {/* Level bar */}
            <div style={{ width: '100%', maxWidth: 280 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'rgba(255,255,255,.2)', marginBottom: 6 }}>
                <span>입력 레벨</span>
                <span>{Math.round(micLevel)}%</span>
              </div>
              <div style={{ height: 7, background: 'rgba(255,255,255,.05)', borderRadius: 99, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${micLevel}%`,
                  background: micLevel > 70 ? '#ef4444' : micLevel > 30 ? '#f59e0b' : '#10b981',
                  borderRadius: 99, transition: 'width .05s',
                }} />
              </div>
            </div>

            {/* Status text */}
            <div style={{ fontSize: 13, fontWeight: 500 }}>
              {micOk
                ? <span style={{ color: '#10b981' }}>✅ 마이크가 정상 작동합니다</span>
                : <span style={{ color: 'rgba(255,255,255,.3)' }}>말하거나 소리를 내보세요</span>
              }
            </div>
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'rgba(255,255,255,.3)', display: 'block', marginBottom: 7 }}>마이크 선택</label>
            <select className="setup-select" value={selMic} onChange={(e) => setSelMic(e.target.value)}>
              {mics.length === 0 && <option value="">마이크를 찾을 수 없습니다</option>}
              {mics.map((m, i) => (
                <option key={m.deviceId} value={m.deviceId}>{m.label || `마이크 ${i + 1}`}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div style={{
        padding: '14px 28px', borderTop: '1px solid rgba(255,255,255,.06)',
        background: '#111422', display: 'flex', alignItems: 'center', gap: 24, flexShrink: 0,
      }}>
        <StatusDot ok={camOk} label="카메라" />
        <StatusDot ok={micOk} label="마이크" />
        <div style={{ flex: 1 }} />
        <button
          onClick={handleReady}
          style={{
            background: 'linear-gradient(90deg, #4f6ef7, #6d85f8)',
            color: '#fff', border: 'none', borderRadius: 10,
            padding: '13px 36px', fontSize: 15, fontWeight: 700, cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(79,110,247,.4)',
          }}
        >
          준비 완료 →
        </button>
      </div>
    </div>
  )
}

function StatusDot({ ok, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13 }}>
      <span style={{
        width: 8, height: 8, borderRadius: '50%',
        background: ok ? '#10b981' : '#374151',
        display: 'inline-block', transition: 'background .3s',
      }} />
      <span style={{ color: ok ? 'rgba(255,255,255,.65)' : 'rgba(255,255,255,.2)' }}>{label}</span>
    </div>
  )
}
