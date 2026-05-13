import { useState } from 'react'                              // 모달 상태 관리
import { Outlet, NavLink, useNavigate } from 'react-router-dom'   // 라우팅
import { useAuthStore } from '@/store/authStore'                 // 사용자 정보 및 로그아웃
import SettingsModal from '@/components/Common/SettingsModal'     // 설정 모달 (미구현?)
import toast from 'react-hot-toast'                              // 토스트 알림

// 사이드바 네비게이션 메뉴
const NAV_ITEMS = [
  { to: '/dashboard', icon: '🏠', label: '대시보드' },
  { to: '/resume',    icon: '📄', label: '면접 시작' },
  { to: '/history',   icon: '📋', label: '면접 이력' },
]

export default function Layout() {
  const { user, logout } = useAuthStore()                        // 사용자 정보 및 로그아웃 함수
  const navigate = useNavigate()                                 // 페이지 네비게이션
  const [showSettings, setShowSettings] = useState(false)        // 설정 모달 표시 여부

  const handleLogout = () => {
    logout()                                                     // 로그아웃 처리 (토큰/사용자 정보 삭제)
    toast.success('로그아웃 되었습니다')
    navigate('/login')                                           // 로그인 페이지로 이동
  }

  return (
    <div className="layout">
      {/* 사이드바 — 로고, 네비게이션, 사용자 정보 */}
      <aside className="layout__sidebar">
        <div className="sidebar__logo">
          <h1>AI <span>면접</span> 도우미</h1>
          <p style={{ color: 'rgba(255,255,255,.4)', fontSize: 12, marginTop: 4 }}>v0.1.0 · 개발 환경</p>
        </div>

        {/* 네비게이션 메뉴 */}
        <nav className="sidebar__nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}  // 현재 페이지면 active 클래스 추가
            >
              <span className="icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* 사용자 정보 및 로그아웃 */}
        <div style={{ marginTop: 'auto', padding: '16px 20px', borderTop: '1px solid rgba(255,255,255,.08)' }}>
          <button
            onClick={() => setShowSettings(true)}
            style={{ width: '100%', background: 'rgba(255,255,255,.05)', border: '1px solid rgba(255,255,255,.1)', borderRadius: 8, padding: '9px 14px', color: 'rgba(255,255,255,.55)', fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}
          >
            ⚙️ 설정
          </button>
          <p style={{ color: '#fff', fontSize: 14, fontWeight: 500 }}>{user?.username}</p>
          <p style={{ color: 'rgba(255,255,255,.4)', fontSize: 12, marginTop: 2 }}>{user?.email}</p>
          <button
            onClick={handleLogout}
            className="btn btn-outline btn-sm"
            style={{ marginTop: 10, color: 'rgba(255,255,255,.5)', borderColor: 'rgba(255,255,255,.15)', width: '100%' }}
          >
            로그아웃
          </button>
        </div>
      </aside>

      {/* 메인 콘텐츠 영역 */}
      <main className="layout__main">
        <header className="layout__header">
          <h2 style={{ fontSize: 16, fontWeight: 600 }}>AI 면접 도우미</h2>
        </header>
        <div className="layout__content">
          <Outlet />                                              {/* 현재 라우트의 페이지 컴포넌트 렌더링 */}
        </div>
      </main>

      {/* 설정 모달 */}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </div>
  )
}

