import { create } from 'zustand'

// 로컬스토리지 키
const STORAGE_KEY = 'ai_interview_resumes'

const loadFromStorage = () => {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

const saveToStorage = (resumes) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(resumes))
}

export const useResumeStore = create((set, get) => ({
  resumes: loadFromStorage(),

  // 자기소개서 추가
  addResume: (resumeData) => {
    const newResume = {
      id: Date.now().toString(),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      interviewHistory: [],
      ...resumeData,
    }
    const resumes = [newResume, ...get().resumes]
    saveToStorage(resumes)
    set({ resumes })
    return newResume
  },

  // 자기소개서 수정
  updateResume: (id, updates) => {
    const resumes = get().resumes.map((r) =>
      r.id === id ? { ...r, ...updates, updatedAt: new Date().toISOString() } : r
    )
    saveToStorage(resumes)
    set({ resumes })
  },

  // 자기소개서 삭제
  deleteResume: (id) => {
    const resumes = get().resumes.filter((r) => r.id !== id)
    saveToStorage(resumes)
    set({ resumes })
  },

  // 단일 조회
  getResume: (id) => get().resumes.find((r) => r.id === id),

  // 면접 기록 추가
  addInterviewRecord: (resumeId, record) => {
    const resumes = get().resumes.map((r) =>
      r.id === resumeId
        ? {
            ...r,
            interviewHistory: [
              { id: Date.now().toString(), createdAt: new Date().toISOString(), ...record },
              ...(r.interviewHistory || []),
            ],
          }
        : r
    )
    saveToStorage(resumes)
    set({ resumes })
  },
}))
