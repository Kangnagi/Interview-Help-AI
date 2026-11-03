import { create } from 'zustand'                           // 가벼운 상태 관리 라이브러리
import { interviewAPI, analysisAPI } from '@/services/api'  // 면접/분석 API 함수들

export const useInterviewStore = create((set, get) => ({
  interviews: [],                                           // 사용자의 면접 목록
  current: null,                                            // 현재 진행 중인 면접 객체
  questions: [],                                            // 현재 면접의 질문 목록
  currentQuestionIdx: 0,                                    // 현재 질문 인덱스
  analysis: null,                                           // 분석 결과 객체
  loading: false,                                           // API 요청 로딩 상태
  error: null,                                              // 에러 메시지

  // 면접 목록 로드
  fetchInterviews: async () => {
    set({ loading: true })
    try {
      const { data } = await interviewAPI.list()            // 백엔드에서 면접 목록 조회
      set({ interviews: data, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  // 면접 생성
  createInterview: async (title, category) => {
    set({ loading: true, error: null })
    try {
      const { data } = await interviewAPI.create({ title, category })  // 백엔드에서 면접 생성 + 질문 할당
      set({ current: data, loading: false })
      return data
    } catch (err) {
      set({ error: err.response?.data?.detail || '생성 실패', loading: false })
      return null
    }
  },

  // 질문 목록 로드
  loadQuestions: async (interviewId) => {
    const { data } = await interviewAPI.getQuestions(interviewId)       // 질문 목록 조회
    set({ questions: data, currentQuestionIdx: 0 })                   // 상태 업데이트 및 인덱스 초기화
  },

  // 다음 질문으로 이동
  nextQuestion: () => {
    const { currentQuestionIdx, questions } = get()
    if (currentQuestionIdx < questions.length - 1) {
      set({ currentQuestionIdx: currentQuestionIdx + 1 })              // 인덱스 증가 (마지막 질문이면 무시)
    }
  },

  // 답변 저장
  submitAnswer: async (interviewId, questionId, answerText) => {
    await interviewAPI.submitAnswer(interviewId, questionId, { answer_text: answerText })  // 백엔드 저장
    // 로컬 상태의 질문 객체도 업데이트 (UI에 즉시 반영)
    set((state) => ({
      questions: state.questions.map((q) =>
        q.id === questionId ? { ...q, answer_text: answerText } : q
      ),
    }))
  },

  // 면접 종료
  finishInterview: async (interviewId) => {
    await interviewAPI.finish(interviewId)                             // 백엔드 종료 처리
    // 로컬 상태의 면접 목록에서 상태 업데이트
    set((state) => ({
      interviews: state.interviews.map((i) =>
        i.id === interviewId ? { ...i, status: 'completed' } : i
      ),
    }))
  },

  // 분석 시작 (백그라운드 작업)
  startAnalysis: async (interviewId) => {
    await analysisAPI.start(interviewId)                               // 백엔드 분석 시작 (202 응답 후 백그라운드 진행)
  },

  // 분석 결과 조회 (폴링용 — loading 플래그 변경 없음, 결과 있으면 화면 유지)
  fetchAnalysis: async (interviewId) => {
    try {
      const { data } = await analysisAPI.get(interviewId)
      set({ analysis: data })
      return data
    } catch {
      return null
    }
  },

  // 분석 결과만 초기화 (새 면접 분석 화면 진입 시 stale 데이터 제거)
  resetAnalysis: () => set({ analysis: null }),

  // 전체 상태 초기화
  reset: () => set({ current: null, questions: [], currentQuestionIdx: 0, analysis: null }),
}))

