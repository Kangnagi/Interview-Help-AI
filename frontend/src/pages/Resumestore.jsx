import { create } from 'zustand'

const STORAGE_KEY = 'ai_interview_resumes'

const loadFromStorage = () => {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
}
const saveToStorage = (resumes) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(resumes)) } catch {}
}

export const useResumeStore = create((set, get) => ({
  resumes: loadFromStorage(),

  addResume: (data) => {
    const r = {
      id: Date.now().toString(),
      title: data.title,
      companyName: data.companyName,
      jobTitle: data.jobTitle,
      jobDescription: data.jobDescription,
      idealCandidate: data.idealCandidate,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      interviewRecords: [],
    }
    const next = [r, ...get().resumes]
    saveToStorage(next)
    set({ resumes: next })
    return r
  },

  updateResume: (id, data) => {
    const next = get().resumes.map((r) =>
      r.id === id ? { ...r, ...data, updatedAt: new Date().toISOString() } : r
    )
    saveToStorage(next)
    set({ resumes: next })
  },

  deleteResume: (id) => {
    const next = get().resumes.filter((r) => r.id !== id)
    saveToStorage(next)
    set({ resumes: next })
  },

  getResume: (id) => get().resumes.find((r) => r.id === id),

  addInterviewRecord: (resumeId, record) => {
    const next = get().resumes.map((r) =>
      r.id === resumeId
        ? {
            ...r,
            interviewRecords: [
              {
                id: Date.now().toString(),
                type: record.type,
                date: new Date().toISOString(),
                duration: record.duration || 0,
                questions: record.questions || [],
                score: record.score || null,
                backendId: record.backendId || null,
              },
              ...r.interviewRecords,
            ],
          }
        : r
    )
    saveToStorage(next)
    set({ resumes: next })
  },
}))
