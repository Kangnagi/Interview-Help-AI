 import { useState, useEffect, useRef } from 'react'
 import { useNavigate, useParams } from 'react-router-dom'
 import { useResumeStore } from '@/store/resumeStore'
 import axios from 'axios'
 
 const PHASE = { WAITING: 'waiting', QUESTION: 'question', ANSWERING: 'answering', FEEDBACK: 'feedback', DONE: 'done' }
 
 export default function PracticeInterviewPage() {
   const navigate = useNavigate()
   const { resumeId } = useParams()
   const resume = useResumeStore((s) => s.getResume(resumeId))
   const { addInterviewRecord } = useResumeStore()
 
   const [phase, setPhase] = useState(PHASE.WAITING)
   const [qIndex, setQIndex] = useState(0)
   const [questions, setQuestions] = useState([])
   const [interviewId, setInterviewId] = useState(null)
   const [isLoading, setIsLoading] = useState(false)
   const [answer, setAnswer] = useState('')
   const [log, setLog] = useState([])
   const [logOpen, setLogOpen] = useState(false)
   const [totalSec, setTotalSec] = useState(0)
   const [answerSec, setAnswerSec] = useState(0)
   const [exitConfirm, setExitConfirm] = useState(false)
   const [faceStatus, setFaceStatus] = useState('waiting')
   const [micVolume, setMicVolume] = useState(0)
   const [feedback, setFeedback] = useState('')
   const [isRecording, setIsRecording] = useState(false)
 
   const videoRef = useRef(null)
   const streamRef = useRef(null)
   const audioStreamRef = useRef(null)
  const audioCtxRef = useRef(null)
   const mediaRecorderRef = useRef(null)
   const audioChunksRef = useRef([])
   const totalTimer = useRef(null)
   const answerTimer = useRef(null)
   const detectionRef = useRef(null)
   const micAnalyserRef = useRef(null)
 
   const currentQ = questions[qIndex]
   const currentQText = currentQ ? currentQ.question_text : ''
 
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
         micAnalyserRef.current = analyser
         const data = new Uint8Array(analyser.frequencyBinCount)
         const check = () => {
           analyser.getByteFrequencyData(data)
           // 평균값(average)을 사용하여 배경 잡음에 의한 튐 현상 방지
           const avg = data.slice(0, 50).reduce((a, b) => a + b, 0) / 50
           setMicVolume(avg) 
           micAnalyserRef.requestId = requestAnimationFrame(check)
         }
         check()
       })
       .catch((e) => {
         console.error("미디어 접근 에러:", e)
         setFaceStatus('lost')
       })
 
     return () => {
       streamRef.current?.getTracks().forEach((t) => t.stop())
       clearInterval(detectionRef.current)
       clearInterval(totalTimer.current)
       clearInterval(answerTimer.current)
       if (micAnalyserRef.current?.requestId) cancelAnimationFrame(micAnalyserRef.current.requestId)
     }
   }, [])
 
   // 총 타이머
   useEffect(() => {
     if (phase === PHASE.WAITING || phase === PHASE.DONE) return
     totalTimer.current = setInterval(() => setTotalSec((p) => p + 1), 1000)
     return () => clearInterval(totalTimer.current)
   }, [phase])
 
   // 답변 타이머
   useEffect(() => {
     clearInterval(answerTimer.current)
     if (phase === PHASE.ANSWERING) {
       setAnswerSec(0)
       answerTimer.current = setInterval(() => setAnswerSec((p) => p + 1), 1000)
     }
     return () => clearInterval(answerTimer.current)
   }, [phase])
 
   const fmt = (sec) => `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
 
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
         title: `${resume.companyName || '새'} 연습 면접`,
         category: 'general',
         resume_text: resume_content || '지원자 자기소개서 내용'
       }, { headers })
       
       const ivId = resInit.data.id
       setInterviewId(ivId)
 
       const resQ = await axios.get(`/api/v1/interviews/${ivId}/questions`, { headers })
       setQuestions(resQ.data)
       setPhase(PHASE.QUESTION)
     } catch (error) {
       console.error('면접 생성 실패:', error)
       alert('면접 질문을 생성하는 데 실패했습니다. 서버 상태를 확인해주세요.')
     } finally {
       setIsLoading(false)
     }
   }
 
   const nextQuestion = async () => {
     if (qIndex + 1 >= questions.length) {
       addInterviewRecord(resumeId, { type: 'practice', duration: totalSec, questions: questions.map((q) => ({ question: q.question_text })), backendId: interviewId })
       const token = localStorage.getItem('auth_token') || localStorage.getItem('token') || ''
       const headers = token ? { Authorization: `Bearer ${token}` } : {}
       if (interviewId) {
         try {
           await axios.patch(`/api/v1/interviews/${interviewId}/finish`, {}, { headers })
           await axios.post(`/api/v1/analysis/${interviewId}/start`, {}, { headers })
         } catch (e) { console.error('면접 종료/분석 실패:', e) }
       }
       setPhase(PHASE.DONE)
     } else {
       setQIndex((p) => p + 1)
       setAnswer('')
       setPhase(PHASE.QUESTION)
     }
   }
 
   const startRecording = () => {
     if (audioCtxRef.current?.state === 'suspended') {
      audioCtxRef.current.resume()
    }
     if (!audioStreamRef.current) {
       alert('마이크 권한이 필요합니다.')
       setPhase(PHASE.QUESTION)
       return
     }
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
     } catch (err) {
       console.error("녹음 시작 에러:", err)
       alert("현재 브라우저에서 녹음을 지원하지 않습니다.")
       setPhase(PHASE.QUESTION)
     }
   }
 
   const submitAnswer = async () => {
     setIsLoading(true)
     clearInterval(answerTimer.current)
 
     // 녹음 종료 및 데이터 추출
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
 
     try {
       const token = localStorage.getItem('auth_token') || localStorage.getItem('token') || ''
       const headers = token ? { Authorization: `Bearer ${token}` } : {}
 
       const ext = mimeType.includes('mp4') ? 'mp4' : mimeType.includes('ogg') ? 'ogg' : 'webm'
       
       let transcribedText = '답변 없음'
       if (audioBlob && audioBlob.size > 0) {
         const sttFormData = new FormData()
         sttFormData.append('file', audioBlob, `record.${ext}`)
         const sttRes = await axios.post('/api/v1/interviews/transcribe', sttFormData, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } })
         transcribedText = sttRes.data.text || '답변 없음'
       }
       setAnswer(transcribedText)
 
       // 2. 답변 서버 저장 & 피드백 요청
       let fb = '답변이 성공적으로 저장되었습니다.'
       if (interviewId && currentQ) {
         const submitFormData = new FormData()
         submitFormData.append('answer_text', transcribedText)
         submitFormData.append('is_practice', 'true')
         if (audioBlob && audioBlob.size > 0) submitFormData.append('audio_file', audioBlob, `answer.${ext}`)
         
         const res = await axios.post(`/api/v1/interviews/${interviewId}/questions/${currentQ.id}/answer`, submitFormData, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } })
         if (res.data.feedback) {
           if (typeof res.data.feedback === 'object') {
             fb = res.data.feedback.feedback || res.data.feedback.message || JSON.stringify(res.data.feedback)
           } else {
             fb = res.data.feedback
           }
         }
       }
       
       setFeedback(fb)
       setLog((prev) => [...prev, { q: currentQText, a: transcribedText, feedback: fb }])
       setLogOpen(true)
       setPhase(PHASE.FEEDBACK)
     } catch (e) {
       console.error('분석 처리 실패:', e)
       alert('답변을 처리하는 중 오류가 발생했습니다.')
       setPhase(PHASE.QUESTION)
     } finally {
       setIsLoading(false)
     }
   }
 
   const handleExit = () => {
     streamRef.current?.getTracks().forEach((t) => t.stop())
     audioStreamRef.current?.getTracks().forEach((t) => t.stop())
     navigate('/resume')
   }
 
   if (!resume) return (
     <div style={{ padding: 40, textAlign: 'center', color: '#fff', background: '#0f1117', minHeight: '100vh' }}>
       자기소개서를 찾을 수 없습니다.
       <button onClick={() => navigate('/resume')} style={{ marginLeft: 12, padding: '8px 16px', background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer' }}>목록으로</button>
     </div>
   )
 
   return (
     <div style={{ position: 'fixed', inset: 0, background: '#0a0d1a', display: 'flex', zIndex: 500, fontFamily: 'inherit' }}>
       <style>{`
         /* 로그 패널 */
         .pi-log-panel { width:0; overflow:hidden; transition:width .25s; flex-shrink:0; background:#111422; }
         .pi-log-panel.open { width:270px; border-left:1px solid rgba(255,255,255,.07); }
         .pi-log-inner { width:270px; padding:16px; height:100%; overflow-y:auto; }
         .pi-log-item { background:#1e2235; border-radius:8px; padding:12px; margin-bottom:10px; font-size:12px; }
         .pi-log-q { color:#4f6ef7; font-weight:600; margin-bottom:5px; }
         .pi-log-a { color:rgba(255,255,255,.6); margin-bottom:5px; line-height:1.5; }
         .pi-log-f { color:#22c55e; line-height:1.5; }
         /* 얼굴 인식 배지 */
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
       `}</style>
 
       {/* ── 메인 영역 ───────────────────────────── */}
       <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
 
         {/* 상단 바 */}
         <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', background: '#111422', borderBottom: '1px solid rgba(255,255,255,.06)', flexShrink: 0 }}>
           <div>
             <span style={{ fontSize: 15, fontWeight: 700, color: '#fff' }}>🎓 연습 면접</span>
             <span style={{ fontSize: 12, color: 'rgba(255,255,255,.35)', marginLeft: 12 }}>{resume.companyName} · {resume.jobTitle}</span>
           </div>
           <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
             {phase !== PHASE.WAITING && phase !== PHASE.DONE && (
               <span style={{ fontSize: 13, color: 'rgba(255,255,255,.4)' }}>Q {qIndex + 1} / {questions.length}</span>
             )}
             <button onClick={() => setLogOpen((p) => !p)} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 8, padding: '6px 14px', color: 'rgba(255,255,255,.6)', fontSize: 12, cursor: 'pointer' }}>
               📋 로그 {log.length > 0 ? `(${log.length})` : ''}
             </button>
             <button onClick={() => setExitConfirm(true)} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '6px 16px', color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>나가기</button>
           </div>
         </div>
 
         {/* 진행바 */}
         <div style={{ height: 3, background: '#1a1d2e', flexShrink: 0 }}>
           <div style={{ height: '100%', background: 'linear-gradient(90deg,#4f6ef7,#10b981)', width: `${(qIndex / questions.length) * 100}%`, transition: 'width .4s' }} />
         </div>
 
         {/* ── 메인 무대 ── */}
         <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
 
           <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 40%, #1a2040 0%, #0a0d1a 70%)', pointerEvents: 'none' }} />
 
           {(phase === PHASE.QUESTION || phase === PHASE.ANSWERING || phase === PHASE.FEEDBACK) && (
             <div key={qIndex} className="fade-up-center" style={{ position: 'absolute', top: '8%', left: '50%', width: '60%', maxWidth: 640, textAlign: 'center', zIndex: 10 }}>
               <div style={{ fontSize: 11, fontWeight: 700, color: '#4f6ef7', letterSpacing: '.08em', marginBottom: 8, textTransform: 'uppercase' }}>Q{qIndex + 1} 질문</div>
               <div style={{ fontSize: 20, fontWeight: 700, color: '#fff', lineHeight: 1.55, background: 'rgba(255,255,255,.04)', border: '1px solid rgba(255,255,255,.08)', borderRadius: 14, padding: '16px 24px', backdropFilter: 'blur(8px)' }}>
                 {currentQText}
               </div>
             </div>
           )}
 
           <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -54%)', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 5 }}>
             <div style={{ width: 130, height: 130, borderRadius: '50%', background: 'linear-gradient(135deg,#4f6ef7,#10b981)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 64, boxShadow: '0 0 48px rgba(79,110,247,.35)' }}>🤖</div>
             <div style={{ marginTop: 12, fontSize: 13, color: 'rgba(255,255,255,.4)', fontWeight: 500 }}>AI 면접관</div>
           </div>
 
           <div style={{ position: 'absolute', top: 20, right: 20, zIndex: 10 }}>
             <div style={{ background: 'rgba(17,20,34,.85)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 12, padding: '10px 16px', backdropFilter: 'blur(8px)', textAlign: 'center' }}>
               <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)', marginBottom: 2 }}>면접 시간</div>
               <div style={{ fontSize: 22, fontWeight: 700, color: '#fff', fontFamily: 'monospace' }}>{fmt(totalSec)}</div>
               {phase === PHASE.ANSWERING && (
                 <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid rgba(255,255,255,.08)' }}>
                   <div style={{ fontSize: 11, color: 'rgba(255,255,255,.35)', marginBottom: 2 }}>답변 시간</div>
                   <div style={{ fontSize: 18, fontWeight: 700, color: answerSec > 120 ? '#ef4444' : '#10b981', fontFamily: 'monospace' }}>{fmt(answerSec)}</div>
                 </div>
               )}
             </div>
           </div>
 
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
 
           {/* ── 하단 액션 패널 ── */}
           <div style={{ position: 'absolute', bottom: 20, left: '50%', transform: 'translateX(-50%)', zIndex: 10, width: '58%', maxWidth: 620 }}>
 
             {phase === PHASE.WAITING && (
               <div className="fade-up" style={{ textAlign: 'center' }}>
                 <div style={{ fontSize: 15, color: 'rgba(255,255,255,.5)', marginBottom: 16 }}>AI가 자기소개서를 바탕으로 맞춤형 질문을 준비합니다.</div>
                 <button onClick={handleStart} disabled={isLoading} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '13px 40px', fontSize: 15, fontWeight: 700, cursor: 'pointer', opacity: isLoading ? 0.7 : 1 }}>
                   {isLoading ? '질문 생성 중...' : '면접 시작 →'}
                 </button>
               </div>
             )}
 
             {phase === PHASE.QUESTION && (
               <div className="fade-up" style={{ textAlign: 'center' }}>
                 <button onClick={() => { setPhase(PHASE.ANSWERING); startRecording(); }} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '13px 40px', fontSize: 15, fontWeight: 700, cursor: 'pointer' }}>
                   🎤 답변 시작
                 </button>
               </div>
             )}
 
             {phase === PHASE.ANSWERING && (
               <div className="fade-up">
                 {isLoading ? (
                   <div style={{ width: '100%', background: 'rgba(79,110,247,.1)', border: '1.5px solid rgba(79,110,247,.4)', borderRadius: 12, padding: '30px 16px', color: '#4f6ef7', fontSize: 16, fontWeight: 600, textAlign: 'center', minHeight: 90, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                     음성을 변환하고 AI 피드백을 생성 중입니다... ⏳
                   </div>
                 ) : (
                   <>
                     <div style={{ width: '100%', background: 'rgba(239,68,68,.1)', border: '1.5px solid rgba(239,68,68,.4)', borderRadius: 12, padding: '30px 16px', color: '#ef4444', fontSize: 16, fontWeight: 600, textAlign: 'center', minHeight: 90, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                       <span className="face-dot" style={{ background: '#ef4444' }} />
                       마이크를 통해 답변을 녹음 중입니다...
                     </div>
                     <div style={{ display: 'flex', gap: 10, marginTop: 10, justifyContent: 'center' }}>
                       <button onClick={() => { if(isRecording){ mediaRecorderRef.current?.stop(); setIsRecording(false) } setPhase(PHASE.QUESTION); setAnswer(''); }} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '10px 24px', color: 'rgba(255,255,255,.6)', fontSize: 14, cursor: 'pointer' }}>
                         취소
                       </button>
                       <button onClick={submitAnswer} style={{ background: '#ef4444', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 28px', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                         ⏹ 녹음 완료
                       </button>
                     </div>
                   </>
                 )}
               </div>
             )}
 
             {phase === PHASE.FEEDBACK && (
               <div className="fade-up" style={{ textAlign: 'center' }}>
                 <div style={{ background: 'rgba(16,185,129,.12)', border: '1.5px solid rgba(34,197,94,.4)', borderRadius: 12, padding: '16px 20px', marginBottom: 16 }}>
                   <div style={{ fontSize: 16, fontWeight: 700, color: '#22c55e', marginBottom: 8 }}>✅ 답변이 기록되었습니다</div>
                   <div style={{ fontSize: 14, color: 'rgba(255,255,255,.85)', lineHeight: 1.6 }}>우측 <b>로그 패널</b>에서 방금 한 답변의 텍스트와 AI 피드백을 확인해 보세요!</div>
                 </div>
                 <button onClick={nextQuestion} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '12px 36px', fontSize: 15, fontWeight: 700, cursor: 'pointer' }}>
                     {qIndex + 1 >= questions.length ? '🎉 면접 종료' : '다음 질문 →'}
                   </button>
               </div>
             )}
 
             {phase === PHASE.DONE && (
               <div className="fade-up" style={{ textAlign: 'center' }}>
                 <div style={{ fontSize: 42, marginBottom: 10 }}>🎉</div>
                 <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 6 }}>면접 완료!</div>
                 <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 20 }}>{questions.length}개 질문 · {fmt(totalSec)} 소요</div>
                 <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
                   <button onClick={handleExit} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 10, padding: '10px 24px', color: 'rgba(255,255,255,.6)', fontSize: 14, cursor: 'pointer' }}>목록으로</button>
                   {interviewId && (
                     <button onClick={() => navigate(`/interview/${interviewId}/result`)} style={{ background: '#4f6ef7', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 28px', fontSize: 14, fontWeight: 700, cursor: 'pointer' }}>
                       상세 분석 결과 보기
                     </button>
                   )}
                 </div>
               </div>
             )}
           </div>
         </div>
       </div>
 
       {/* ── 로그 패널 ── */}
       <div className={`pi-log-panel${logOpen ? ' open' : ''}`}>
         <div className="pi-log-inner">
           <div style={{ fontSize: 13, fontWeight: 700, color: 'rgba(255,255,255,.45)', marginBottom: 14 }}>📋 면접 로그</div>
           {log.length === 0
             ? <div style={{ fontSize: 13, color: 'rgba(255,255,255,.25)', textAlign: 'center', marginTop: 40 }}>아직 기록이 없습니다</div>
             : log.map((item, i) => (
               <div key={i} className="pi-log-item">
                 <div className="pi-log-q">Q{i + 1}. {typeof item.q === 'string' ? item.q : JSON.stringify(item.q)}</div>
                 <div className="pi-log-a">A: {typeof item.a === 'string' ? item.a : JSON.stringify(item.a) || '(없음)'}</div>
                 <div className="pi-log-f">💡 {typeof item.feedback === 'string' ? item.feedback : JSON.stringify(item.feedback)}</div>
               </div>
             ))
           }
         </div>
       </div>
 
       {/* 나가기 확인 */}
       {exitConfirm && (
         <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 600 }}>
           <div style={{ background: '#111422', borderRadius: 14, padding: '28px 32px', minWidth: 300, textAlign: 'center', border: '1px solid rgba(255,255,255,.1)' }}>
             <div style={{ fontSize: 18, fontWeight: 700, color: '#fff', marginBottom: 10 }}>면접을 종료하시겠습니까?</div>
             <div style={{ fontSize: 13, color: 'rgba(255,255,255,.4)', marginBottom: 24 }}>진행 중인 내용은 저장되지 않습니다.</div>
             <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
               <button onClick={() => setExitConfirm(false)} style={{ background: 'rgba(255,255,255,.07)', border: '1px solid rgba(255,255,255,.15)', borderRadius: 8, padding: '10px 22px', color: 'rgba(255,255,255,.6)', cursor: 'pointer', fontSize: 14 }}>계속 진행</button>
               <button onClick={handleExit} style={{ background: '#ef4444', border: 'none', borderRadius: 8, padding: '10px 22px', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>종료</button>
             </div>
           </div>
         </div>
       )}
     </div>
   )
 }
