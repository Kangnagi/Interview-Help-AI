import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useResumeStore } from '@/store/resumeStore'
import toast from 'react-hot-toast'

export default function ResumeListPage() {
  const navigate = useNavigate()
  const { resumes, deleteResume } = useResumeStore()

  const [actionModal, setActionModal] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)

  const handleCardClick = (resume) => {
    setActionModal({ resumeId: resume.id, title: resume.title })
  }

  const handleAction = (type) => {
    const { resumeId } = actionModal
    setActionModal(null)
    if (type === 'history')       navigate(`/resume/${resumeId}/history`)
    else if (type === 'edit')     navigate(`/resume/${resumeId}/edit`)
    else if (type === 'practice') navigate(`/interview/practice/${resumeId}`)
    else if (type === 'real')     navigate(`/interview/real/${resumeId}`)
  }

  const handleEdit = (e, id) => {
    e.stopPropagation()
    navigate(`/resume/${id}/edit`)
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
        .rl-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
        .rl-header h2 { font-size:22px; font-weight:700; color:var(--text-primary); }

        /* 안내 배너 */
        .rl-guide {
          display:flex; align-items:flex-start; gap:14px;
          background:linear-gradient(135deg,#eff2ff,#e0f2fe);
          border:1.5px solid #c7d7fd; border-radius:14px;
          padding:18px 20px; margin-bottom:24px;
        }
        .rl-guide__icon { font-size:28px; flex-shrink:0; margin-top:2px; }
        .rl-guide__title { font-size:15px; font-weight:700; color:#3730a3; margin-bottom:6px; }
        .rl-guide__steps { display:flex; flex-direction:column; gap:4px; }
        .rl-guide__step {
          display:flex; align-items:center; gap:8px;
          font-size:13px; color:#4338ca;
        }
        .rl-guide__num {
          width:20px; height:20px; border-radius:50%;
          background:#4f6ef7; color:#fff;
          font-size:11px; font-weight:700;
          display:flex; align-items:center; justify-content:center;
          flex-shrink:0;
        }
        .rl-guide__arrow { color:#818cf8; font-size:12px; }

        .rl-empty { text-align:center; padding:60px 0; color:var(--text-muted); }
        .rl-empty p { font-size:16px; margin-bottom:20px; }
        .rl-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }
        .rl-card {
          background:#fff; border-radius:var(--radius-lg); border:1px solid var(--border);
          padding:20px; cursor:pointer; position:relative;
          transition:box-shadow .18s, border-color .18s;
        }
        .rl-card:hover { box-shadow:var(--shadow-md); border-color:var(--primary); }
        .rl-card:hover .rl-card__hint { opacity:1; }
        .rl-card__badge {
          display:inline-block; background:var(--primary-light); color:var(--primary);
          font-size:11px; font-weight:600; padding:2px 8px; border-radius:99px; margin-bottom:10px;
        }
        .rl-card__title { font-size:16px; font-weight:700; margin-bottom:6px; color:var(--text-primary); }
        .rl-card__sub { font-size:13px; color:var(--text-secondary); margin-bottom:12px; }
        .rl-card__hint {
          font-size:12px; color:var(--primary); font-weight:600;
          margin-bottom:10px; opacity:0; transition:opacity .15s;
        }
        .rl-card__meta { display:flex; align-items:center; justify-content:space-between; font-size:12px; color:var(--text-muted); }
        .rl-card__btns { display:flex; align-items:center; gap:6px; }
        .rl-card__edit { padding:4px 10px; border-radius:6px; font-size:12px; color:#4f6ef7; background:#eff2ff; border:none; cursor:pointer; }
        .rl-card__edit:hover { background:#e0e7ff; }
        .rl-card__del  { padding:4px 10px; border-radius:6px; font-size:12px; color:#ef4444; background:#fff1f1; border:none; cursor:pointer; }
        .rl-card__del:hover { background:#fee2e2; }

        /* 모달 */
        .modal-bg { position:fixed; inset:0; background:rgba(0,0,0,.45); display:flex; align-items:center; justify-content:center; z-index:1000; }
        .modal-box { background:#fff; border-radius:16px; padding:28px; min-width:320px; max-width:420px; width:90%; box-shadow:0 8px 40px rgba(0,0,0,.18); }
        .modal-title { font-size:17px; font-weight:700; text-align:center; margin-bottom:4px; }
        .modal-sub { font-size:13px; color:var(--text-muted); text-align:center; margin-bottom:20px; }
        .modal-section-label { font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; letter-spacing:.05em; margin-bottom:8px; }
        .modal-actions { display:flex; flex-direction:column; gap:8px; }
        .modal-divider { height:1px; background:#f3f4f6; margin:6px 0; }
        .modal-btn { padding:12px; border-radius:10px; font-size:14px; font-weight:600; border:none; cursor:pointer; transition:background .15s; text-align:left; display:flex; align-items:center; gap:10px; }
        .modal-btn-edit     { background:#eff2ff; color:#4338ca; }
        .modal-btn-edit:hover { background:#e0e7ff; }
        .modal-btn-history  { background:#f3f4f6; color:#374151; }
        .modal-btn-history:hover { background:#e5e7eb; }
        .modal-btn-practice { background:#dbeafe; color:#1d4ed8; }
        .modal-btn-practice:hover { background:#bfdbfe; }
        .modal-btn-real     { background:#d1fae5; color:#065f46; }
        .modal-btn-real:hover { background:#a7f3d0; }
        .modal-btn-cancel   { background:#fff; color:#9ca3af; border:1.5px solid #e5e7eb; justify-content:center; }
        .modal-btn-cancel:hover { background:#f9fafb; }
        .modal-btn-danger   { background:#ef4444; color:#fff; justify-content:center; }
        .modal-btn-danger:hover { background:#dc2626; }
      `}</style>

      {/* 헤더 */}
      <div className="rl-header">
        <h2>🎤 면접 시작</h2>
        <button className="btn btn-primary" onClick={() => navigate('/resume/new')}>
          ✏️ 자기소개서 작성
        </button>
      </div>

      {/* 이용 안내 배너 */}
      <div className="rl-guide">
        <div className="rl-guide__icon">💡</div>
        <div>
          <div className="rl-guide__title">면접을 시작하려면 자기소개서를 선택하세요</div>
          <div className="rl-guide__steps">
            <div className="rl-guide__step">
              <span className="rl-guide__num">1</span>
              자기소개서가 없다면 오른쪽 상단 <b>자기소개서 작성</b> 버튼을 눌러 먼저 작성해주세요.
            </div>
            <div className="rl-guide__step">
              <span className="rl-guide__num">2</span>
              아래 목록에서 원하는 자기소개서 카드를 <b>클릭</b>하세요.
            </div>
            <div className="rl-guide__step">
              <span className="rl-guide__num">3</span>
              <span><b>연습 면접</b> 또는 <b>실전 면접</b>을 선택하면 바로 시작됩니다.</span>
            </div>
          </div>
        </div>
      </div>

      {/* 자기소개서 없을 때 */}
      {resumes.length === 0 ? (
        <div className="rl-empty">
          <div style={{ fontSize: 56, marginBottom: 16 }}>📋</div>
          <p>작성된 자기소개서가 없습니다.<br />자기소개서를 먼저 작성해주세요.</p>
          <button className="btn btn-primary" onClick={() => navigate('/resume/new')}>
            ✏️ 자기소개서 작성하기
          </button>
        </div>
      ) : (
        <>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
            총 {resumes.length}개의 자기소개서 · 카드를 클릭해서 면접을 시작하세요
          </div>
          <div className="rl-grid">
            {resumes.map((r) => (
              <div key={r.id} className="rl-card" onClick={() => handleCardClick(r)}>
                <div className="rl-card__badge">{r.companyName || '기업명 미입력'}</div>
                <div className="rl-card__title">{r.title}</div>
                <div className="rl-card__sub">{r.jobTitle || '지원 업무명 미입력'}</div>
                <div className="rl-card__hint">👆 클릭해서 면접 시작</div>
                <div className="rl-card__meta">
                  <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    🗂 면접 기록 {r.interviewRecords?.length || 0}건
                  </span>
                  <div className="rl-card__btns">
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{fmt(r.createdAt)}</span>
                    <button className="rl-card__edit" onClick={(e) => handleEdit(e, r.id)}>수정</button>
                    <button className="rl-card__del"  onClick={(e) => handleDelete(e, r.id)}>삭제</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 면접 유형 선택 모달 */}
      {actionModal && (
        <div className="modal-bg" onClick={() => setActionModal(null)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="modal-title">"{actionModal.title}"</div>
            <div className="modal-sub">면접 유형을 선택하세요</div>
            <div className="modal-actions">

              {/* 면접 시작 */}
              <div className="modal-section-label">🎤 면접 시작</div>
              <button className="modal-btn modal-btn-practice" onClick={() => handleAction('practice')}>
                <span>🎓</span>
                <div>
                  <div>연습 면접</div>
                  <div style={{ fontSize: 12, fontWeight: 400, opacity: .75 }}>질문 → 답변 → AI 피드백 반복</div>
                </div>
              </button>
              <button className="modal-btn modal-btn-real" onClick={() => handleAction('real')}>
                <span>🎯</span>
                <div>
                  <div>실전 면접</div>
                  <div style={{ fontSize: 12, fontWeight: 400, opacity: .75 }}>120초 타이머, 실전처럼 진행</div>
                </div>
              </button>

              <div className="modal-divider" />

              {/* 관리 */}
              <div className="modal-section-label">📋 관리</div>
              <button className="modal-btn modal-btn-history" onClick={() => handleAction('history')}>
                <span>🗂</span> 면접 기록 보기
              </button>
              <button className="modal-btn modal-btn-edit" onClick={() => handleAction('edit')}>
                <span>✏️</span> 자기소개서 수정
              </button>

              <div className="modal-divider" />
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
