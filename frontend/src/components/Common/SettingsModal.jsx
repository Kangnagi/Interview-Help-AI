import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authAPI } from '@/services/api'
import toast from 'react-hot-toast'
import CameraSettingsTab from '@/components/Common/CameraSettingsTab'   // 카메라 미리보기 · 장치 · 밝기 · 대비
import MicSettingsTab from '@/components/Common/MicSettingsTab'         // 마이크 고르기 · 소리 크기 · 녹음해서 들어 보기

const TAB = { CAMERA: 'camera', MIC: 'mic', PROFILE: 'profile', DATA: 'data' }

export default function SettingsModal({ onClose }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [withdrawing, setWithdrawing] = useState(false)
  const [tab, setTab] = useState(TAB.CAMERA)

  // 개인 정보
  const [profileForm, setProfileForm] = useState({ username: user?.username || '', currentPw: '', newPw: '', confirmPw: '' })

  // 삭제 확인
  const [deleteType, setDeleteType] = useState(null) // 'data' | 'account'
  const [deleteInput, setDeleteInput] = useState('')

  const tabs = [
    { id: TAB.CAMERA, icon: '📷', label: '카메라' },
    { id: TAB.MIC,    icon: '🎙️', label: '마이크' },
    { id: TAB.PROFILE, icon: '👤', label: '개인 정보' },
    { id: TAB.DATA,   icon: '🗂', label: '데이터 관리' },
  ]

  const handleSave = (type) => {
    toast.success(`${type} 설정이 저장되었습니다`)
  }

  const handleDataDelete = () => {
    if (deleteInput !== '삭제') return toast.error('"삭제"를 입력해주세요')
    // 이 브라우저에 남은 기록만 지운다 (자기소개서는 계정에 저장 — 목록 화면에서 하나씩 삭제)
    localStorage.removeItem('ai_interview_resumes')
    if (user?.id != null) localStorage.removeItem(`ai_interview_records_${user.id}`)
    toast.success('이 브라우저의 면접 데이터가 삭제되었습니다')
    setDeleteType(null); setDeleteInput('')
  }

  // 회원 탈퇴 — 서버에서 자기소개서 · 면접 기록 · 녹음 · 감점 장면 사진을 모두 지우고 계정 정보를 비운다 (DELETE /auth/me)
  const handleAccountDelete = async () => {
    if (!deleteInput) return toast.error('비밀번호를 입력해주세요')
    setWithdrawing(true)
    try {
      await authAPI.withdraw(deleteInput)
      // 이 브라우저에 남은 이 계정의 기록도 지운다
      localStorage.removeItem('ai_interview_resumes')
      if (user?.id != null) {
        localStorage.removeItem(`ai_interview_records_${user.id}`)
        localStorage.removeItem(`tutorial_done_${user.id}`)
      }
      logout()
      toast.success('회원 탈퇴가 처리되었습니다. 모든 기록이 삭제되었습니다.')
      onClose()
      navigate('/login', { replace: true })
    } catch (err) {
      const d = err.response?.data?.detail
      toast.error(typeof d === 'string' ? d : '탈퇴 처리에 실패했습니다. 잠시 후 다시 시도해주세요.')
    } finally {
      setWithdrawing(false)
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 800 }} onClick={onClose}>
      <style>{`
        .sm-box { background:#fff; border-radius:18px; width:620px; max-height:85vh; overflow:hidden; display:flex; flex-direction:column; box-shadow:0 12px 48px rgba(0,0,0,.22); }
        .sm-head { display:flex; align-items:center; justify-content:space-between; padding:20px 24px; border-bottom:1px solid var(--border); }
        .sm-head-title { font-size:17px; font-weight:700; }
        .sm-body { display:flex; flex:1; overflow:hidden; }
        .sm-sidebar { width:130px; background:#f9fafb; border-right:1px solid var(--border); padding:12px 0; flex-shrink:0; }
        .sm-tab { padding:10px 16px; font-size:13px; cursor:pointer; display:flex; align-items:center; gap:8px; color:var(--text-secondary); transition:all .15s; }
        .sm-tab.active { background:#fff; color:var(--primary); font-weight:600; border-right:2px solid var(--primary); }
        .sm-tab:hover:not(.active) { background:#f3f4f6; }
        .sm-content { flex:1; overflow-y:auto; padding:24px; }
        .sm-group { margin-bottom:24px; }
        .sm-label { font-size:13px; font-weight:600; color:var(--text-secondary); margin-bottom:10px; display:flex; justify-content:space-between; }
        .sm-slider { width:100%; accent-color:var(--primary); height:4px; }
        .sm-toggle { position:relative; display:inline-block; width:44px; height:24px; }
        .sm-toggle input { opacity:0; width:0; height:0; }
        .sm-toggle-slider { position:absolute; inset:0; background:#e5e7eb; border-radius:99px; cursor:pointer; transition:.2s; }
        .sm-toggle input:checked + .sm-toggle-slider { background:var(--primary); }
        .sm-toggle-slider:before { content:''; position:absolute; width:18px; height:18px; background:#fff; border-radius:50%; left:3px; top:3px; transition:.2s; box-shadow:0 1px 4px rgba(0,0,0,.2); }
        .sm-toggle input:checked + .sm-toggle-slider:before { transform:translateX(20px); }
        .sm-input { width:100%; padding:10px 13px; border:1.5px solid var(--border); border-radius:8px; font-size:14px; }
        .sm-input:focus { border-color:var(--primary); outline:none; }
        .sm-danger-btn { background:#fff1f1; color:#ef4444; border:1.5px solid #fecaca; border-radius:8px; padding:10px 18px; font:inherit; font-weight:600; font-size:13px; cursor:pointer; width:100%; transition:background .15s; margin-bottom:10px; }
        .sm-danger-btn:hover { background:#fee2e2; }
        .sm-save-btn { background:var(--primary); color:#fff; border:none; border-radius:8px; padding:10px 24px; font:inherit; font-weight:600; cursor:pointer; font-size:14px; }
        .sm-cam-preview { position:relative; background:#111827; border-radius:10px; overflow:hidden; aspect-ratio:4 / 3; height:200px; margin:0 auto 18px; }
        .sm-cam-preview video { width:100%; height:100%; object-fit:cover; }
        .sm-cam-msg { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; text-align:center; padding:16px; color:rgba(255,255,255,.6); font-size:13px; line-height:1.6; }
        .sm-cam-note { font-size:12px; color:var(--text-muted, #6B7280); line-height:1.6; margin:-8px 0 16px; }
        .sm-mic-meter { position:relative; height:12px; background:#f3f4f6; border-radius:99px; overflow:hidden; }
        .sm-mic-meter > div { height:100%; border-radius:99px; transition:width .08s linear, background .2s; }
        .sm-mic-good { position:absolute; top:0; bottom:0; left:47%; width:40%; border-left:2px dashed rgba(16,185,129,.5); border-right:2px dashed rgba(16,185,129,.5); }
        .sm-mic-hint { font-size:12px; color:var(--text-muted, #6B7280); line-height:1.6; margin-top:8px; }
        .sm-reset-btn:disabled { opacity:.5; cursor:default; }
        .sm-reset-btn { background:#f3f4f6; color:var(--text-secondary); border:none; border-radius:8px; padding:10px 18px; font:inherit; font-size:14px; cursor:pointer; }
        .sm-section-title { font-size:13px; font-weight:700; color:var(--text-primary); margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border); }
      `}</style>

      <div className="sm-box" onClick={(e) => e.stopPropagation()}>
        {/* 헤더 */}
        <div className="sm-head">
          <div className="sm-head-title">⚙️ 설정</div>
          <button onClick={onClose} style={{ background: '#f3f4f6', border: 'none', borderRadius: 8, width: 32, height: 32, cursor: 'pointer', fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
        </div>

        <div className="sm-body">
          {/* 사이드 탭 */}
          <div className="sm-sidebar">
            {tabs.map((t) => (
              <div key={t.id} className={`sm-tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
                {t.icon} {t.label}
              </div>
            ))}
          </div>

          {/* 내용 */}
          <div className="sm-content">
            {/* 카메라 */}
            {tab === TAB.CAMERA && <CameraSettingsTab />}

            {/* 마이크 */}
            {tab === TAB.MIC && <MicSettingsTab />}

            {/* 개인 정보 */}
            {tab === TAB.PROFILE && (
              <>
                <div className="sm-section-title">👤 개인 정보 관리</div>
                <div className="sm-group">
                  <div className="sm-label"><span>현재 아이디</span></div>
                  <input className="sm-input" value={profileForm.username} onChange={(e) => setProfileForm((p) => ({ ...p, username: e.target.value }))} />
                </div>
                <div style={{ background: '#f9fafb', borderRadius: 10, padding: 16, marginBottom: 16 }}>
                  <div className="sm-section-title" style={{ fontSize: 12, borderColor: '#e5e7eb' }}>비밀번호 변경</div>
                  <div className="sm-group" style={{ marginBottom: 12 }}>
                    <div className="sm-label"><span>현재 비밀번호</span></div>
                    <input type="password" className="sm-input" placeholder="현재 비밀번호" value={profileForm.currentPw} onChange={(e) => setProfileForm((p) => ({ ...p, currentPw: e.target.value }))} />
                  </div>
                  <div className="sm-group" style={{ marginBottom: 12 }}>
                    <div className="sm-label"><span>새 비밀번호</span></div>
                    <input type="password" className="sm-input" placeholder="새 비밀번호" value={profileForm.newPw} onChange={(e) => setProfileForm((p) => ({ ...p, newPw: e.target.value }))} />
                  </div>
                  <div className="sm-group" style={{ marginBottom: 0 }}>
                    <div className="sm-label"><span>비밀번호 확인</span></div>
                    <input type="password" className="sm-input" placeholder="새 비밀번호 확인" value={profileForm.confirmPw} onChange={(e) => setProfileForm((p) => ({ ...p, confirmPw: e.target.value }))} />
                  </div>
                </div>
                <button className="sm-save-btn" onClick={() => { if (profileForm.newPw && profileForm.newPw !== profileForm.confirmPw) return toast.error('비밀번호가 일치하지 않습니다'); handleSave('개인 정보') }}>변경 사항 저장</button>
              </>
            )}

            {/* 데이터 관리 */}
            {tab === TAB.DATA && (
              <>
                <div className="sm-section-title">🗂 면접 데이터 관리</div>
                <div style={{ background: '#f9fafb', borderRadius: 10, padding: 16, marginBottom: 16, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                  <b style={{ color: 'var(--text-primary)' }}>저장된 데이터 현황</b><br />
                  자기소개서와 면접 기록 · 분석 결과는 계정에 저장되어 다른 PC에서 로그인해도 그대로 보입니다.<br />
                  아래 초기화는 이 브라우저에 남은 간단한 기록만 지웁니다. 자기소개서 삭제는 '면접 시작' 목록에서 하세요.
                </div>
                <button className="sm-danger-btn" onClick={() => { setDeleteType('data'); setDeleteInput('') }}>
                  🗑 면접 데이터 초기화
                </button>
                <div style={{ height: 1, background: 'var(--border)', margin: '16px 0' }} />
                <div className="sm-section-title" style={{ color: '#ef4444', borderColor: '#fee2e2' }}>⚠️ 위험 구역</div>
                <button className="sm-danger-btn" style={{ border: '1.5px solid #ef4444' }} onClick={() => { setDeleteType('account'); setDeleteInput('') }}>
                  🚪 회원 탈퇴
                </button>

                {/* 확인 모달 */}
                {deleteType && (
                  <div style={{ background: '#fff1f1', border: '1.5px solid #fecaca', borderRadius: 10, padding: 16, marginTop: 16 }}>
                    <div style={{ fontWeight: 700, color: '#ef4444', marginBottom: 8, fontSize: 14 }}>
                      {deleteType === 'data' ? '⚠️ 면접 데이터를 정말 삭제하시겠습니까?' : '⚠️ 정말 탈퇴하시겠습니까?'}
                    </div>
                    <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 12, lineHeight: 1.6 }}>
                      {deleteType === 'data'
                        ? '"삭제"를 입력하세요.'
                        : <>자기소개서, 면접 기록, 녹음, 감점 장면 사진이 <b style={{ color: '#ef4444' }}>모두 삭제되며 되돌릴 수 없습니다.</b><br />확인을 위해 비밀번호를 입력하세요.</>}
                    </div>
                    <input className="sm-input" type={deleteType === 'account' ? 'password' : 'text'} autoComplete={deleteType === 'account' ? 'current-password' : 'off'}
                           maxLength={128} value={deleteInput} onChange={(e) => setDeleteInput(e.target.value)} style={{ marginBottom: 10 }} />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={() => setDeleteType(null)} style={{ flex: 1, background: '#f3f4f6', border: 'none', borderRadius: 8, padding: '9px', font: 'inherit', cursor: 'pointer' }}>취소</button>
                      <button disabled={withdrawing} onClick={deleteType === 'data' ? handleDataDelete : handleAccountDelete} style={{ flex: 1, background: '#ef4444', color: '#fff', border: 'none', borderRadius: 8, padding: '9px', font: 'inherit', fontWeight: 600, cursor: withdrawing ? 'wait' : 'pointer' }}>
                        {deleteType === 'data' ? '삭제' : withdrawing ? '처리 중...' : '탈퇴'}
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
