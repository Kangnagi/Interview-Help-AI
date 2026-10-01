import api from '@/services/api'   // 토큰 첨부·401 처리가 설정된 공용 Axios 인스턴스

// ── 관리자 검토 (B2) — .env ADMIN_EMAILS 계정만 사용 가능 ─────────────
export const adminAPI = {
  me:     ()                         => api.get('/admin/me'),                                   // { is_admin }
  stats:  ()                         => api.get('/admin/review/stats'),
  queue:  (status = 'pending', offset = 0, limit = 50) => api.get('/admin/review/queue', { params: { status, offset, limit } }),
  item:   (questionId)               => api.get(`/admin/review/items/${questionId}`),
  save:   (questionId, data)         => api.put(`/admin/review/items/${questionId}`, data),
  export: ()                         => api.get('/admin/review/export', { responseType: 'blob', timeout: 60000 }),
}
