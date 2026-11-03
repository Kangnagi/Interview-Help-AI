import { useState, useEffect, useRef } from 'react'                  // 로컬 상태 관리 및 마운트 시 작업
import { useNavigate, useParams } from 'react-router-dom'    // 라우팅
import { useResumeStore } from '@/store/resumeStore'        // 자기소개서 상태 관리
import { resumeAPI } from '@/services/api'                  // 파일로 채우기
import toast from 'react-hot-toast'                          // 토스트 알림

const SELF_INTRO_MAX = 3000   // 서버도 질문 생성에 이 길이까지만 쓴다 (llama_service.SELF_INTRO_MAX)
const FILE_ACCEPT = '.pdf,.hwp,.hwpx,.docx,.txt'
const FILE_MAX_MB = 5
const PASTE_MAX = 20000
const FIELD_NAMES = { title: '제목', companyName: '기업명', jobTitle: '지원 업무명', jobDescription: '직무 수행 업무', idealCandidate: '인재상', selfIntroduction: '자기소개서' }
// 채용공고는 회사 쪽 칸, 이력서 · 자기소개서는 자기소개서 칸만 채운다
const KIND_FIELDS = {
  posting: ['title', 'companyName', 'jobTitle', 'jobDescription', 'idealCandidate'],
  intro: ['selfIntroduction'],
}

export default function ResumeFormPage() {
  const navigate = useNavigate()
  const { id } = useParams()                                  // URL 파라미터에서 자기소개서 ID 추출
  const { addResume, updateResume, getResume, loadedFor, loadError } = useResumeStore()
  const isEdit = Boolean(id)                                 // 수정 모드 여부

  // 폼 데이터
  const [form, setForm] = useState({
    title: '',                 // 자기소개서 제목
    companyName: '',           // 회사명
    jobTitle: '',              // 직무명
    jobDescription: '',        // 직무 설명
    idealCandidate: '',        // 인재상 (선택사항)
    selfIntroduction: '',      // 자기소개서 내용 (선택사항) — 여기 쓴 경험에서 키워드를 뽑아 꼬리 질문을 만든다
  })
  const [errors, setErrors] = useState({})                    // 입력값 검증 에러
  const [saving, setSaving] = useState(false)                 // 서버에 저장 중 (두 번 눌러 두 개 생기지 않게)
  const [parsing, setParsing] = useState(null)                // 읽는 중인 종류: 'posting' | 'intro' | null
  const [dragOver, setDragOver] = useState(null)              // 파일을 끌어다 대고 있는 칸: 'posting' | 'intro' | null
  const [pasteOpen, setPasteOpen] = useState(false)           // 채용공고 붙여넣기 창
  const [pasteText, setPasteText] = useState('')
  const postingFileRef = useRef(null)
  const introFileRef = useRef(null)

  // 수정 모드일 때 기존 데이터 로드 (서버에서 목록을 다 불러온 뒤)
  useEffect(() => {
    if (isEdit && (loadedFor || loadError)) {
      const r = getResume(id)
      // 예전에 저장한 자기소개서에는 없는 칸이 있을 수 있어 빈 문자열로 채운다
      if (r) setForm({ title: r.title || '', companyName: r.companyName || '', jobTitle: r.jobTitle || '', jobDescription: r.jobDescription || '',
                       idealCandidate: r.idealCandidate || '', selfIntroduction: r.selfIntroduction || '' })
      else { toast.error('자기소개서를 찾을 수 없습니다'); navigate('/resume') }
    }
  }, [id, loadedFor, loadError])

  // 입력값 업데이트 헬퍼 함수
  const set = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }))

  // 서버가 읽어 준 내용으로 칸 채우기 — 채용공고면 회사 쪽 칸, 이력서 · 자기소개서면 자기소개서 칸만
  const applyParsed = (data, kind) => {
    const all = {
      title: data.title, companyName: data.company_name, jobTitle: data.job_title,
      jobDescription: data.job_description, idealCandidate: data.ideal_candidate, selfIntroduction: data.self_introduction,
    }
    const found = KIND_FIELDS[kind].filter((k) => all[k])
    if (found.length === 0) {
      toast.error(kind === 'posting' ? '채용공고에서 채울 내용을 찾지 못했어요. 직접 입력해 주세요.' : '자기소개서 내용을 찾지 못했어요.')
      return
    }
    // 이미 입력한 칸을 다른 내용으로 바꾸게 되면 먼저 묻는다
    const overwrite = found.filter((k) => form[k].trim() && form[k].trim() !== all[k].trim())
    const replace = overwrite.length === 0 ||
      window.confirm(`이미 입력한 칸(${overwrite.map((k) => FIELD_NAMES[k]).join(', ')})을 새 내용으로 바꿀까요?\n취소를 누르면 빈 칸만 채웁니다.`)
    setForm((p) => {
      const next = { ...p }
      found.forEach((k) => { if (replace || !p[k].trim()) next[k] = all[k] })
      return next
    })
    setErrors({})
    toast.success(`${found.map((k) => FIELD_NAMES[k]).join(' · ')} 칸을 채웠습니다. 내용을 확인해 주세요.`, { duration: 5000 })
    const notes = []
    if (data.truncated) notes.push(`자기소개서가 길어 앞 ${SELF_INTRO_MAX.toLocaleString()}자만 넣었습니다`)
    if (data.removed_personal) notes.push('전화번호 · 이메일 같은 개인정보는 빼고 넣었습니다')
    if (notes.length) toast(notes.join('\n'), { icon: 'ℹ️', duration: 6000 })
    if (kind === 'posting') {
      const missing = ['companyName', 'jobTitle', 'jobDescription'].filter((k) => !all[k] && !form[k].trim())
      if (missing.length) toast(`${missing.map((k) => FIELD_NAMES[k]).join(' · ')}은(는) 채용공고에서 찾지 못했어요. 직접 입력해 주세요.`, { icon: '✏️', duration: 6000 })
    }
  }

  const showError = (err) => {
    const detail = err.response?.data?.detail
    toast.error(typeof detail === 'string' ? detail : '내용을 읽지 못했습니다. 잠시 후 다시 시도해주세요')
  }

  // 파일로 채우기 — 파일은 서버에 저장하지 않고 글자만 읽는다 (전화번호 · 이메일 · 주민번호는 지움)
  const handleFile = async (file, kind) => {
    if (!file || parsing) return
    if (file.size > FILE_MAX_MB * 1024 * 1024) return toast.error(`파일이 너무 큽니다 (최대 ${FILE_MAX_MB}MB)`)
    // 끌어다 놓기는 파일 선택 창의 accept 제한을 거치지 않으므로 여기서도 확장자를 본다 (서버는 확장자가 아니라 파일 내용으로 다시 확인)
    const ext = (file.name.match(/\.[^.]+$/)?.[0] || '').toLowerCase()
    if (!FILE_ACCEPT.split(',').includes(ext)) return toast.error('PDF · HWP · HWPX · DOCX · TXT 파일만 올릴 수 있습니다')
    setParsing(kind)
    try {
      const { data } = await resumeAPI.parseFile(file, kind)
      applyParsed(data, kind)
    } catch (err) {
      showError(err)
    } finally {
      setParsing(null)
      const ref = kind === 'posting' ? postingFileRef : introFileRef
      if (ref.current) ref.current.value = ''
    }
  }

  // 채용공고 붙여넣기 — 사람인 · 잡코리아 같은 사이트의 공고 내용을 복사해 붙여넣으면 칸을 나눠 채운다
  const handlePaste = async () => {
    if (!pasteText.trim() || parsing) return
    setParsing('posting')
    try {
      const { data } = await resumeAPI.parseText(pasteText, 'posting')
      applyParsed(data, 'posting')
      setPasteOpen(false)
      setPasteText('')
    } catch (err) {
      showError(err)
    } finally {
      setParsing(null)
    }
  }

  // 칸에 파일을 끌어다 놓기
  const dropProps = (kind) => ({
    onDragOver: (e) => { if (e.dataTransfer.types.includes('Files')) { e.preventDefault(); setDragOver(kind) } },
    onDragLeave: () => setDragOver(null),
    onDrop: (e) => { if (e.dataTransfer.files?.length) { e.preventDefault(); setDragOver(null); handleFile(e.dataTransfer.files[0], kind) } },
  })

  const validate = () => {
    const e = {}
    if (!form.title.trim()) e.title = '제목을 입력해주세요'
    if (!form.companyName.trim()) e.companyName = '기업명을 입력해주세요'
    if (!form.jobTitle.trim()) e.jobTitle = '지원 업무명을 입력해주세요'
    if (!form.jobDescription.trim()) e.jobDescription = '직무 수행 업무를 입력해주세요'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async () => {
    if (!validate() || saving) return
    setSaving(true)
    try {
      // 계정(서버)에 저장 — 다른 PC에서 같은 이메일로 로그인해도 보인다
      if (isEdit) { await updateResume(id, form); toast.success('수정되었습니다') }
      else { await addResume(form); toast.success('자기소개서가 등록되었습니다') }
      navigate('/resume')
    } catch (err) {
      const detail = err.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : '저장하지 못했습니다. 잠시 후 다시 시도해주세요')
      setSaving(false)
    }
  }

  return (
    <div style={{ maxWidth: 680, margin: '0 auto' }}>
      <style>{`
        .rf-card { background:#fff; border-radius:var(--radius-lg); border:1px solid var(--border); padding:32px; }
        .rf-title { font-size:20px; font-weight:700; margin-bottom:28px; color:var(--text-primary); text-align:center; }
        .rf-group { margin-bottom:20px; }
        .rf-label { display:flex; align-items:center; gap:4px; font-size:14px; font-weight:600; color:var(--text-primary); margin-bottom:8px; }
        .rf-label-req { color:#ef4444; }
        .rf-input { width:100%; padding:11px 14px; border:1.5px solid var(--border); border-radius:var(--radius-sm); font-size:14px; transition:border-color .15s; background:#fff; }
        .rf-input:focus { border-color:var(--primary); outline:none; }
        .rf-input.err { border-color:#ef4444; }
        .rf-textarea { resize:vertical; min-height:110px; }
        .rf-error { font-size:12px; color:#ef4444; margin-top:5px; }
        .rf-row { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .rf-info { background:#f0f4ff; border-radius:10px; padding:12px 16px; font-size:13px; color:#4f6ef7; margin-bottom:20px; }
        .rf-footer { display:flex; gap:12px; margin-top:28px; }
        .rf-label-row { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px; flex-wrap:wrap; }
        .rf-label-row .rf-label { margin-bottom:0; }
        .rf-file-btn { display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:8px; font-size:13px; font-weight:600; color:var(--primary); background:#eef2ff; border:1px solid #c7d2fe; cursor:pointer; transition:background .15s; }
        .rf-file-btn:hover:not(:disabled) { background:#e0e7ff; }
        .rf-file-btn:disabled { cursor:wait; opacity:.7; }
        .rf-textarea.over { border-color:var(--primary); background:#eef2ff; }
        .rf-posting { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; border:1.5px dashed #c7d2fe; border-radius:12px; padding:12px 16px; margin-bottom:22px; background:#fafbff; transition:background .15s, border-color .15s; }
        .rf-posting.over { background:#eef2ff; border-color:var(--primary); }
        .rf-posting-title { font-size:14px; font-weight:600; color:var(--text-primary); }
        .rf-posting-btns { display:flex; gap:8px; flex-shrink:0; }
        .rf-paste-bg { position:fixed; inset:0; background:rgba(0,0,0,.45); display:flex; align-items:center; justify-content:center; z-index:1000; padding:16px; }
        .rf-paste-box { background:#fff; border-radius:16px; padding:24px; width:100%; max-width:640px; box-shadow:0 8px 40px rgba(0,0,0,.18); }
        .rf-file-note { font-size:12px; color:var(--text-muted); margin-top:4px; }
        @media(max-width:600px){ .rf-row { grid-template-columns:1fr; } }
      `}</style>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button onClick={() => navigate('/resume')} style={{ background: '#f3f4f6', border: 'none', borderRadius: 8, padding: '8px 14px', cursor: 'pointer', fontSize: 14 }}>
          ← 목록으로
        </button>
        <h2 style={{ fontSize: 18, fontWeight: 700 }}>{isEdit ? '자기소개서 수정' : '자기소개서 작성'}</h2>
      </div>

      <div className="rf-card">
        <div className="rf-info">
          💡 작성한 자기소개서를 바탕으로 AI가 맞춤형 면접 질문을 생성합니다. 최대한 상세히 작성해 주세요.
        </div>

        {/* 채용공고로 채우기 — 제목 · 채용 정보 · 직무 수행 업무 · 인재상 */}
        <div className={`rf-posting${dragOver === 'posting' ? ' over' : ''}`} {...dropProps('posting')}>
          <div>
            <div className="rf-posting-title">📄 채용공고로 채우기</div>
            <div className="rf-file-note" style={{ marginTop: 2 }}>공고 파일을 올리거나 내용을 붙여넣으면 제목 · 채용 정보 · 직무 수행 업무 · 인재상을 채웁니다.</div>
          </div>
          <div className="rf-posting-btns">
            <button type="button" className="rf-file-btn" disabled={!!parsing} onClick={() => postingFileRef.current?.click()}
                    title={`PDF · HWP · HWPX · DOCX · TXT (${FILE_MAX_MB}MB까지)`}>
              {parsing === 'posting' ? '⏳ 읽는 중...' : '📎 파일'}
            </button>
            <button type="button" className="rf-file-btn" disabled={!!parsing} onClick={() => setPasteOpen(true)}>📋 붙여넣기</button>
          </div>
          <input ref={postingFileRef} type="file" accept={FILE_ACCEPT} style={{ display: 'none' }} onChange={(e) => handleFile(e.target.files?.[0], 'posting')} />
        </div>

        {/* 제목 */}
        <div className="rf-group">
          <div className="rf-label">제목 <span className="rf-label-req">*</span></div>
          <input className={`rf-input${errors.title ? ' err' : ''}`} placeholder="예) 카카오 서버 개발자 지원" value={form.title} onChange={set('title')} maxLength={200} />
          {errors.title && <div className="rf-error">{errors.title}</div>}
        </div>

        {/* 채용 정보 */}
        <div className="rf-group">
          <div className="rf-label">채용 정보 <span className="rf-label-req">*</span></div>
          <div className="rf-row">
            <div>
              <input className={`rf-input${errors.companyName ? ' err' : ''}`} placeholder="기업명 (예: 카카오)" value={form.companyName} onChange={set('companyName')} maxLength={200} />
              {errors.companyName && <div className="rf-error">{errors.companyName}</div>}
            </div>
            <div>
              <input className={`rf-input${errors.jobTitle ? ' err' : ''}`} placeholder="지원 업무명 (예: 서버 개발자)" value={form.jobTitle} onChange={set('jobTitle')} maxLength={200} />
              {errors.jobTitle && <div className="rf-error">{errors.jobTitle}</div>}
            </div>
          </div>
        </div>

        {/* 직무 수행 업무 */}
        <div className="rf-group">
          <div className="rf-label">직무 수행 업무 <span className="rf-label-req">*</span></div>
          <textarea
            className={`rf-input rf-textarea${errors.jobDescription ? ' err' : ''}`}
            placeholder="채용공고의 담당 업무 · 자격 요건을 적어 주세요. 위 '채용공고로 채우기'로 공고 파일이나 내용을 넣으면 자동으로 채워집니다."
            value={form.jobDescription}
            onChange={set('jobDescription')}
            maxLength={5000}
          />
          {errors.jobDescription && <div className="rf-error">{errors.jobDescription}</div>}
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right', marginTop: 4 }}>{form.jobDescription.length}자</div>
        </div>

        {/* 인재상 */}
        <div className="rf-group">
          <div className="rf-label">인재상</div>
          <textarea
            className="rf-input rf-textarea"
            placeholder="지원하는 회사의 인재상 또는 본인이 지향하는 인재상을 작성해 주세요. (선택사항)"
            value={form.idealCandidate}
            maxLength={3000}
            onChange={set('idealCandidate')}
          />
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right', marginTop: 4 }}>{form.idealCandidate.length}자</div>
        </div>

        {/* 자기소개서 내용 */}
        <div className="rf-group">
          <div className="rf-label-row">
            <div className="rf-label">자기소개서 내용</div>
            {/* 이력서 · 자기소개서 파일로 채우기 — 자기소개서 칸만 채운다 */}
            <button type="button" className="rf-file-btn" disabled={!!parsing} onClick={() => introFileRef.current?.click()}
                    title={`PDF · HWP · HWPX · DOCX · TXT (${FILE_MAX_MB}MB까지) — 파일은 저장하지 않고 내용만 칸에 채웁니다`}>
              {parsing === 'intro' ? '⏳ 파일 읽는 중...' : '📎 이력서 · 자기소개서 파일로 채우기'}
            </button>
            <input ref={introFileRef} type="file" accept={FILE_ACCEPT} style={{ display: 'none' }} onChange={(e) => handleFile(e.target.files?.[0], 'intro')} />
          </div>
          <textarea
            className={`rf-input rf-textarea${dragOver === 'intro' ? ' over' : ''}`}
            style={{ minHeight: 220 }}
            {...dropProps('intro')}
            maxLength={SELF_INTRO_MAX}
            placeholder={'지원 동기, 직무 관련 경험(프로젝트 · 실습 · 아르바이트 · 대외활동), 성과 등을 자유롭게 작성해 주세요. (선택사항)\n여기 쓴 경험을 바탕으로 "그때 맡은 역할은?", "어떻게 해결했나요?" 같은 꼬리 질문이 만들어집니다.'}
            value={form.selfIntroduction}
            onChange={set('selfIntroduction')}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div className="rf-file-note">📎 이력서 · 자기소개서 파일(PDF · HWP · HWPX · DOCX · TXT, {FILE_MAX_MB}MB까지)을 올리거나 이 칸에 끌어다 놓으면 자기소개서 내용을 채웁니다. 전화번호 · 주소 같은 개인정보는 빼고, 파일은 저장하지 않습니다.</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4, flexShrink: 0 }}>{form.selfIntroduction.length} / {SELF_INTRO_MAX}자</div>
          </div>
        </div>

        <div className="rf-footer">
          <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => navigate('/resume')}>취소</button>
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={handleSubmit} disabled={saving}>
            {saving ? '저장 중...' : isEdit ? '✅ 수정 완료' : '📋 등록하기'}
          </button>
        </div>
      </div>

      {/* 채용공고 붙여넣기 창 */}
      {pasteOpen && (
        <div className="rf-paste-bg" onClick={() => !parsing && setPasteOpen(false)}>
          <div className="rf-paste-box" onClick={(e) => e.stopPropagation()}>
            <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>📋 채용공고 붙여넣기</div>
            <div className="rf-file-note" style={{ marginBottom: 12 }}>
              채용 사이트의 공고 내용을 전체 선택(Ctrl+A) · 복사(Ctrl+C)해서 아래에 붙여넣으세요. 모집부문 · 담당업무 · 자격요건 · 우대사항 · 인재상을 찾아 칸을 채웁니다.
            </div>
            <textarea
              className="rf-input rf-textarea"
              style={{ minHeight: 260 }}
              autoFocus
              maxLength={PASTE_MAX}
              placeholder={'예)\n[그린페이] 백엔드 개발자 채용\n모집부문: 백엔드 개발자\n담당업무\n- 결제 API 개발\n자격요건\n- 서버 개발 경험'}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
            />
            <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right', marginTop: 4 }}>{pasteText.length.toLocaleString()} / {PASTE_MAX.toLocaleString()}자</div>
            <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
              <button className="btn btn-outline" style={{ flex: 1 }} disabled={!!parsing} onClick={() => setPasteOpen(false)}>취소</button>
              <button className="btn btn-primary" style={{ flex: 2 }} disabled={!!parsing || !pasteText.trim()} onClick={handlePaste}>
                {parsing === 'posting' ? '읽는 중...' : '칸 채우기'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
