import { useRef, useState, useCallback, useEffect } from 'react'

const STT_SUPPORTED =
  typeof window !== 'undefined' &&
  !!(window.SpeechRecognition || window.webkitSpeechRecognition)

// 안드로이드 크롬은 continuous 모드에서 같은 문장을 여러 번 '최종 결과'로 돌려준다 → 문장마다 끊어 받고(onend에서 다시 시작) 같은 문장이 곧바로 또 오면 버린다
const IS_ANDROID = typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent)

// 음성 인식 오류 → 화면 안내용 문제 코드 (예전엔 'no-speech'를 무시하고 다시 시작만 해서, 소리가 안 들어와도 '인식 중지'만 떠 있었다)
const PROBLEM_OF = {
  'no-speech': 'no-speech',             // 말소리를 못 받음 (마이크를 다른 곳이 쓰고 있을 때도 이렇게 끝남)
  'audio-capture': 'mic',               // 마이크를 열 수 없음
  'not-allowed': 'denied',              // 마이크 권한 거부
  'service-not-allowed': 'denied',
  'network': 'network',                 // 브라우저 음성 인식 서버 연결 실패
}

export const STT_PROBLEM_TEXT = {
  'no-speech': '음성이 인식되지 않고 있어요. 마이크 가까이에서 말해 보시고, 계속 안 되면 글자로 입력해 주세요.',
  mic: '마이크를 열 수 없어요. 다른 앱이 마이크를 쓰고 있지 않은지 확인하거나 글자로 입력해 주세요.',
  denied: '마이크 권한이 꺼져 있어 음성 입력을 쓸 수 없어요. 글자로 입력해 주세요.',
  network: '음성 인식 서버에 연결하지 못했어요. 인터넷 연결을 확인하거나 글자로 입력해 주세요.',
}

export function useSpeechRecognition({ onFinal, lang = 'ko-KR' } = {}) {
  const recRef = useRef(null)
  const activeRef = useRef(false)
  const heardRef = useRef(false)          // 이번에 켠 뒤로 한 번이라도 인식됐는지
  const lastFinalRef = useRef({ text: '', at: 0 })
  const onFinalRef = useRef(onFinal)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [problem, setProblem] = useState(null)

  useEffect(() => { onFinalRef.current = onFinal }, [onFinal])

  const stop = useCallback(() => {
    activeRef.current = false
    recRef.current?.stop()
    recRef.current = null
    setListening(false)
    setInterim('')
    setProblem(null)
  }, [])

  const start = useCallback(() => {
    if (!STT_SUPPORTED || activeRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = lang
    rec.continuous = !IS_ANDROID
    rec.interimResults = true

    rec.onresult = (e) => {
      let interimText = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) {
          const now = Date.now(), last = lastFinalRef.current
          if (!(t.trim() && t.trim() === last.text && now - last.at < 3000)) onFinalRef.current?.(t)
          lastFinalRef.current = { text: t.trim(), at: now }
        } else {
          interimText += t
        }
      }
      if (e.results.length) {
        heardRef.current = true
        setProblem(null)
      }
      setInterim(interimText)
    }

    rec.onend = () => {
      setInterim('')
      if (activeRef.current) {
        try { rec.start() } catch {}
      } else {
        setListening(false)
      }
    }

    rec.onerror = (e) => {
      const p = PROBLEM_OF[e.error]
      if (e.error === 'no-speech') {
        // 잠깐 말을 쉬어도 생기므로 계속 듣되, 켠 뒤로 한 번도 인식되지 않았으면 안내를 띄운다
        if (!heardRef.current) setProblem(p)
      } else if (e.error !== 'aborted') {
        activeRef.current = false
        setListening(false)
        if (p) setProblem(p)
      }
      setInterim('')
    }

    recRef.current = rec
    activeRef.current = true
    heardRef.current = false
    setProblem(null)
    setListening(true)
    rec.start()
  }, [lang])

  const toggle = useCallback(() => {
    if (activeRef.current) stop()
    else start()
  }, [start, stop])

  return { listening, interim, problem, start, stop, toggle, isSupported: STT_SUPPORTED }
}
