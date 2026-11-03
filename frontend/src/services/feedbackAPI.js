import api from '@/services/api'   // 토큰 첨부·401 처리가 설정된 공용 Axios 인스턴스

// ── AI 학습 활용 동의 + 질문별 AI 채점 평가 ─────────────────────────
export const feedbackAPI = {
  getConsent:  ()                  => api.get('/users/me/training-consent'),               // { training_consent: true|false|null }
  setConsent:  (consent)           => api.put('/users/me/training-consent', { consent }),
  listRatings: (interviewId)       => api.get(`/interviews/${interviewId}/ratings`),         // [{ question_id, score_rating, feedback_helpful }]
  rate:        (interviewId, qId, data) => api.put(`/interviews/${interviewId}/questions/${qId}/rating`, data),
}

// 같은 면접 화면의 여러 질문 카드가 평가 목록을 한 번만 불러오도록 면접별로 캐시한다.
const ratingsCache = new Map()
export function loadRatings(interviewId) {
  if (!ratingsCache.has(interviewId)) {
    ratingsCache.set(
      interviewId,
      feedbackAPI.listRatings(interviewId)
        .then((res) => Object.fromEntries(res.data.map((r) => [r.question_id, r])))
        .catch(() => { ratingsCache.delete(interviewId); return {} }),
    )
  }
  return ratingsCache.get(interviewId)
}
