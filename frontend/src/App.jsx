import { Routes, Route, Navigate } from 'react-router-dom'              // React Router 핵심 컴포넌트
import { useAuthStore } from '@/store/authStore'                     // 로그인 상태 관리 스토어
import Layout from '@/components/Common/Layout'                      // 메인 레이아웃 (사이드바, 헤더)
import LoginPage from '@/pages/LoginPage'                             // 로그인 페이지
import RegisterPage from '@/pages/RegisterPage'                       // 회원가입 페이지
import DashboardPage from '@/pages/DashboardPage'                     // 대시보드 (통계·시작 가이드)
import InterviewPage from '@/pages/InterviewPage'                     // 면접 진행 페이지 (미사용?)
import AnalysisPage from '@/pages/AnalysisPage'                       // 면접 분석 결과 페이지
import HistoryPage from '@/pages/HistoryPage'                         // 면접 이력 페이지 (미사용?)
import ResumeListPage from '@/pages/ResumeListPage'                   // 자기소개서 목록 (면접 시작 선택)
import ResumeFormPage from '@/pages/ResumeFormPage'                   // 자기소개서 작성/수정 페이지
import ResumeHistoryPage from '@/pages/ResumeHistoryPage'             // 자기소개서별 면접 기록 페이지
import PracticeInterviewPage from '@/pages/PracticeInterviewPage'     // 연습 면접 풀스크린 페이지
import RealInterviewPage from '@/pages/RealInterviewPage'             // 실전 면접 풀스크린 페이지 (타이머·제한시간)

// 보호된 라우트 — 로그인한 사용자만 접근 가능 (토큰 확인)
function PrivateRoute({ children }) {
  const token = useAuthStore((s) => s.token)                          // Zustand 스토어에서 토큰 읽기
  return token ? children : <Navigate to="/login" replace />          // 토큰 없으면 로그인 페이지로 리다이렉트
}

export default function App() {
  return (
    <Routes>
      {/* 공개 라우트 (로그인 불필요) */}
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* 풀스크린 면접 라우트 (Layout 밖 — 사이드바/헤더 없음) */}
      <Route path="/interview/practice/:resumeId" element={<PrivateRoute><PracticeInterviewPage /></PrivateRoute>} />
      <Route path="/interview/real/:resumeId"     element={<PrivateRoute><RealInterviewPage /></PrivateRoute>} />

      {/* 인증 필요 라우트 (Layout 안에 중첩) */}
      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index                       element={<Navigate to="/dashboard" replace />} />           {/* / → /dashboard */}
        <Route path="dashboard"            element={<DashboardPage />} />
        <Route path="resume"               element={<ResumeListPage />} />                            {/* 자기소개서 목록 및 면접 선택 */}
        <Route path="resume/new"           element={<ResumeFormPage />} />                            {/* 자기소개서 작성 */}
        <Route path="resume/:id/edit"      element={<ResumeFormPage />} />                            {/* 자기소개서 수정 */}
        <Route path="resume/:id/history"   element={<ResumeHistoryPage />} />                         {/* 자기소개서별 면접 이력 */}
        <Route path="interview/:id"        element={<InterviewPage />} />                             {/* 면접 상세 (미사용?) */}
        <Route path="interview/:id/result" element={<AnalysisPage />} />                              {/* 면접 분석 결과 */}
        <Route path="history"              element={<HistoryPage />} />                               {/* 전체 면접 이력 (미사용?) */}
      </Route>

      {/* 정의되지 않은 경로 → 루트로 리다이렉트 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
