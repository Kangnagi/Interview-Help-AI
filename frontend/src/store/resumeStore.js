import { create } from 'zustand'                           // 가벼운 상태 관리 라이브러리

// 로컬스토리지 키 — 자기소개서 데이터 저장 위치
const STORAGE_KEY = 'ai_interview_resumes'

// 로컬스토리지에서 자기소개서 목록 읽기
const loadFromStorage = () => {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')      // JSON 파싱 (없으면 빈 배열)
  } catch {
    return []                                                          // 파싱 실패하면 빈 배열
  }
}

// 로컬스토리지에 자기소개서 목록 저장
const saveToStorage = (resumes) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(resumes))          // 배열을 JSON 문자열로 저장
}

export const useResumeStore = create((set, get) => ({
  resumes: loadFromStorage(),                                          // 초기 상태: 로컬스토리지에서 로드

  // 자기소개서 추가
  addResume: (resumeData) => {
    const newResume = {
      id: Date.now().toString(),                                      // 타임스탬프 기반 고유 ID
      createdAt: new Date().toISOString(),                            // 생성 시각 (ISO 8601)
      updatedAt: new Date().toISOString(),
      interviewHistory: [],                                           // 면접 기록 (초기값: 빈 배열)
      ...resumeData,                                                  // 사용자 입력 데이터 병합
    }
    const resumes = [newResume, ...get().resumes]                     // 최신순으로 앞에 배치
    saveToStorage(resumes)                                            // 로컬스토리지 저장
    set({ resumes })                                                  // 상태 업데이트
    return newResume
  },

  // 자기소개서 수정
  updateResume: (id, updates) => {
    const resumes = get().resumes.map((r) =>
      r.id === id ? { ...r, ...updates, updatedAt: new Date().toISOString() } : r  // 해당 ID만 업데이트
    )
    saveToStorage(resumes)
    set({ resumes })
  },

  // 자기소개서 삭제
  deleteResume: (id) => {
    const resumes = get().resumes.filter((r) => r.id !== id)          // 해당 ID 제외한 배열 반환
    saveToStorage(resumes)
    set({ resumes })
  },

  // 단일 자기소개서 조회
  getResume: (id) => get().resumes.find((r) => r.id === id),         // ID로 검색

  // 자기소개서에 면접 기록 추가
  addInterviewRecord: (resumeId, record) => {
    const resumes = get().resumes.map((r) =>
      r.id === resumeId
        ? {
            ...r,
            interviewHistory: [
              { id: Date.now().toString(), createdAt: new Date().toISOString(), ...record },  // 새 기록 추가
              ...(r.interviewHistory || []),                          // 기존 기록 뒤에 배치
            ],
          }
        : r
    )
    saveToStorage(resumes)
    set({ resumes })
  },
}))

