import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 요청 인터셉터 — 토큰 자동 첨부
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 응답 인터셉터 — 401 처리
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login:    (data) => api.post('/auth/login', data),
}

// ── Interview ─────────────────────────────────────
export const interviewAPI = {
  create:      (data)             => api.post('/interviews', data),
  list:        ()                 => api.get('/interviews'),
  get:         (id)               => api.get(`/interviews/${id}`),
  getQuestions:(id)               => api.get(`/interviews/${id}/questions`),
  submitAnswer:(id, qId, data)    => api.post(`/interviews/${id}/questions/${qId}/answer`, data),
  finish:      (id)               => api.patch(`/interviews/${id}/finish`),
}

// ── Analysis ──────────────────────────────────────
export const analysisAPI = {
  start: (id) => api.post(`/analysis/${id}/start`),
  get:   (id) => api.get(`/analysis/${id}`),
}

export default api
