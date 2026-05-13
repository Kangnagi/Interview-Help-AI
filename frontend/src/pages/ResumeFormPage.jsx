import { useState, useEffect } from 'react'                  // 로컬 상태 관리 및 마운트 시 작업
import { useNavigate, useParams } from 'react-router-dom'    // 라우팅
import { useResumeStore } from '@/store/resumeStore'        // 자기소개서 상태 관리
import toast from 'react-hot-toast'                          // 토스트 알림

export default function ResumeFormPage() {
  const navigate = useNavigate()
  const { id } = useParams()                                  // URL 파라미터에서 자기소개서 ID 추출
  const { addResume, updateResume, getResume } = useResumeStore()
  const isEdit = Boolean(id)                                 // 수정 모드 여부

  // 폼 데이터
  const [form, setForm] = useState({
    title: '',                 // 자기소개서 제목
    companyName: '',           // 회사명
    jobTitle: '',              // 직무명
    jobDescription: '',        // 직무 설명
    idealCandidate: '',        // 인재상 (선택사항)
  })
  const [errors, setErrors] = useState({})                    // 입력값 검증 에러

  // 수정 모드일 때 기존 데이터 로드
  useEffect(() => {
    if (isEdit) {
      const r = getResume(id)
      if (r) setForm({ title: r.title, companyName: r.companyName, jobTitle: r.jobTitle, jobDescription: r.jobDescription, idealCandidate: r.idealCandidate })
      else { toast.error('자기소개서를 찾을 수 없습니다'); navigate('/resume') }
    }
  }, [id])

  // 입력값 업데이트 헬퍼 함수
  const set = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }))

  const validate = () => {
    const e = {}
    if (!form.title.trim()) e.title = '제목을 입력해주세요'
    if (!form.companyName.trim()) e.companyName = '기업명을 입력해주세요'
    if (!form.jobTitle.trim()) e.jobTitle = '지원 업무명을 입력해주세요'
    if (!form.jobDescription.trim()) e.jobDescription = '직무 수행 업무를 입력해주세요'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = () => {
    if (!validate()) return
    if (isEdit) { updateResume(id, form); toast.success('수정되었습니다') }
    else { addResume(form); toast.success('자기소개서가 등록되었습니다') }
    navigate('/resume')
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

        {/* 제목 */}
        <div className="rf-group">
          <div className="rf-label">제목 <span className="rf-label-req">*</span></div>
          <input className={`rf-input${errors.title ? ' err' : ''}`} placeholder="예) 카카오 서버 개발자 지원" value={form.title} onChange={set('title')} />
          {errors.title && <div className="rf-error">{errors.title}</div>}
        </div>

        {/* 채용 정보 */}
        <div className="rf-group">
          <div className="rf-label">채용 정보 <span className="rf-label-req">*</span></div>
          <div className="rf-row">
            <div>
              <input className={`rf-input${errors.companyName ? ' err' : ''}`} placeholder="기업명 (예: 카카오)" value={form.companyName} onChange={set('companyName')} />
              {errors.companyName && <div className="rf-error">{errors.companyName}</div>}
            </div>
            <div>
              <input className={`rf-input${errors.jobTitle ? ' err' : ''}`} placeholder="지원 업무명 (예: 서버 개발자)" value={form.jobTitle} onChange={set('jobTitle')} />
              {errors.jobTitle && <div className="rf-error">{errors.jobTitle}</div>}
            </div>
          </div>
        </div>

        {/* 직무 수행 업무 */}
        <div className="rf-group">
          <div className="rf-label">직무 수행 업무 <span className="rf-label-req">*</span></div>
          <textarea
            className={`rf-input rf-textarea${errors.jobDescription ? ' err' : ''}`}
            placeholder="담당하게 될 주요 업무나, 지금까지 수행한 직무 경험을 상세히 작성해 주세요."
            value={form.jobDescription}
            onChange={set('jobDescription')}
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
            onChange={set('idealCandidate')}
          />
          <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'right', marginTop: 4 }}>{form.idealCandidate.length}자</div>
        </div>

        <div className="rf-footer">
          <button className="btn btn-outline" style={{ flex: 1 }} onClick={() => navigate('/resume')}>취소</button>
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={handleSubmit}>
            {isEdit ? '✅ 수정 완료' : '📋 등록하기'}
          </button>
        </div>
      </div>
    </div>
  )
}
