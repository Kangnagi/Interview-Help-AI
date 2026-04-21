import { create } from 'zustand'
import { authAPI } from '@/services/api'

export const useAuthStore = create((set) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  token: localStorage.getItem('token') || null,
  loading: false,
  error: null,

  login: async (email, password) => {
    set({ loading: true, error: null })
    try {
      const { data } = await authAPI.login({ email, password })
      localStorage.setItem('token', data.access_token)
      localStorage.setItem('user', JSON.stringify(data.user))
      set({ token: data.access_token, user: data.user, loading: false, error: null })
      return true
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '로그인 실패. 백엔드 서버를 확인해주세요.'
      set({ error: msg, loading: false })
      return false
    }
  },

  register: async (email, username, password) => {
    set({ loading: true, error: null })
    try {
      await authAPI.register({ email, username, password })
      set({ loading: false })
      return true
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '회원가입 실패. 백엔드 서버를 확인해주세요.'
      set({ error: msg, loading: false })
      return false
    }
  },

  logout: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ user: null, token: null, error: null })
  },
}))
