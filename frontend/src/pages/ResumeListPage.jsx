import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'

const MODE_ICONS = {
  practice: '🎓',
  real: '💼',
  history: '📋',
}

export default function ResumeListPage() {
  const navigate = useNavigate()
  const { resumes, deleteResume } = useResumeStore()
  const [selectedResume, setSelectedResume] = useState(null) // 선택된 자기소개서
  const [showModeModal, setShowModeModal] = useState(false)  // 면접 모드 선택 모달
  const [deleteConfirm, setDeleteConfirm] = useState(null)   // 삭제 확인 대상

  const handleResumeClick = (resume) => {
    setSelectedResume(resume)
    setShowModeModal(true)
  }

  const handleModeSelect = (mode) => {
    setShowModeModal(false)
    if (mode === 'history') {
      navigate(`/resume/${selectedResume.id}/history`)
    } else if (mode === 'practice') {
      navigate(`/interview/practice/${selectedResume.id}`)
    } else if (mode === 'real') {
      navigate(`/interview/real/${selectedResume.id}`)
    }
  }

  const handleDelete = (e, id) => {
    e.stopPropagation()
    setDeleteConfirm(id)
  }

  const confirmDelete = () => {
    deleteResume(deleteConfirm)
    setDeleteConfirm(null)
  }

  return (
    <div className="resume-list-page">
      {/* 헤더 */}
      <div className="rl-header">
        <div>
          <h2 className="rl-title">자기소개서 목록</h2>
          <p className="rl-subtitle">
            {resumes.length > 0
              ? `총 ${resumes.length}개의 자기소개서`
              : 'AI 면접 연습을 위한 자기소개서를 작성해주세요'}
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => navigate('/resume/new')}
        >
          ✍️ 자기소개서 작성
        </button>
      </div>

      {/* 목록 */}
      {resumes.length === 0 ? (
        <div className="rl-empty">
          <div className="rl-empty-icon">📄</div>
          <p className="rl-empty-title">아직 작성된 자기소개서가 없습니다</p>
          <p className="rl-empty-sub">자기소개서를 작성하면 맞춤형 AI 면접을 시작할 수 있어요</p>
          <button
            className="btn btn-primary"
            style={{ marginTop: 20 }}
            onClick={() => navigate('/resume/new')}
          >
            첫 자기소개서 작성하기
          </button>
        </div>
      ) : (
        <div className="rl-grid">
          {resumes.map((resume) => (
            <div
              key={resume.id}
              className="rl-card"
              onClick={() => handleResumeClick(resume)}
            >
              <div className="rl-card-header">
                <div className="rl-card-badge">
                  {resume.jobTitle || '직무 미기재'}
                </div>
                <button
                  className="rl-delete-btn"
                  onClick={(e) => handleDelete(e, resume.id)}
                  title="삭제"
                >
                  🗑️
                </button>
              </div>

              <h3 className="rl-card-title">{resume.title}</h3>
              <p className="rl-card-company">
                🏢 {resume.companyName || '기업명 미기재'}
              </p>

              <div className="rl-card-preview">
                {resume.jobDescription
                  ? resume.jobDescription.slice(0, 80) + (resume.jobDescription.length > 80 ? '...' : '')
                  : '직무 수행 업무 미기재'}
              </div>

              <div className="rl-card-footer">
                <span className="rl-card-date">
                  {new Date(resume.createdAt).toLocaleDateString('ko-KR')}
                </span>
                <span className="rl-card-history">
                  면접 {(resume.interviewHistory || []).length}회
                </span>
              </div>

              <div className="rl-card-cta">클릭하여 면접 시작 →</div>
            </div>
          ))}
        </div>
      )}

      {/* 면접 모드 선택 모달 */}
      {showModeModal && selectedResume && (
        <div className="modal-overlay" onClick={() => setShowModeModal(false)}>
          <div className="modal-box mode-modal" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={() => setShowModeModal(false)}>✕</button>
            <h3 className="modal-title">무엇을 할까요?</h3>
            <p className="modal-sub">
              <strong>{selectedResume.title}</strong>
            </p>

            <div className="mode-options">
              <button className="mode-btn mode-practice" onClick={() => handleModeSelect('practice')}>
                <span className="mode-icon">🎓</span>
                <span className="mode-label">연습면접</span>
                <span className="mode-desc">질문 → 답변 → 피드백 반복 학습</span>
              </button>

              <button className="mode-btn mode-real" onClick={() => handleModeSelect('real')}>
                <span className="mode-icon">💼</span>
                <span className="mode-label">실전면접</span>
                <span className="mode-desc">실제 면접처럼 진행</span>
              </button>

              <button className="mode-btn mode-history" onClick={() => handleModeSelect('history')}>
                <span className="mode-icon">📋</span>
                <span className="mode-label">면접 기록</span>
                <span className="mode-desc">지난 면접 기록 보기</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {deleteConfirm && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal-box confirm-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">자기소개서 삭제</h3>
            <p style={{ color: 'var(--text-secondary)', marginTop: 8, fontSize: 14 }}>
              삭제하면 관련 면접 기록도 함께 삭제됩니다.<br />정말 삭제하시겠습니까?
            </p>
            <div className="modal-actions">
              <button className="btn btn-outline" onClick={() => setDeleteConfirm(null)}>취소</button>
              <button className="btn btn-danger" onClick={confirmDelete}>삭제</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .resume-list-page { padding: 0; }

        .rl-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 28px;
        }
        .rl-title { font-size: 22px; font-weight: 700; }
        .rl-subtitle { font-size: 14px; color: var(--text-secondary); margin-top: 4px; }

        .rl-empty {
          text-align: center;
          padding: 80px 20px;
          background: var(--bg-card);
          border-radius: var(--radius-lg);
          border: 2px dashed var(--border);
        }
        .rl-empty-icon { font-size: 48px; margin-bottom: 16px; }
        .rl-empty-title { font-size: 18px; font-weight: 600; }
        .rl-empty-sub { color: var(--text-secondary); margin-top: 8px; font-size: 14px; }

        .rl-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 20px;
        }

        .rl-card {
          background: var(--bg-card);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          padding: 20px;
          cursor: pointer;
          transition: all 0.2s;
          position: relative;
          overflow: hidden;
        }
        .rl-card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 3px;
          background: linear-gradient(90deg, var(--primary), #8B5CF6);
          opacity: 0;
          transition: opacity 0.2s;
        }
        .rl-card:hover { border-color: var(--primary); box-shadow: 0 4px 20px rgba(79,110,247,.12); transform: translateY(-2px); }
        .rl-card:hover::before { opacity: 1; }

        .rl-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .rl-card-badge {
          font-size: 11px;
          background: var(--primary-light);
          color: var(--primary);
          padding: 3px 10px;
          border-radius: 99px;
          font-weight: 600;
        }
        .rl-delete-btn { font-size: 14px; opacity: 0.4; transition: opacity 0.15s; background: none; border: none; cursor: pointer; padding: 2px 4px; }
        .rl-delete-btn:hover { opacity: 1; }

        .rl-card-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
        .rl-card-company { font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; }

        .rl-card-preview {
          font-size: 13px;
          color: var(--text-muted);
          line-height: 1.5;
          background: var(--bg-page);
          border-radius: var(--radius-sm);
          padding: 10px 12px;
          min-height: 48px;
        }

        .rl-card-footer {
          display: flex;
          justify-content: space-between;
          margin-top: 14px;
          font-size: 12px;
          color: var(--text-muted);
        }
        .rl-card-cta {
          margin-top: 12px;
          font-size: 12px;
          color: var(--primary);
          font-weight: 500;
          opacity: 0;
          transition: opacity 0.2s;
        }
        .rl-card:hover .rl-card-cta { opacity: 1; }

        /* 모달 공통 */
        .modal-overlay {
          position: fixed; inset: 0;
          background: rgba(0,0,0,.5);
          display: flex; align-items: center; justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(4px);
        }
        .modal-box {
          background: var(--bg-card);
          border-radius: var(--radius-lg);
          padding: 28px;
          width: 90%;
          position: relative;
          animation: modalIn .2s ease;
        }
        @keyframes modalIn {
          from { opacity: 0; transform: scale(.95) translateY(8px); }
          to   { opacity: 1; transform: scale(1) translateY(0); }
        }
        .modal-close {
          position: absolute; top: 16px; right: 16px;
          font-size: 16px; color: var(--text-muted);
          background: none; border: none; cursor: pointer;
        }
        .modal-title { font-size: 18px; font-weight: 700; }
        .modal-sub { font-size: 13px; color: var(--text-secondary); margin-top: 6px; }

        /* 모드 선택 */
        .mode-modal { max-width: 400px; }
        .mode-options { display: flex; flex-direction: column; gap: 12px; margin-top: 20px; }
        .mode-btn {
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 16px;
          border: 1.5px solid var(--border);
          border-radius: var(--radius-md);
          background: var(--bg-page);
          cursor: pointer;
          transition: all 0.15s;
          text-align: left;
        }
        .mode-btn:hover { border-color: var(--primary); background: var(--primary-light); }
        .mode-practice:hover { border-color: #10B981; background: #D1FAE5; }
        .mode-real:hover { border-color: #F59E0B; background: #FEF3C7; }
        .mode-history:hover { border-color: #8B5CF6; background: #EDE9FE; }
        .mode-icon { font-size: 24px; flex-shrink: 0; }
        .mode-label { font-size: 15px; font-weight: 700; display: block; }
        .mode-desc { font-size: 12px; color: var(--text-secondary); display: block; margin-top: 2px; }

        /* 삭제 확인 */
        .confirm-modal { max-width: 340px; }
        .modal-actions { display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }
      `}</style>
    </div>
  )
}
