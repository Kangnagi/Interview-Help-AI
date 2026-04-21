import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import Layout from '@/components/Common/Layout'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import InterviewSetupPage from '@/pages/InterviewSetupPage'
import InterviewPage from '@/pages/InterviewPage'
import AnalysisPage from '@/pages/AnalysisPage'
import HistoryPage from '@/pages/HistoryPage'
import ResumeListPage from '@/pages/ResumeListPage'
import ResumeFormPage from '@/pages/ResumeFormPage'
import ResumeHistoryPage from '@/pages/ResumeHistoryPage'
import PracticeInterviewPage from '@/pages/PracticeInterviewPage'
import RealInterviewPage from '@/pages/RealInterviewPage'

function PrivateRoute({ children }) {
  const token = useAuthStore((s) => s.token)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route path="/interview/practice/:resumeId" element={<PrivateRoute><PracticeInterviewPage /></PrivateRoute>} />
      <Route path="/interview/real/:resumeId"     element={<PrivateRoute><RealInterviewPage /></PrivateRoute>} />

      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index                       element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard"            element={<DashboardPage />} />
        <Route path="resume"               element={<ResumeListPage />} />
        <Route path="resume/new"           element={<ResumeFormPage />} />
        <Route path="resume/:id/edit"      element={<ResumeFormPage />} />
        <Route path="resume/:id/history"   element={<ResumeHistoryPage />} />
        <Route path="interview/setup"      element={<InterviewSetupPage />} />
        <Route path="interview/:id"        element={<InterviewPage />} />
        <Route path="interview/:id/result" element={<AnalysisPage />} />
        <Route path="history"              element={<HistoryPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
