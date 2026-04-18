import { create } from 'zustand'
import { interviewAPI, analysisAPI } from '@/services/api'

export const useInterviewStore = create((set, get) => ({
  interviews: [],
  current: null,          // 현재 진행 중인 면접
  questions: [],
  currentQuestionIdx: 0,
  analysis: null,
  loading: false,
  error: null,

  // ─ 목록 로드 ─────────────────────────────────
  fetchInterviews: async () => {
    set({ loading: true })
    try {
      const { data } = await interviewAPI.list()
      set({ interviews: data, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  // ─ 면접 생성 ─────────────────────────────────
  createInterview: async (title, category) => {
    set({ loading: true, error: null })
    try {
      const { data } = await interviewAPI.create({ title, category })
      set({ current: data, loading: false })
      return data
    } catch (err) {
      set({ error: err.response?.data?.detail || '생성 실패', loading: false })
      return null
    }
  },

  // ─ 질문 로드 ─────────────────────────────────
  loadQuestions: async (interviewId) => {
    const { data } = await interviewAPI.getQuestions(interviewId)
    set({ questions: data, currentQuestionIdx: 0 })
  },

  // ─ 다음 질문 ─────────────────────────────────
  nextQuestion: () => {
    const { currentQuestionIdx, questions } = get()
    if (currentQuestionIdx < questions.length - 1) {
      set({ currentQuestionIdx: currentQuestionIdx + 1 })
    }
  },

  // ─ 답변 저장 ─────────────────────────────────
  submitAnswer: async (interviewId, questionId, answerText) => {
    await interviewAPI.submitAnswer(interviewId, questionId, { answer_text: answerText })
    // 로컬 state 업데이트
    set((state) => ({
      questions: state.questions.map((q) =>
        q.id === questionId ? { ...q, answer_text: answerText } : q
      ),
    }))
  },

  // ─ 면접 종료 ─────────────────────────────────
  finishInterview: async (interviewId) => {
    await interviewAPI.finish(interviewId)
    set((state) => ({
      interviews: state.interviews.map((i) =>
        i.id === interviewId ? { ...i, status: 'completed' } : i
      ),
    }))
  },

  // ─ 분석 시작 ─────────────────────────────────
  startAnalysis: async (interviewId) => {
    await analysisAPI.start(interviewId)
  },

  // ─ 분석 조회 ─────────────────────────────────
  fetchAnalysis: async (interviewId) => {
    set({ loading: true })
    try {
      const { data } = await analysisAPI.get(interviewId)
      set({ analysis: data, loading: false })
      return data
    } catch {
      set({ loading: false })
      return null
    }
  },

  reset: () => set({ current: null, questions: [], currentQuestionIdx: 0, analysis: null }),
}))
