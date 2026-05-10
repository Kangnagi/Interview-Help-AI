import { useRef, useState, useCallback, useEffect } from 'react'

const STT_SUPPORTED =
  typeof window !== 'undefined' &&
  !!(window.SpeechRecognition || window.webkitSpeechRecognition)

export function useSpeechRecognition({ onFinal, lang = 'ko-KR' } = {}) {
  const recRef = useRef(null)
  const activeRef = useRef(false)
  const onFinalRef = useRef(onFinal)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')

  useEffect(() => { onFinalRef.current = onFinal }, [onFinal])

  const stop = useCallback(() => {
    activeRef.current = false
    recRef.current?.stop()
    recRef.current = null
    setListening(false)
    setInterim('')
  }, [])

  const start = useCallback(() => {
    if (!STT_SUPPORTED || activeRef.current) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    rec.lang = lang
    rec.continuous = true
    rec.interimResults = true

    rec.onresult = (e) => {
      let interimText = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) {
          onFinalRef.current?.(t)
        } else {
          interimText += t
        }
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
      if (e.error !== 'no-speech') {
        activeRef.current = false
        setListening(false)
      }
      setInterim('')
    }

    recRef.current = rec
    activeRef.current = true
    setListening(true)
    rec.start()
  }, [lang])

  const toggle = useCallback(() => {
    if (activeRef.current) stop()
    else start()
  }, [start, stop])

  return { listening, interim, start, stop, toggle, isSupported: STT_SUPPORTED }
}
