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
  const [permError, setPermError] = useState(null) // null | 'denied' | 'unavailable' | 'notfound' | 'other'
  const [camError, setCamError] = useState(null)   // null | 'denied' | 'notfound' | 'busy' | 'other'
  const [micError, setMicError] = useState(null)   // null | 'denied' | 'notfound' | 'other'
  const [retryCount, setRetryCount] = useState(0)

  // 1) 권한 요청 & 장치 목록 조회
  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setPermError('unavailable')
      return
    }

    let cancelled = false
    async function init() {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        s.getTracks().forEach((t) => t.stop())
        if (!cancelled) setPermError(null)
      } catch (err) {
        if (!cancelled) {
          if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
            setPermError('denied')
          } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
            setPermError('notfound')
          } else {
            setPermError('other')
          }
        }
      }

      try {
        const devs = await navigator.mediaDevices.enumerateDevices()
        if (cancelled) return
        const cams = devs.filter((d) => d.kind === 'videoinput')
        const allMics = devs.filter((d) => d.kind === 'audioinput')
        setCameras(cams)
        setMics(allMics)
        if (cams[0]) setSelCam(cams[0].deviceId)
        if (allMics[0]) setSelMic(allMics[0].deviceId)
      } catch {}
    }
    init()

    return () => {
      cancelled = true
      cancelAnimationFrame(rafRef.current)
      camStreamRef.current?.getTracks().forEach((t) => t.stop())
      micCleanupRef.current?.()
    }
  }, [retryCount])

  // 2) 카메라 미리보기
  useEffect(() => {
    if (!selCam || !navigator.mediaDevices?.getUserMedia) return
    setCamError(null)
    setCamOk(false)
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
      .catch((err) => {
        if (cancelled) return
        setCamOk(false)
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') setCamError('denied')
        else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') setCamError('notfound')
        else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') setCamError('busy')
        else setCamError('other')
      })
    return () => { cancelled = true }
  }, [selCam, retryCount])

  // 3) 마이크 레벨 측정
  useEffect(() => {
    if (!selMic || !navigator.mediaDevices?.getUserMedia) return
    setMicError(null)
    setMicOk(false)
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
      .catch((err) => {
        if (cancelled) return
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') setMicError('denied')
        else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') setMicError('notfound')
        else setMicError('other')
      })

    return () => {
      cancelled = true
      cleanup?.()
      micCleanupRef.current = null
    }
  }, [selMic, retryCount])

  const handleRetry = () => {
    setPermError(null)
    setCamError(null)
    setMicError(null)
    setCameras([])
    setMics([])
    setSelCam('')
    setSelMic('')
    setRetryCount((c) => c + 1)
  }

  const handleReady = () => {
    cancelAnimationFrame(rafRef.current)
    micCleanupRef.current?.()
    camStreamRef.current?.getTracks().forEach((t) => t.stop())
    onReady({ cameraId: selCam, micId: selMic })
  }

  const CAM_ERR_MSG = {
    denied: '카메라 권한이 거부되었습니다. 브라우저에서 권한을 허용해 주세요.',
    notfound: '카메라를 찾을 수 없습니다. 연결 상태를 확인해 주세요.',
    busy: '카메라가 다른 앱에서 사용 중입니다. 다른 앱을 종료 후 다시 시도해 주세요.',
    other: '카메라에 연결하지 못했습니다.',
  }

  const MIC_ERR_MSG = {
    denied: '마이크 권한이 거부되었습니다.',
    notfound: '마이크를 찾을 수 없습니다.',
    other: '마이크에 연결하지 못했습니다.',
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

      {/* 헤더 */}
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

      {/* 권한/장치 오류 배너 */}
      {permError && (
        <div style={{
          background: permError === 'denied' ? '#450a0a' : '#431407',
          borderBottom: `1px solid ${permError === 'denied' ? 'rgba(239,68,68,.35)' : 'rgba(249,115,22,.35)'}`,
          padding: '10px 28px', display: 'flex', alignItems: 'flex-start', gap: 12, flexShrink: 0,
        }}>
          <span style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }}>⚠️</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: permError === 'denied' ? '#fca5a5' : '#fdba74', marginBottom: 3 }}>
              {permError === 'denied' && '카메라/마이크 권한이 거부되었습니다'}
              {permError === 'unavailable' && 'HTTPS 연결이 필요합니다'}
              {permError === 'notfound' && '카메라 또는 마이크 장치를 찾을 수 없습니다'}
              {permError === 'other' && '장치 접근 중 오류가 발생했습니다'}
            </div>
            <div style={{ fontSize: 12, color: 'rgba(255,255,255,.45)', lineHeight: 1.6 }}>
              {permError === 'denied' &&
                '브라우저 주소창의 자물쇠 또는 카메라 아이콘을 클릭하여 카메라/마이크 권한을 "허용"으로 변경한 후, 아래 새로고침 버튼을 눌러주세요.'}
              {permError === 'unavailable' &&
                '카메라/마이크는 https:// 또는 localhost 환경에서만 사용 가능합니다. 보안 연결로 접속해 주세요.'}
              {permError === 'notfound' &&
                '카메라와 마이크가 PC에 올바르게 연결되어 있는지 확인한 후 다시 시도해 주세요. 내장/외장 기기 모두 지원됩니다.'}
              {permError === 'other' &&
                '다른 프로그램이 카메라/마이크를 점유 중이거나 드라이버 문제일 수 있습니다. 다시 시도해 주세요.'}
            </div>
          </div>
          <div style={{ flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 6 }}>
            {permError === 'denied' ? (
              <button
                onClick={() => window.location.reload()}
                style={{ background: '#ef4444', color: '#fff', border: 'none', borderRadius: 7, padding: '7px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
              >
                새로고침
              </button>
            ) : permError !== 'unavailable' ? (
              <button
                onClick={handleRetry}
                style={{ background: '#f97316', color: '#fff', border: 'none', borderRadius: 7, padding: '7px 14px', fontSize: 12, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
              >
                다시 시도
              </button>
            ) : null}
          </div>
        </div>
      )}

      {/* 본문 */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>

        {/* 카메라 영역 */}
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
            border: `2px solid ${camOk ? 'rgba(16,185,129,.5)' : camError ? 'rgba(239,68,68,.4)' : 'rgba(255,255,255,.06)'}`,
            transition: 'border-color .4s', minHeight: 0,
          }}>
            <video
              ref={videoRef} autoPlay muted playsInline
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: 'scaleX(-1)' }}
            />
            {/* 연결 중 상태 */}
            {!camOk && !camError && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 10,
              }}>
                <span style={{ fontSize: 36, opacity: .25 }}>📷</span>
                <span style={{ fontSize: 13, color: 'rgba(255,255,255,.25)' }}>카메라를 연결하는 중...</span>
              </div>
            )}
            {/* 카메라 오류 상태 */}
            {camError && (
              <div style={{
                position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', gap: 12, padding: '0 20px',
              }}>
                <span style={{ fontSize: 32 }}>⚠️</span>
                <span style={{ fontSize: 12, color: 'rgba(255,130,130,.85)', textAlign: 'center', lineHeight: 1.6 }}>
                  {CAM_ERR_MSG[camError]}
                </span>
                {(camError === 'busy' || camError === 'other') && (
                  <button
                    onClick={handleRetry}
                    style={{ background: 'rgba(239,68,68,.2)', color: '#fca5a5', border: '1px solid rgba(239,68,68,.4)', borderRadius: 7, padding: '6px 14px', fontSize: 12, cursor: 'pointer' }}
                  >
                    다시 시도
                  </button>
                )}
              </div>
            )}
            {/* 정상 뱃지 */}
            {camOk && (
              <div style={{
                position: 'absolute', top: 10, right: 10,
                background: 'rgba(16,185,129,.85)', borderRadius: 99,
                padding: '4px 12px', fontSize: 11, fontWeight: 700, color: '#fff',
              }}>✅ 정상</div>
            )}
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'rgba(255,255,255,.3)', display: 'block', marginBottom: 7 }}>
              카메라 선택 {cameras.length > 0 && <span style={{ color: 'rgba(79,110,247,.7)' }}>({cameras.length}개 감지됨)</span>}
            </label>
            <select className="setup-select" value={selCam} onChange={(e) => { setCamError(null); setSelCam(e.target.value) }}>
              {cameras.length === 0 && <option value="">카메라를 찾을 수 없습니다</option>}
              {cameras.map((c, i) => (
                <option key={c.deviceId} value={c.deviceId}>{c.label || `카메라 ${i + 1}`}</option>
              ))}
            </select>
          </div>
        </div>

        {/* 마이크 영역 */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column', gap: 14,
          padding: '20px 28px 20px 16px',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,.4)', letterSpacing: '.06em', textTransform: 'uppercase' }}>
            🎤 마이크 테스트
          </div>
          <div style={{
            flex: 1, background: '#111422', borderRadius: 14,
            border: micError ? '1px solid rgba(239,68,68,.35)' : '1px solid rgba(255,255,255,.05)',
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', gap: 18, padding: 28, minHeight: 0,
          }}>
            {micError ? (
              <>
                <span style={{ fontSize: 32 }}>⚠️</span>
                <div style={{ fontSize: 13, color: 'rgba(255,130,130,.85)', textAlign: 'center', lineHeight: 1.6 }}>
                  {MIC_ERR_MSG[micError]}
                </div>
                {micError !== 'denied' && (
                  <button
                    onClick={handleRetry}
                    style={{ background: 'rgba(239,68,68,.2)', color: '#fca5a5', border: '1px solid rgba(239,68,68,.4)', borderRadius: 7, padding: '6px 14px', fontSize: 12, cursor: 'pointer' }}
                  >
                    다시 시도
                  </button>
                )}
              </>
            ) : (
              <>
                {/* 마이크 아이콘 */}
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

                {/* 이퀄라이저 바 */}
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

                {/* 레벨 바 */}
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

                {/* 상태 텍스트 */}
                <div style={{ fontSize: 13, fontWeight: 500 }}>
                  {micOk
                    ? <span style={{ color: '#10b981' }}>✅ 마이크가 정상 작동합니다</span>
                    : <span style={{ color: 'rgba(255,255,255,.3)' }}>말하거나 소리를 내보세요</span>
                  }
                </div>
              </>
            )}
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'rgba(255,255,255,.3)', display: 'block', marginBottom: 7 }}>
              마이크 선택 {mics.length > 0 && <span style={{ color: 'rgba(79,110,247,.7)' }}>({mics.length}개 감지됨)</span>}
            </label>
            <select className="setup-select" value={selMic} onChange={(e) => { setMicError(null); setSelMic(e.target.value) }}>
              {mics.length === 0 && <option value="">마이크를 찾을 수 없습니다</option>}
              {mics.map((m, i) => (
                <option key={m.deviceId} value={m.deviceId}>{m.label || `마이크 ${i + 1}`}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* 푸터 */}
      <div style={{
        padding: '14px 28px', borderTop: '1px solid rgba(255,255,255,.06)',
        background: '#111422', display: 'flex', alignItems: 'center', gap: 24, flexShrink: 0,
      }}>
        <StatusDot ok={camOk} error={!!camError} label="카메라" />
        <StatusDot ok={micOk} error={!!micError} label="마이크" />
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

function StatusDot({ ok, error, label }) {
  const color = ok ? '#10b981' : error ? '#ef4444' : '#374151'
  const textColor = ok ? 'rgba(255,255,255,.65)' : error ? 'rgba(255,180,180,.8)' : 'rgba(255,255,255,.2)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13 }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block', transition: 'background .3s' }} />
      <span style={{ color: textColor }}>{label}{error ? ' 오류' : ''}</span>
    </div>
  )
}
