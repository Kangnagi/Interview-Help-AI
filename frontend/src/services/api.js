import axios from 'axios'                                              // HTTP 클라이언트 라이브러리

// Axios 인스턴스 생성 — 모든 API 호출의 기본 설정
const api = axios.create({
  baseURL: '/api/v1',                                                 // 백엔드 API 기본 경로 (Vite proxy로 :8000 연결)
  timeout: 10000,                                                     // 요청 타임아웃 (10초)
})

// 요청 인터셉터 — 모든 요청 전에 JWT 토큰 자동 첨부
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')                         // 로컬스토리지에 저장된 JWT 토큰
  if (token) config.headers.Authorization = `Bearer ${token}`         // Authorization 헤더 추가
  return config
})

// 응답 인터셉터 — 401(권한 없음) 처리 및 로그인 페이지 리다이렉트
api.interceptors.response.use(
  (res) => res,                                                       // 성공 응답 통과
  (err) => {
    const url = err.config?.url || ''                                 // 요청한 엔드포인트 경로
    const isAuthRoute = url.includes('/auth/login') || url.includes('/auth/register')   // 인증 관련 엔드포인트인지 확인
    if (err.response?.status === 401 && !isAuthRoute) {               // 401 에러이고 인증 엔드포인트가 아닐 때 (토큰 만료)
      localStorage.removeItem('token')                                // 로컬스토리지 토큰 삭제
      localStorage.removeItem('user')                                 // 사용자 정보도 삭제
      window.location.href = '/login'                                 // 로그인 페이지로 이동
    }
    return Promise.reject(err)                                         // 에러를 그대로 반환 (호출부에서 처리)
  }
)

// ── Auth API (인증 관련 엔드포인트) ─────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),               // POST /auth/register — 회원가입
  login:    (data) => api.post('/auth/login', data),                 // POST /auth/login — 로그인 (JWT 발급)
}

// ── Interview API (면접 관련 엔드포인트) ────────────────────────────
export const interviewAPI = {
  create:      (data)          => api.post('/interviews', data, { timeout: 90000 }),                 // POST — 면접 생성 + 질문 할당 (Gemini 질문 생성 최대 90초)
  list:        ()              => api.get('/interviews'),                                            // GET — 내 면접 목록
  get:         (id)            => api.get(`/interviews/${id}`),                                      // GET — 면접 상세 조회
  getQuestions:(id)            => api.get(`/interviews/${id}/questions`),                            // GET — 질문 목록 조회
  submitAnswer:       (id, qId, data) => api.post(`/interviews/${id}/questions/${qId}/answer`, data),      // POST — 질문 답변 저장
  getQuestionFeedback:(id, qId)      => api.post(`/interviews/${id}/questions/${qId}/feedback`, null, { timeout: 60000 }), // POST — 즉시 AI 피드백 (Gemini 최대 60초)
  finish:             (id)           => api.patch(`/interviews/${id}/finish`),                             // PATCH — 면접 종료 (분석 가능 상태로)
  delete:             (id)           => api.delete(`/interviews/${id}`),                                   // DELETE — 면접 기록 삭제
}

// ── Analysis API (분석 결과 엔드포인트) ────────────────────────────
export const analysisAPI = {
  start:       (id)   => api.post(`/analysis/${id}/start`),
  get:         (id)   => api.get(`/analysis/${id}`),
  getFeedback: (data) => api.post('/analysis/feedback', data),        // POST — 질문별 즉시 AI 피드백
}

export default api

