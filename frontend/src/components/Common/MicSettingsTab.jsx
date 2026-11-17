import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { recordingAudioConstraints } from '@/services/websocket'
import { loadMicSettings, saveMicSettings } from '@/utils/micSettings'

const TEST_SECONDS = 4

/**
 * 설정 > 마이크 — 쓸 마이크 고르기, 실시간 소리 크기, 녹음해서 들어 보기.
 * 면접 녹음과 같은 조건(브라우저 소음 제거 · 자동 음량 조절 끔)으로 받아서, 여기서 들리는 크기가 실제 녹음 크기와 같다.
 * 이 탭이 닫히면(다른 탭 · 설정 창 닫기) 마이크를 끈다.
 */
export default function MicSettingsTab() {
  const streamRef = useRef(null)
  const recorderRef = useRef(null)
  const timerRef = useRef(null)
  const [mics, setMics] = useState([])
  const [deviceId, setDeviceId] = useState(() => loadMicSettings().deviceId)
  const [status, setStatus] = useState('loading')   // loading | ok | denied | notfound | busy | unavailable | other
  const [level, setLevel] = useState(0)              // 0~100 (지금 소리 크기)
  const [verdict, setVerdict] = useState('quiet')    // quiet | low | good | loud (최근 2초 기준)
  const [recLeft, setRecLeft] = useState(0)          // 녹음 남은 초 (0이면 녹음 중 아님)
  const [playUrl, setPlayUrl] = useState('')

  // 마이크 목록 (권한을 한 번 받아야 장치 이름이 보인다)
  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('unavailable'); return }
    let cancelled = false
    ;(async () => {
      try {
        const s = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
        s.getTracks().forEach((t) => t.stop())
      } catch (err) {
        if (!cancelled) setStatus(errorKind(err))
        return
      }
      const list = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'audioinput')
      if (cancelled) return
      setMics(list)
      if (!list.length) { setStatus('notfound'); return }
      setDeviceId((id) => (list.some((m) => m.deviceId === id) ? id : list[0].deviceId))
    })()
    return () => { cancelled = true }
  }, [])

  // 고른 마이크로 소리 크기 재기
  useEffect(() => {
    if (!deviceId) return
    let cancelled = false, raf = 0, ctx = null
    setStatus('loading')
    navigator.mediaDevices.getUserMedia({ audio: recordingAudioConstraints(deviceId), video: false })
      .then((s) => {
        if (cancelled) { s.getTracks().forEach((t) => t.stop()); return }
        streamRef.current?.getTracks().forEach((t) => t.stop())
        streamRef.current = s
        setStatus('ok')
        ctx = new (window.AudioContext || window.webkitAudioContext)()
        if (ctx.state === 'suspended') ctx.resume()
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 2048
        ctx.createMediaStreamSource(s).connect(analyser)
        const buf = new Float32Array(analyser.fftSize)
        const recent = []                                  // 최근 2초의 [시각, 소리 dB, 깨짐 여부]
        let frame = 0
        const tick = () => {
          analyser.getFloatTimeDomainData(buf)
          let sum = 0, peak = 0
          for (let i = 0; i < buf.length; i++) { sum += buf[i] * buf[i]; peak = Math.max(peak, Math.abs(buf[i])) }
          const db = 20 * Math.log10(Math.sqrt(sum / buf.length) || 1e-6)   // -60(조용) ~ 0(최대)
          const now = performance.now()
          recent.push([now, db, peak >= 0.98])
          while (recent.length && now - recent[0][0] > 2000) recent.shift()
          if (++frame % 3 === 0) {
            setLevel(Math.max(0, Math.min(100, ((db + 60) / 60) * 100)))
            const loudest = Math.max(...recent.map((r) => r[1]))
            setVerdict(recent.some((r) => r[2]) ? 'loud' : loudest < -45 ? 'quiet' : loudest < -32 ? 'low' : 'good')
          }
          raf = requestAnimationFrame(tick)
        }
        tick()
      })
      .catch((err) => { if (!cancelled) setStatus(errorKind(err)) })
    return () => {
      cancelled = true
      cancelAnimationFrame(raf)
      if (ctx && ctx.state !== 'closed') ctx.close()
    }
  }, [deviceId])

  useEffect(() => () => {                                    // 탭을 벗어나면 마이크 끄기 · 녹음 정리
    clearInterval(timerRef.current)
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    streamRef.current?.getTracks().forEach((t) => t.stop())
  }, [])
  useEffect(() => () => { if (playUrl) URL.revokeObjectURL(playUrl) }, [playUrl])

  // 녹음해서 들어 보기 — 지금 마이크로 몇 초 녹음해서 바로 재생 (서버로 보내지 않음)
  const recordTest = () => {
    const s = streamRef.current
    if (!s || recLeft) return
    let rec
    try { rec = new MediaRecorder(s) } catch { toast.error('이 브라우저에서는 녹음해 볼 수 없습니다'); return }
    const chunks = []
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    rec.onstop = () => setPlayUrl(URL.createObjectURL(new Blob(chunks, { type: rec.mimeType || 'audio/webm' })))
    recorderRef.current = rec
    setPlayUrl('')
    rec.start()
    setRecLeft(TEST_SECONDS)
    let left = TEST_SECONDS
    timerRef.current = setInterval(() => {
      left -= 1
      setRecLeft(left)
      if (left <= 0) { clearInterval(timerRef.current); if (rec.state === 'recording') rec.stop() }
    }, 1000)
  }

  const save = () => {
    saveMicSettings({ deviceId })
    toast.success('마이크 설정을 저장했습니다. 다음 면접부터 적용됩니다')
  }

  const V = VERDICT[verdict]
  return (
    <>
      <div className="sm-section-title">🎙️ 마이크 설정</div>

      <div className="sm-group">
        <div className="sm-label"><span>사용할 마이크</span></div>
        <select className="sm-input" value={deviceId} onChange={(e) => setDeviceId(e.target.value)} disabled={!mics.length}>
          {!mics.length && <option value="">마이크 없음</option>}
          {mics.map((m, i) => <option key={m.deviceId} value={m.deviceId}>{m.label || `마이크 ${i + 1}`}</option>)}
        </select>
      </div>

      <div className="sm-group">
        <div className="sm-label"><span>소리 크기 확인</span>{status === 'ok' && <span style={{ color: V.color }}>{V.label}</span>}</div>
        {status === 'ok' ? (
          <>
            <div className="sm-mic-meter"><div style={{ width: `${level}%`, background: V.color }} /><span className="sm-mic-good" title="적당한 크기" /></div>
            <p className="sm-mic-hint">면접 때처럼 평소 목소리로 말해 보세요. {V.hint}</p>
          </>
        ) : (
          <p className="sm-mic-hint">{STATUS_TEXT[status]}</p>
        )}
      </div>

      <div className="sm-group">
        <div className="sm-label"><span>녹음해서 들어 보기</span></div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button type="button" className="sm-reset-btn" onClick={recordTest} disabled={status !== 'ok' || recLeft > 0}>
            {recLeft > 0 ? `🔴 녹음 중... ${recLeft}초` : `🎙️ ${TEST_SECONDS}초 녹음하기`}
          </button>
          {playUrl && <audio src={playUrl} controls autoPlay style={{ height: 36, flex: 1, minWidth: 200 }} />}
        </div>
        <p className="sm-mic-hint">녹음한 소리는 이 화면에서만 재생되고 서버로 보내지 않습니다.</p>
      </div>

      <div className="sm-cam-note" style={{ marginTop: 0 }}>
        소리가 작거나 크면 Windows의 설정 &gt; 시스템 &gt; 소리 &gt; 입력에서 마이크 볼륨을 조절해 주세요(Mac은 시스템 설정 &gt; 사운드 &gt; 입력).
        목소리 분석이 정확하도록 면접 녹음에는 브라우저의 소음 제거와 자동 음량 조절을 쓰지 않습니다.
      </div>

      <button className="sm-save-btn" onClick={save} disabled={!deviceId}>저장</button>
    </>
  )
}

function errorKind(err) {
  if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') return 'denied'
  if (err?.name === 'NotFoundError' || err?.name === 'DevicesNotFoundError') return 'notfound'
  if (err?.name === 'NotReadableError' || err?.name === 'TrackStartError') return 'busy'
  return 'other'
}

const VERDICT = {
  quiet: { label: '소리가 거의 없음', color: '#9ca3af', hint: '말해도 막대가 움직이지 않으면 다른 마이크를 골라 보세요.' },
  low:   { label: '조금 작음', color: '#f59e0b', hint: '마이크에 조금 더 가까이 가거나 마이크 볼륨을 올려 주세요.' },
  good:  { label: '적당함', color: '#10b981', hint: '이 정도 크기면 목소리 분석에 충분합니다.' },
  loud:  { label: '너무 큼', color: '#ef4444', hint: '소리가 깨질 수 있습니다. 마이크에서 조금 떨어지거나 볼륨을 낮춰 주세요.' },
}

const STATUS_TEXT = {
  loading: '마이크를 연결하는 중입니다...',
  denied: '마이크 권한이 꺼져 있습니다. 주소창 왼쪽의 자물쇠 아이콘에서 마이크를 허용해 주세요.',
  notfound: '연결된 마이크를 찾지 못했습니다.',
  busy: '다른 프로그램이 마이크를 쓰고 있습니다. 그 프로그램을 닫고 다시 열어 주세요.',
  unavailable: '이 브라우저에서는 마이크를 쓸 수 없습니다. https 주소인지 확인해 주세요.',
  other: '마이크를 열지 못했습니다. 잠시 후 다시 시도해 주세요.',
}
