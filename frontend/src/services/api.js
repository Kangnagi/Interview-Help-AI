import axios from 'axios'                                              // HTTP 클라이언트 라이브러리

// Axios 인스턴스 생성 — 모든 API 호출의 기본 설정
const api = axios.create({
  baseURL: '/api/v1',                                                 // 백엔드 API 기본 경로 (Vite proxy로 :8000 연결)
  timeout: 10000,                                                     // 요청 타임아웃 (10초)
})

// ── 로그인 자동 연장 ─────────────────────────────────────────────────
// 토큰은 ACCESS_TOKEN_EXPIRE_MINUTES(60분) 뒤 만료된다. 사용 중이면 만료 REFRESH_BEFORE_MS 전에 /auth/refresh로
// 새 토큰을 받아 이어 쓴다 (면접 도중 60분이 지나 답변 저장이 401로 실패하던 문제).
// '사용 중' = API 요청이 있었거나, 최근 ACTIVE_WINDOW_MS 안에 클릭 · 키 입력 · 스크롤이 있었음.
// 서버는 로그인 후 SESSION_MAX_HOURS(24시간)가 지나면 연장을 거절한다 → 그때는 다시 로그인.
const REFRESH_BEFORE_MS = 15 * 60 * 1000
const ACTIVE_WINDOW_MS = 20 * 60 * 1000
let lastActivity = Date.now()
let refreshing = null                                                 // 진행 중인 연장 요청 (동시에 여러 번 부르지 않게)

function tokenExpiresAt(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.exp * 1000
  } catch {
    return null
  }
}

function refreshIfNeeded() {
  const token = localStorage.getItem('token')
  const exp = token && tokenExpiresAt(token)
  if (!exp || refreshing) return refreshing
  const left = exp - Date.now()
  if (left <= 0 || left > REFRESH_BEFORE_MS) return null              // 이미 만료(→ 401로 처리) 또는 아직 넉넉함
  refreshing = axios.post('/api/v1/auth/refresh', null, { headers: { Authorization: `Bearer ${token}` }, timeout: 10000 })
    .then(({ data }) => {
      if (localStorage.getItem('token') === token) {                  // 그 사이 로그아웃 · 재로그인했으면 덮어쓰지 않음
        localStorage.setItem('token', data.access_token)
        localStorage.setItem('user', JSON.stringify(data.user))
      }
    })
    .catch(() => {})                                                  // 실패해도 지금 토큰은 아직 유효 — 만료되면 401 안내
    .finally(() => { refreshing = null })
  return refreshing
}

if (typeof window !== 'undefined') {
  const markActive = () => { lastActivity = Date.now() }
  ;['pointerdown', 'keydown', 'scroll', 'touchstart'].forEach((e) => window.addEventListener(e, markActive, { passive: true }))
  // 녹음하며 말만 하는 동안처럼 API 요청이 뜸할 때도 연장되게 1분마다 확인
  setInterval(() => { if (Date.now() - lastActivity < ACTIVE_WINDOW_MS) refreshIfNeeded() }, 60 * 1000)
}

// 요청 인터셉터 — 모든 요청 전에 JWT 토큰 자동 첨부 (만료가 가까우면 먼저 연장)
api.interceptors.request.use(async (config) => {
  lastActivity = Date.now()
  await refreshIfNeeded()
  const token = localStorage.getItem('token')                         // 로컬스토리지에 저장된 JWT 토큰
  if (token) config.headers.Authorization = `Bearer ${token}`         // Authorization 헤더 추가
  return config
})

// 응답 인터셉터 — 401(로그인 만료) 처리: 안내와 함께 로그인 페이지로, 다시 로그인하면 보던 화면으로 돌아옴
api.interceptors.response.use(
  (res) => res,                                                       // 성공 응답 통과
  (err) => {
    const url = err.config?.url || ''                                 // 요청한 엔드포인트 경로
    const isAuthRoute = url.includes('/auth/login') || url.includes('/auth/register')   // 인증 관련 엔드포인트인지 확인
    if (err.response?.status === 401 && !isAuthRoute) {               // 401 에러이고 인증 엔드포인트가 아닐 때 (토큰 만료)
      localStorage.removeItem('token')                                // 로컬스토리지 토큰 삭제
      localStorage.removeItem('user')                                 // 사용자 정보도 삭제
      const next = window.location.pathname + window.location.search
      window.location.href = `/login?expired=1${next.startsWith('/login') ? '' : `&next=${encodeURIComponent(next)}`}`
      // 이동하는 동안 페이지가 "이력을 불러오지 못했습니다" 같은 오류를 띄우지 않게 응답을 끝내지 않는다
      return new Promise(() => {})
    }
    return Promise.reject(err)                                         // 에러를 그대로 반환 (호출부에서 처리)
  }
)

// ── Auth API (인증 관련 엔드포인트) ─────────────────────────────────
export const authAPI = {
  register:             (data) => api.post('/auth/register', data),
  login:                (data) => api.post('/auth/login', data),
  requestPasswordReset: (data) => api.post('/auth/password-reset/request', data),
  confirmPasswordReset: (data) => api.post('/auth/password-reset/confirm', data),
}

// ── Interview API (면접 관련 엔드포인트) ────────────────────────────
export const interviewAPI = {
  create:      (data)          => api.post('/interviews', data, { timeout: 90000 }),                 // POST — 면접 생성 + 질문 할당 (Gemini 질문 생성 최대 90초)
  list:        ()              => api.get('/interviews'),                                            // GET — 내 면접 목록
  get:         (id)            => api.get(`/interviews/${id}`),                                      // GET — 면접 상세 조회
  getQuestions:(id)            => api.get(`/interviews/${id}/questions`),                            // GET — 질문 목록 조회
  submitAnswer:       (id, qId, data) => api.post(`/interviews/${id}/questions/${qId}/answer`, data),      // POST — 질문 답변 저장
  followUp:           (id, qId, data) => api.post(`/interviews/${id}/questions/${qId}/follow-up`, data, { timeout: 20000 }), // POST — 방금 답변으로 꼬리 질문 (없으면 question: null)
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

// ── Stats API (통계 대시보드) ────────────────────────────────
export const statsAPI = {
  dashboard: () => api.get('/stats/dashboard'),
}

export default api

