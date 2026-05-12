import { create } from 'zustand'                   // 가벼운 상태 관리 라이브러리
import { authAPI } from '@/services/api'           // 인증 API 함수들

// Zustand로 전역 상태 관리 (Redux 없이 간단하게)
export const useAuthStore = create((set) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),           // 현재 로그인 사용자 (로컬스토리지에서 복원)
  token: localStorage.getItem('token') || null,                        // JWT 액세스 토큰
  loading: false,                                                      // API 요청 로딩 상태
  error: null,                                                         // 에러 메시지

  // 로그인 함수
  login: async (email, password) => {
    set({ loading: true, error: null })                               // 로딩 시작
    try {
      const { data } = await authAPI.login({ email, password })       // 백엔드 로그인 요청
      localStorage.setItem('token', data.access_token)                // JWT 토큰 저장
      localStorage.setItem('user', JSON.stringify(data.user))         // 사용자 정보 저장
      set({ token: data.access_token, user: data.user, loading: false, error: null })  // 상태 업데이트
      return true
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '로그인 실패. 백엔드 서버를 확인해주세요.'
      set({ error: msg, loading: false })
      return false
    }
  },

  // 회원가입 함수
  register: async (email, username, password) => {
    set({ loading: true, error: null })
    try {
      await authAPI.register({ email, username, password })           // 백엔드 회원가입 요청
      set({ loading: false })
      return true
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '회원가입 실패. 백엔드 서버를 확인해주세요.'
      set({ error: msg, loading: false })
      return false
    }
  },

  // 로그아웃 함수
  logout: () => {
    localStorage.removeItem('token')                                  // 로컬스토리지 정리
    localStorage.removeItem('user')
    set({ user: null, token: null, error: null })                     // 상태 초기화
  },
}))

