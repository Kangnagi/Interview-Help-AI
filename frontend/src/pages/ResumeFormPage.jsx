import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import toast from 'react-hot-toast'

export default function ResumeFormPage() {
  const navigate = useNavigate()
  const { id } = useParams()
  const { addResume, updateResume, getResume } = useResumeStore()

  const existing = id ? getResume(id) : null

  const [form, setForm] = useState({
    title:          existing?.title || '',
    companyName:    existing?.companyName || '',
    jobTitle:       existing?.jobTitle || '',
    jobDescription: existing?.jobDescription || '',
    talentProfile:  existing?.talentProfile || '',
  })

  const [errors, setErrors] = useState({})

  const validate = () => {
    const e = {}
    if (!form.title.trim())          e.title = '제목을 입력해주세요'
    if (!form.companyName.trim())    e.companyName = '기업명을 입력해주세요'
    if (!form.jobTitle.trim())       e.jobTitle = '지원 업무명을 입력해주세요'
    if (!form.jobDescription.trim()) e.jobDescription = '직무 수행 업무를 입력해주세요'
    if (!form.talentProfile.trim())  e.talentProfile = '인재상을 입력해주세요'
    return e
  }

  const handleChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }))
  }

  const handleSubmit = () => {
    const e = validate()
    if (Object.keys(e).length) {
      setErrors(e)
      toast.error('모든 항목을 입력해주세요')
      return
    }

    if (existing) {
      updateResume(id, form)
      toast.success('자기소개서가 수정되었습니다')
    } else {
      addResume(form)
      toast.success('자기소개서가 등록되었습니다')
    }
    navigate('/resume')
  }

  const charCount = (val, max) => (
    <span style={{ fontSize: 12, color: val.length > max * 0.9 ? 'var(--warning)' : 'var(--text-muted)' }}>
      {val.length} / {max}
    </span>
  )

  return (
    <div className="rf-page">
      {/* 헤더 */}
      <div className="rf-header">
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/resume')}>
          ← 목록으로
        </button>
        <h2 className="rf-title">{existing ? '자기소개서 수정' : '자기소개서 작성'}</h2>
        <p className="rf-sub">작성하신 내용을 바탕으로 AI가 맞춤형 면접 질문을 생성합니다</p>
      </div>

      <div className="rf-card">
        {/* 제목 */}
        <div className="rf-field">
          <div className="rf-label-row">
            <label className="rf-label">제목 <span className="rf-required">*</span></label>
            {charCount(form.title, 50)}
          </div>
          <input
            className={`rf-input ${errors.title ? 'rf-input-error' : ''}`}
            placeholder="예) 네이버 프론트엔드 개발자 자기소개서"
            value={form.title}
            onChange={handleChange('title')}
            maxLength={50}
          />
          {errors.title && <p className="rf-error">{errors.title}</p>}
        </div>

        {/* 채용 정보 */}
        <div className="rf-field">
          <label className="rf-label">채용 정보 <span className="rf-required">*</span></label>
          <div className="rf-row">
            <div style={{ flex: 1 }}>
              <input
                className={`rf-input ${errors.companyName ? 'rf-input-error' : ''}`}
                placeholder="기업명"
                value={form.companyName}
                onChange={handleChange('companyName')}
                maxLength={50}
              />
              {errors.companyName && <p className="rf-error">{errors.companyName}</p>}
            </div>
            <div style={{ flex: 1 }}>
              <input
                className={`rf-input ${errors.jobTitle ? 'rf-input-error' : ''}`}
                placeholder="지원 업무명 (예: 프론트엔드 개발자)"
                value={form.jobTitle}
                onChange={handleChange('jobTitle')}
                maxLength={50}
              />
              {errors.jobTitle && <p className="rf-error">{errors.jobTitle}</p>}
            </div>
          </div>
        </div>

        {/* 직무 수행 업무 */}
        <div className="rf-field">
          <div className="rf-label-row">
            <label className="rf-label">직무 수행 업무 <span className="rf-required">*</span></label>
            {charCount(form.jobDescription, 800)}
          </div>
          <p className="rf-hint">해당 직무에서 수행하는 업무나 지원자의 경험·역량을 구체적으로 작성해주세요</p>
          <textarea
            className={`rf-textarea ${errors.jobDescription ? 'rf-input-error' : ''}`}
            placeholder="예) React, TypeScript를 활용한 웹 프론트엔드 개발&#10;컴포넌트 설계, 성능 최적화, API 연동 경험&#10;Git 기반 협업 및 코드 리뷰..."
            rows={6}
            value={form.jobDescription}
            onChange={handleChange('jobDescription')}
            maxLength={800}
          />
          {errors.jobDescription && <p className="rf-error">{errors.jobDescription}</p>}
        </div>

        {/* 인재상 */}
        <div className="rf-field">
          <div className="rf-label-row">
            <label className="rf-label">인재상 <span className="rf-required">*</span></label>
            {charCount(form.talentProfile, 500)}
          </div>
          <p className="rf-hint">지원 기업의 인재상이나 본인의 강점/가치관을 작성해주세요</p>
          <textarea
            className={`rf-textarea ${errors.talentProfile ? 'rf-input-error' : ''}`}
            placeholder="예) 창의적 문제해결 능력을 갖춘 인재&#10;지속적인 학습과 성장을 추구&#10;팀원과 적극적으로 소통하고 협력..."
            rows={5}
            value={form.talentProfile}
            onChange={handleChange('talentProfile')}
            maxLength={500}
          />
          {errors.talentProfile && <p className="rf-error">{errors.talentProfile}</p>}
        </div>

        {/* AI 활용 안내 */}
        <div className="rf-ai-notice">
          <span className="rf-ai-icon">🤖</span>
          <div>
            <strong>AI 맞춤 면접 질문 생성</strong>
            <p>작성하신 내용을 바탕으로 AI가 직무 관련 질문, 인성 질문, 경험 기반 질문을 자동으로 생성합니다.</p>
          </div>
        </div>

        {/* 버튼 */}
        <div className="rf-actions">
          <button className="btn btn-outline" onClick={() => navigate('/resume')}>취소</button>
          <button className="btn btn-primary btn-lg" onClick={handleSubmit}>
            {existing ? '✅ 수정 완료' : '✅ 등록하기'}
          </button>
        </div>
      </div>

      <style>{`
        .rf-page { max-width: 720px; margin: 0 auto; padding-bottom: 40px; }

        .rf-header { margin-bottom: 24px; }
        .rf-title { font-size: 24px; font-weight: 700; margin: 16px 0 6px; }
        .rf-sub { font-size: 14px; color: var(--text-secondary); }

        .rf-card {
          background: var(--bg-card);
          border-radius: var(--radius-lg);
          border: 1px solid var(--border);
          padding: 32px;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .rf-field { display: flex; flex-direction: column; gap: 8px; }
        .rf-label-row { display: flex; align-items: center; justify-content: space-between; }
        .rf-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
        .rf-required { color: var(--danger); }
        .rf-hint { font-size: 12px; color: var(--text-muted); }

        .rf-input, .rf-textarea {
          width: 100%;
          padding: 11px 14px;
          border: 1.5px solid var(--border);
          border-radius: var(--radius-md);
          font-size: 14px;
          transition: border-color 0.15s;
          background: var(--bg-page);
        }
        .rf-input:focus, .rf-textarea:focus { border-color: var(--primary); background: #fff; }
        .rf-input-error { border-color: var(--danger) !important; }
        .rf-textarea { resize: vertical; min-height: 100px; line-height: 1.6; }
        .rf-error { font-size: 12px; color: var(--danger); }

        .rf-row { display: flex; gap: 12px; }

        .rf-ai-notice {
          display: flex;
          gap: 14px;
          align-items: flex-start;
          padding: 16px;
          background: var(--primary-light);
          border-radius: var(--radius-md);
          border: 1px solid rgba(79,110,247,.2);
        }
        .rf-ai-icon { font-size: 24px; flex-shrink: 0; }
        .rf-ai-notice strong { font-size: 14px; display: block; margin-bottom: 4px; color: var(--primary); }
        .rf-ai-notice p { font-size: 13px; color: var(--text-secondary); line-height: 1.5; }

        .rf-actions { display: flex; gap: 12px; justify-content: flex-end; padding-top: 8px; }
      `}</style>
    </div>
  )
}
