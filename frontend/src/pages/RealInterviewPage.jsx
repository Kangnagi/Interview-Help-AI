 import { useState, useEffect, useRef } from 'react'
 import { useNavigate, useParams } from 'react-router-dom'
 import { useResumeStore } from '@/store/resumeStore'
 import axios from 'axios'
 
 const Q_LIMIT = 120
 
 export default function RealInterviewPage() {
   const navigate = useNavigate()
   const { resumeId } = useParams()
   const resume = useResumeStore((s) => s.getResume(resumeId))
   const { addInterviewRecord } = useResumeStore()
 
   const [phase, setPhase] = useState('intro')   // intro | interview | result
   const [qIndex, setQIndex] = useState(0)
   const [questions, setQuestions] = useState([])
   const [interviewId, setInterviewId] = useState(null)
   const [isLoading, setIsLoading] = useState(false)
   const [remaining, setRemaining] = useState(Q_LIMIT)
   const [answers, setAnswers] = useState([])
   const [totalSec, setTotalSec] = useState(0)
   const [exitConfirm, setExitConfirm] = useState(false)
   const [faceStatus, setFaceStatus] = useState('waiting')
   const [micVolume, setMicVolume] = useState(0)
   const [isRecording, setIsRecording] = useState(false)
   const [isTranscribing, setIsTranscribing] = useState(false)
 
   const videoRef = useRef(null)
   const streamRef = useRef(null)
   const audioStreamRef = useRef(null)
  const audioCtxRef = useRef(null)
   const mediaRecorderRef = useRef(null)
   const audioChunksRef = useRef([])
   const timerRef = useRef(null)
   const totalRef = useRef(null)
   const detectionRef = useRef(null)
   const handleNextRef = useRef(null)
   const micRafRef = useRef(null)
 
   const currentQ = questions[qIndex]
   const currentQText = currentQ ? currentQ.question_text : ''
   const pct = Math.round(((Q_LIMIT - remaining) / Q_LIMIT) * 100)
   const r = 44, circ = 2 * Math.PI * r
   const timerColor = remaining > 60 ? '#10b981' : remaining > 30 ? '#f59e0b' : '#ef4444'
 
   // 카메라 + 마이크
   useEffect(() => {
     setFaceStatus('detecting')
     navigator.mediaDevices?.getUserMedia({ video: true, audio: true })
       .then((stream) => {
         streamRef.current = stream
         audioStreamRef.current = stream
         
         if (videoRef.current) { videoRef.current.srcObject = stream; videoRef.current.play().catch(()=>{}) }
         
         if (typeof FaceDetector !== 'undefined') {
           const detector = new FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
           detectionRef.current = setInterval(async () => {
             if (!videoRef.current || videoRef.current.readyState < 2) return
             try {
               const faces = await detector.detect(videoRef.current)
               setFaceStatus(faces.length > 0 ? 'detected' : 'lost')
             } catch { setFaceStatus('detected') }
           }, 800)
         } else {
           setTimeout(() => setFaceStatus('detected'), 1500)
         }
 
         const ctx = new (window.AudioContext || window.webkitAudioContext)()
         audioCtxRef.current = ctx
         
         const resumeAudio = () => { if (ctx.state === 'suspended') ctx.resume() }
         window.addEventListener('click', resumeAudio)
         window.addEventListener('touchstart', resumeAudio)

         resumeAudio()
         const analyser = ctx.createAnalyser()
         analyser.fftSize = 256
         analyser.smoothingTimeConstant = 0.5
         ctx.createMediaStreamSource(stream).connect(analyser)
         const data = new Uint8Array(analyser.frequencyBinCount)
         const check = () => {
           analyser.getByteFrequencyData(data)
           // 평균값(average)을 사용하여 배경 잡음에 의한 튐 현상 방지
           const avg = data.slice(0, 50).reduce((a, b) => a + b, 0) / 50
           setMicVolume(avg) 
           micRafRef.current = requestAnimationFrame(check)
         }
         check()
       })
       .catch((e) => {
         console.error("미디어 권한 에러:", e)
         setFaceStatus('lost')
       })
 
     return () => {
       streamRef.current?.getTracks().forEach((t) => t.stop())
       clearInterval(detectionRef.current)
       clearInterval(timerRef.current)
       clearInterval(totalRef.current)
       if (micRafRef.current) cancelAnimationFrame(micRafRef.current)
     }
   }, [])
 
   const startQTimer = () => {
     clearInterval(timerRef.current)
     setRemaining(Q_LIMIT)
     timerRef.current = setInterval(() => {
       setRemaining((p) => {
         if (p <= 1) { clearInterval(timerRef.current); handleNextRef.current?.(); return 0 }
         return p - 1
       })
     }, 1000)
   }
 
   const startRecording = () => {
     if (audioCtxRef.current?.state === 'suspended') {
      audioCtxRef.current.resume()
    }
     if (!audioStreamRef.current) return
     audioChunksRef.current = []

     try {
       const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus') ? 'video/webm;codecs=vp8,opus' 
                      : MediaRecorder.isTypeSupported('video/webm') ? 'video/webm' 
                      : MediaRecorder.isTypeSupported('video/mp4') ? 'video/mp4' 
                      : ''
       const options = mimeType ? { mimeType } : {}
       const recorder = new MediaRecorder(audioStreamRef.current, options)
       recorder.ondataavailable = (e) => {
         if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data)
       }
       recorder.start()
       mediaRecorderRef.current = recorder
       setIsRecording(true)
     } catch (e) {
       console.error("녹음 시작 에러:", e)
     }
   }
 
   const handleStart = async () => {
    if (audioCtxRef.current?.state === 'suspended') {
      audioCtxRef.current.resume()
    }
     setIsLoading(true)
     try {
       const token = localStorage.getItem('auth_token') || localStorage.getItem('token') || ''
       const headers = token ? { Authorization: `Bearer ${token}` } : {}
 
       const resumeDetails = resume.content || resume.text || resume.resume_text || [resume.jobDescription, resume.idealCandidate].filter(Boolean).join('\n\n') || '내용 없음';
       const resume_content = `[지원 회사] ${resume.companyName || '미정'}\n[지원 직무] ${resume.jobTitle || '미정'}\n\n[자기소개서/경험]\n${resumeDetails}`;
       
       const resInit = await axios.post('/api/v1/interviews', {
         title: `${resume.companyName || '새'} 실전 면접`,
         category: 'general',
         resume_text: resume_content || '지원자 자기소개서 내용'
       }, { headers })
       
       const ivId = resInit.data.id
       setInterviewId(ivId)
 
       const resQ = await axios.get(`/api/v1/interviews/${ivId}/questions`, { headers })
       setQuestions(resQ.data)
       
       setPhase('interview')
       totalRef.current = setInterval(() => setTotalSec((p) => p + 1), 1000)
       startRecording() // 질문 렌더링과 동시에 바로 녹음 시작
       startQTimer()
     } catch (error) {
       console.error('면접 생성 실패:', error)
       alert('면접 질문을 생성하는 데 실패했습니다. 서버 상태를 확인해주세요.')
     } finally {
       setIsLoading(false)
     }
   }
 
   const handleNext = async () => {
     clearInterval(timerRef.current)
     setIsTranscribing(true) // 처리 상태 표시
 
     let audioBlob = null
     let mimeType = 'video/webm'
     if (mediaRecorderRef.current && isRecording) {
      mimeType = mediaRecorderRef.current.mimeType || 'video/webm'
       try {
         if (mediaRecorderRef.current.state !== 'inactive') {
           audioBlob = await new Promise(resolve => {
             mediaRecorderRef.current.onstop = () => {
               resolve(new Blob(audioChunksRef.current, { type: mimeType }))
             }
             mediaRecorderRef.current.stop()
           })
         } else {
           audioBlob = new Blob(audioChunksRef.current, { type: mimeType })
         }
       } catch (err) {
         console.error('녹음 중지 에러:', err)
         audioBlob = new Blob(audioChunksRef.current, { type: mimeType })
       }
       setIsRecording(false)
     }
 
     const token = localStorage.getItem('auth_token') || localStorage.getItem('token') || ''
     const headers = token ? { Authorization: `Bearer ${token}` } : {}
     const ext = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('ogg') ? 'ogg' : 'webm'
     
     let transcribedText = '답변 없음'
     
     // 1. STT
     if (audioBlob && audioBlob.size > 0) {
       try {
         const sttFormData = new FormData()
         sttFormData.append('file', audioBlob, `record.${ext}`)
         const sttRes = await axios.post('/api/v1/interviews/transcribe', sttFormData, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } })
         transcribedText = sttRes.data.text || '답변 없음'
       } catch (e) { console.error('STT 변환 실패:', e) }
     }
 
     const newAnswers = [...answers, { q: currentQText, a: transcribedText }]
     setAnswers(newAnswers)
 
     // 2. 답변 저장
     if (interviewId && currentQ) {
       try {
         const formData = new FormData()
         formData.append('answer_text', transcribedText)
         if (audioBlob && audioBlob.size > 0) formData.append('audio_file', audioBlob, `answer.${ext}`)
         
         await axios.post(`/api/v1/interviews/${interviewId}/questions/${currentQ.id}/answer`, formData, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } })
       } catch (e) { console.error('답변 저장 실패:', e) }
     }
 
     // 3. 다음 질문 or 종료
     if (qIndex + 1 >= questions.length) {
       clearInterval(totalRef.current)
       addInterviewRecord(resumeId, { type: 'real', duration: totalSec, questions: newAnswers, backendId: interviewId })
       if (interviewId) {
         try {
           await axios.patch(`/api/v1/interviews/${interviewId}/finish`, {}, { headers })
           await axios.post(`/api/v1/analysis/${interviewId}/start`, {}, { headers })
         } catch (e) { console.error('면접 종료/분석 실패:', e) }
       }
       setPhase('result')
       setIsTranscribing(false)
     } else {
       setQIndex((p) => p + 1)
       setIsTranscribing(false)
       startRecording() // 다음 문제 녹음 시작
       startQTimer()
     }
   }
 
   useEffect(() => {
     handleNextRef.current = handleNext
   })
 
   const fmt = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
 
   const handleExit = () => {
     streamRef.current?.getTracks().forEach((t) => t.stop())
     audioStreamRef.current?.getTracks().forEach((t) => t.stop())
     navigate('/resume')
   }
 
   if (!resume) return (
     <div style={{ padding: 40, textAlign: 'center', color: '#fff', background: '#0a0d1a', minHeight: '100vh' }}>
       자기소개서를 찾을 수 없습니다.
       <button onClick={() => navigate('/resume')} style={{ marginLeft: 12, padding: '8px 16px', background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>목록으로</button>
     </div>
   )
 
   return (
     <div style={{ position: 'fixed', inset: 0, background: '#0a0d1a', display: 'flex', flexDirection: 'column', zIndex: 500, fontFamily: 'inherit' }}>
       <style>{`
         .face-badge { position:absolute; bottom:8px; left:50%; transform:translateX(-50%); display:flex; align-items:center; gap:5px; padding:4px 10px; border-radius:99px; font-size:11px; font-weight:600; white-space:nowrap; backdrop-filter:blur(6px); }
         .face-badge.detecting { background:rgba(245,158,11,.85); color:#fff; }
         .face-badge.detected  { background:rgba(16,185,129,.85); color:#fff; }
         .face-badge.lost      { background:rgba(239,68,68,.85); color:#fff; }
         @keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
         .face-dot { width:6px; height:6px; border-radius:50%; background:currentColor; animation:blink 1.2s infinite; }
         @keyframes fadeUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:none} }
         @keyframes fadeUpCenter { from{opacity:0;transform:translateX(-50%) translateY(10px)} to{opacity:1;transform:translateX(-50%) translateY(0)} }
         .fade-up-center { animation:fadeUpCenter .35s ease forwards; }
         .fade-up { animation:fadeUp .35s ease; }
         .ri-result-item { background:#1a1d2e; border-radius:10px; padding:14px; margin-bottom:10px; }
         .ri-result-q { font-size:13px; color:#4f6ef7; margin-bottom:6px; font-weight:600; }
         .ri-result-a { font-size:13px; color:rgba(255,255,255,.7); line-height:1.5; }
       `}</style>
 
       {/* 상단 바 */}
       <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', background: '#111422', borderBottom: '1px solid rgba(255,255,255,.06)', flexShrink: 0 }}>
         <div>
           <span style={{ fontSize: 15, fontWeight: 700, color: '#fff' }}>🎯 실전 면접</span>
           <span style={{ fontSize: 12, color: 'rgba(255,255,255,.35)', marginLeft: 12 }}>{resume.companyName} · {resume.jobTitle}</span>
         </div>
         {phase === 'interview' && (
           <span style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>
           Q {qIndex + 1} / {questions.length} &nbsp;·&nbsp; 총 {fmt(totalSec)}
           </span>
         )}
         <button onClick={() => setExitConfirm(true)} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '6px 16px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>나가기</button>
       </div>
 
       {/* 진행바 */}
       {phase === 'interview' && (
         <div style={{ height: 3, background: '#1a1d2e', flexShrink: 0 }}>
         <div style={{ height: '100%', background: 'linear-gradient(90deg,#4f6ef7,#10b981)', width: `${(qIndex / questions.length) * 100}%`, transition: 'width .4s' }} />
         </div>
       )}
 
       {/* ── 메인 무대 (인트로 & 면접 진행) ── */}
       {(phase === 'intro' || phase === 'interview') && (
         <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
 
           <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, #1a2040 0%, #0a0d1a 70%)', pointerEvents: 'none' }} />
 
           {/* 카메라 화면 (인트로부터 표시) */}
           <div style={{ position: 'absolute', bottom: 20, right: 20, zIndex: 10, width: 440, height: 320 }}>
             <div style={{
               width: '100%', height: '100%', borderRadius: 14, overflow: 'hidden', position: 'relative',
               border: `2px solid ${micVolume > 15 ? '#22c55e' : 'rgba(255,255,255,.12)'}`,
               boxShadow: micVolume > 15 ? `0 0 0 ${(micVolume / 255) * 12}px rgba(34,197,94,0.25), 0 0 ${16 + (micVolume / 255) * 30}px rgba(34,197,94,${0.4 + (micVolume / 255) * 0.4})` : '0 4px 20px rgba(0,0,0,.5)',
               transition: 'box-shadow 0.05s ease-out, border-color 0.15s ease-out',
               background: '#111827',
             }}>
               <video ref={videoRef} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block', transform: 'scaleX(-1)' }} autoPlay playsInline muted />
               <div style={{ position: 'absolute', top: 6, left: 8, fontSize: 11, color: 'rgba(255,255,255,.5)', background: 'rgba(0,0,0,.4)', padding: '2px 7px', borderRadius: 99 }}>📹 나</div>
               {faceStatus === 'detecting' && <div className="face-badge detecting"><span className="face-dot" />인식 중...</div>}
               {faceStatus === 'detected'  && <div className="face-badge detected"><span className="face-dot" />얼굴 인식됨</div>}
               {faceStatus === 'lost'      && <div className="face-badge lost"><span className="face-dot" />얼굴 없음</div>}
             </div>
           </div>
 
           {/* 인트로 화면 내용 */}
           {phase === 'intro' && (
             <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 20, zIndex: 20 }}>
               <div style={{ fontSize: 56 }}>🎯</div>
               <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>실전 면접 안내</div>
               <div style={{ fontSize: 14, color: 'rgba(255,255,255,.5)', lineHeight: 1.9, textAlign: 'center' }}>
                 각 질문당 <b style={{ color: '#fff' }}>{Q_LIMIT}초</b>의 답변 시간이 주어집니다.<br />
                 시간이 지나면 자동으로 다음 질문으로 넘어갑니다.<br />
                 자기소개서를 바탕으로 맞춤형 <b style={{ color: '#fff' }}>AI 면접 질문</b>이 생성됩니다.
               </div>
               <div style={{ display: 'flex', gap: 12 }}>
                 <button onClick={() => navigate('/resume')} style={{ background: 'transparent', color: 'rgba(255,255,255,.5)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '12px 24px', fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>취소</button>
                 <button onClick={handleStart} disabled={isLoading} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 36px', fontSize: 15, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', opacity: isLoading ? 0.7 : 1 }}>
                   {isLoading ? '질문 생성 중...' : '면접 시작'}
                 </button>
               </div>
             </div>
           )}
 
           {/* 면접 진행 시 화면 내용 */}
           {phase === 'interview' && (
             <>
               <div key={qIndex} className="fade-up-center" style={{ position: 'absolute', top: '8%', left: '50%', width: '60%', maxWidth: 640, textAlign: 'center', zIndex: 10 }}>
                 <div style={{ fontSize: 11, fontWeight: 700, color: '#4f6ef7', letterSpacing: '.08em', marginBottom: 8, textTransform: 'uppercase' }}>Q{qIndex + 1} 질문</div>
                 <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', lineHeight: 1.55, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, padding: '16px 24px', backdropFilter: 'blur(8px)' }}>
                 {currentQText}
                 </div>
               </div>
 
               <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -54%)', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 5 }}>
                 <div style={{ width: 130, height: 130, borderRadius: '50%', background: 'linear-gradient(135deg,#4f6ef7,#10b981)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64, boxShadow: '0 0 48px rgba(79,110,247,.35)' }}>🤖</div>
                 <div style={{ marginTop: 12, fontSize: 13, color: 'rgba(255,255,255,.4)', fontWeight: 500 }}>AI 면접관</div>
               </div>
 
               <div style={{ position: 'absolute', top: 20, right: 20, zIndex: 10 }}>
                 <div style={{ background: 'rgba(17,20,34,.85)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 14, padding: '12px 14px', backdropFilter: 'blur(8px)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                   <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)' }}>답변 시간</div>
                   <svg width={100} height={100} viewBox="0 0 100 100">
                     <circle cx={50} cy={50} r={r} fill="none" stroke="#1e2540" strokeWidth={8} />
                     <circle
                       cx={50} cy={50} r={r} fill="none"
                       stroke={timerColor} strokeWidth={8} strokeLinecap="round"
                       strokeDasharray={circ}
                       strokeDashoffset={circ * (pct / 100)}
                       transform="rotate(-90 50 50)"
                       style={{ transition: 'stroke-dashoffset .9s, stroke .3s' }}
                     />
                     <text x={50} y={54} textAnchor="middle" dominantBaseline="middle" fill={timerColor} fontSize={18} fontWeight={700} fontFamily="monospace">
                       {fmt(remaining)}
                     </text>
                   </svg>
                   <div style={{ fontSize: 11, color: 'rgba(255,255,255,.3)' }}>총 {fmt(totalSec)}</div>
                 </div>
               </div>
 
               <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 10, width: '58%', maxWidth: 620 }}>
                 <div className="fade-up" key={qIndex}>
                   {isTranscribing ? (
                     <div style={{ width: '100%', background: 'rgba(79,110,247,.1)', border: '1.5px solid rgba(79,110,247,.4)', borderRadius: 12, padding: '30px 16px', color: '#4f6ef7', fontSize: 16, fontWeight: 600, textAlign: 'center', minHeight: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                       답변을 저장하고 다음 질문을 준비 중입니다... ⏳
                     </div>
                   ) : (
                     <>
                       <div style={{ width: '100%', background: 'rgba(239,68,68,.1)', border: '1.5px solid rgba(239,68,68,.4)', borderRadius: 12, padding: '30px 16px', color: '#ef4444', fontSize: 16, fontWeight: 600, textAlign: 'center', minHeight: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                         <span className="face-dot" style={{ background: '#ef4444' }} />
                         마이크를 통해 실전 면접 답변을 녹음 중입니다...
                       </div>
                       <div style={{ display: 'flex', justifyContent: 'center', marginTop: 10 }}>
                         <button onClick={handleNext} style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: 10, padding: '11px 32px', fontSize: 14, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit' }}>
                           {qIndex + 1 >= questions.length ? '✅ 녹음 완료 및 면접 종료' : '⏹ 녹음 완료 및 다음 질문 →'}
                         </button>
                       </div>
                     </>
                   )}
                 </div>
               </div>
             </>
           )}
         </div>
       )}
 
       {/* 결과 */}
       {phase === 'result' && (
         <div style={{ flex: 1, overflow: 'auto', padding: '32px 40px' }}>
           <div style={{ maxWidth: 700, margin: '0 auto' }}>
             <div style={{ textAlign: 'center', marginBottom: 32 }}>
               <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
               <div style={{ fontSize: 22, fontWeight: 800, color: '#fff' }}>실전 면접 완료</div>
               <div style={{ fontSize: 14, color: 'rgba(255,255,255,.4)', marginTop: 8 }}>
               {questions.length}개 질문 · 총 {fmt(totalSec)}
               </div>
             </div>
             <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,.4)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '.05em' }}>답변 요약</div>
             {answers.map((item, i) => (
               <div key={i} className="ri-result-item">
                 <div className="ri-result-q">Q{i + 1}. {typeof item.q === 'string' ? item.q : JSON.stringify(item.q)}</div>
                 <div className="ri-result-a">{typeof item.a === 'string' ? item.a : JSON.stringify(item.a) || '(답변 없음)'}</div>
               </div>
             ))}
             <div style={{ display: 'flex', gap: 12, marginTop: 24, justifyContent: 'center' }}>
               <button onClick={handleExit} style={{ background: 'transparent', color: 'rgba(255,255,255,.6)', border: '1.5px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '12px 24px', fontSize: 14, cursor: 'pointer', fontFamily: 'inherit' }}>목록으로</button>
             {interviewId ? (
               <button onClick={() => navigate(`/interview/${interviewId}/result`)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 28px', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>상세 분석 결과 보기</button>
             ) : (
               <button onClick={() => navigate(`/resume/${resumeId}/history`)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 28px', fontSize: 14, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>기록 보기</button>
             )}
             </div>
           </div>
         </div>
       )}
 
       {/* 나가기 확인 */}
       {exitConfirm && (
         <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 600 }}>
           <div style={{ background: '#111422', borderRadius: 14, padding: '28px 32px', minWidth: 300, textAlign: 'center', border: '1px solid rgba(255,255,255,.1)' }}>
             <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 10 }}>면접을 종료하시겠습니까?</div>
             <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 24 }}>진행 중인 내용은 저장되지 않습니다.</div>
             <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
               <button onClick={() => setExitConfirm(false)} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 8, padding: '10px 22px', color: 'rgba(255,255,255,.6)', cursor: 'pointer', fontSize: 14 }}>계속</button>
               <button onClick={handleExit} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '10px 22px', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>종료</button>
             </div>
           </div>
         </div>
       )}
     </div>
   )
 }
