import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import toast from 'react-hot-toast'

export default function ResumeListPage() {
  const navigate = useNavigate()
  const { resumes, deleteResume } = useResumeStore()

  // 모달 상태: null | { resumeId }
  const [actionModal, setActionModal] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  const handleCardClick = (resume) => {
    setActionModal({ resumeId: resume.id, title: resume.title })
  }

  const handleAction = (type) => {
    const { resumeId } = actionModal
    setActionModal(null)
    if (type === 'history') navigate(`/resume/${resumeId}/history`)
    else if (type === 'practice') navigate(`/interview/practice/${resumeId}`)
    else if (type === 'real') navigate(`/interview/real/${resumeId}`)
  }

  const handleDelete = (e, id) => {
    e.stopPropagation()
    setDeleteConfirm(id)
  }

  const confirmDelete = () => {
    deleteResume(deleteConfirm)
    setDeleteConfirm(null)
    toast.success('자기소개서가 삭제되었습니다')
  }

  const fmt = (iso) => new Date(iso).toLocaleDateString('ko-KR')

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <style>{`
        .rl-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }
        .rl-header h2 { font-size:22px; font-weight:700; color:var(--text-primary); }
        .rl-empty { text-align:center; padding:80px 0; color:var(--text-muted); }
        .rl-empty p { font-size:16px; margin-bottom:20px; }
        .rl-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }
        .rl-card {
          background:#fff; border-radius:var(--radius-lg); border:1px solid var(--border);
          padding:20px; cursor:pointer; position:relative;
          transition:box-shadow .18s, border-color .18s;
        }
        .rl-card:hover { box-shadow:var(--shadow-md); border-color:var(--primary); }
        .rl-card__badge {
          display:inline-block; background:var(--primary-light); color:var(--primary);
          font-size:11px; font-weight:600; padding:2px 8px; border-radius:99px; margin-bottom:10px;
        }
        .rl-card__title { font-size:16px; font-weight:700; margin-bottom:6px; color:var(--text-primary); }
        .rl-card__sub { font-size:13px; color:var(--text-secondary); margin-bottom:12px; }
        .rl-card__meta { display:flex; align-items:center; justify-content:space-between; font-size:12px; color:var(--text-muted); }
        .rl-card__del { padding:4px 10px; border-radius:6px; font-size:12px; color:#ef4444; background:#fff1f1; border:none; cursor:pointer; }
        .rl-card__del:hover { background:#fee2e2; }
        .rl-record-count { display:flex; align-items:center; gap:4px; }

        /* 모달 */
        .modal-bg { position:fixed; inset:0; background:rgba(0,0,0,.45); display:flex; align-items:center; justify-content:center; z-index:1000; }
        .modal-box { background:#fff; border-radius:16px; padding:32px 28px; min-width:320px; max-width:420px; width:90%; box-shadow:0 8px 40px rgba(0,0,0,.18); }
        .modal-title { font-size:18px; font-weight:700; text-align:center; margin-bottom:6px; }
        .modal-sub { font-size:13px; color:var(--text-muted); text-align:center; margin-bottom:24px; }
        .modal-actions { display:flex; flex-direction:column; gap:10px; }
        .modal-btn { padding:13px; border-radius:10px; font-size:15px; font-weight:600; border:none; cursor:pointer; transition:background .15s; }
        .modal-btn-history { background:#f3f4f6; color:#374151; }
        .modal-btn-history:hover { background:#e5e7eb; }
        .modal-btn-practice { background:#dbeafe; color:#1d4ed8; }
        .modal-btn-practice:hover { background:#bfdbfe; }
        .modal-btn-real { background:#d1fae5; color:#065f46; }
        .modal-btn-real:hover { background:#a7f3d0; }
        .modal-btn-cancel { background:#fff; color:#9ca3af; border:1.5px solid #e5e7eb; margin-top:4px; }
        .modal-btn-cancel:hover { background:#f9fafb; }
        .modal-btn-danger { background:#ef4444; color:#fff; }
        .modal-btn-danger:hover { background:#dc2626; }
      `}</style>

      <div className="rl-header">
        <h2>📄 자기소개서 목록</h2>
        <button className="btn btn-primary" onClick={() => navigate('/resume/new')}>
          ✏️ 자기소개서 작성
        </button>
      </div>

      {resumes.length === 0 ? (
        <div className="rl-empty">
          <div style={{ fontSize: 56, marginBottom: 16 }}>📋</div>
          <p>아직 작성된 자기소개서가 없습니다.</p>
          <button className="btn btn-primary" onClick={() => navigate('/resume/new')}>
            첫 자기소개서 작성하기
          </button>
        </div>
      ) : (
        <div className="rl-grid">
          {resumes.map((r) => (
            <div key={r.id} className="rl-card" onClick={() => handleCardClick(r)}>
              <div className="rl-card__badge">{r.companyName || '기업명 미입력'}</div>
              <div className="rl-card__title">{r.title}</div>
              <div className="rl-card__sub">{r.jobTitle || '지원 업무명 미입력'}</div>
              <div className="rl-card__meta">
                <span className="rl-record-count">
                  🗂 면접 기록 {r.interviewRecords?.length || 0}건
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span>{fmt(r.createdAt)}</span>
                  <button className="rl-card__del" onClick={(e) => handleDelete(e, r.id)}>삭제</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 면접 유형 선택 모달 */}
      {actionModal && (
        <div className="modal-bg" onClick={() => setActionModal(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">"{actionModal.title}"</div>
            <div className="modal-sub">어떤 기능을 이용하시겠습니까?</div>
            <div className="modal-actions">
              <button className="modal-btn modal-btn-history" onClick={() => handleAction('history')}>
                🗂 면접 기록 보기
              </button>
              <button className="modal-btn modal-btn-practice" onClick={() => handleAction('practice')}>
                🎓 연습 면접 시작
              </button>
              <button className="modal-btn modal-btn-real" onClick={() => handleAction('real')}>
                🎯 실전 면접 시작
              </button>
              <button className="modal-btn modal-btn-cancel" onClick={() => setActionModal(null)}>
                취소
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 삭제 확인 모달 */}
      {deleteConfirm && (
        <div className="modal-bg" onClick={() => setDeleteConfirm(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">자기소개서 삭제</div>
            <div className="modal-sub">삭제하면 면접 기록도 함께 삭제됩니다.<br />정말 삭제하시겠습니까?</div>
            <div className="modal-actions">
              <button className="modal-btn modal-btn-danger" onClick={confirmDelete}>삭제</button>
              <button className="modal-btn modal-btn-cancel" onClick={() => setDeleteConfirm(null)}>취소</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
