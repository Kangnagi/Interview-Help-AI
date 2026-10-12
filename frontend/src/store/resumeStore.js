import { create } from 'zustand'                           // 가벼운 상태 관리 라이브러리
import { resumeAPI } from '@/services/api'

// 자기소개서는 계정(서버)에 저장한다 — 다른 PC · 브라우저에서 같은 이메일로 로그인해도 그대로 보인다.
// (예전엔 브라우저 localStorage에만 저장해서 다른 PC에선 비어 있었고, 같은 PC의 다른 계정에도 보였다)

// 예전 방식으로 이 브라우저에 남아 있는 자기소개서 — 목록 화면에서 '내 계정으로 옮기기'를 안내한다
const LEGACY_KEY = 'ai_interview_resumes'
// 화면에서 남기는 간단한 면접 기록(이전 면접 기록)은 계정별로 이 브라우저에 둔다 — 실제 면접 기록 · 분석은 서버에 있다
const recordsKey = (userId) => `ai_interview_records_${userId}`

const currentUserId = () => {
  try { return JSON.parse(localStorage.getItem('user') || 'null')?.id ?? null } catch { return null }
}

const readJSON = (key, fallback) => {
  try { return JSON.parse(localStorage.getItem(key) || 'null') ?? fallback } catch { return fallback }
}
const writeJSON = (key, value) => {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* 저장 공간 부족 등 — 기록만 못 남김 */ }
}

// 서버 응답(snake_case) → 화면에서 쓰는 모양(camelCase)
const fromServer = (r, records) => ({
  id: r.id,
  title: r.title || '',
  companyName: r.company_name || '',
  jobTitle: r.job_title || '',
  jobDescription: r.job_description || '',
  idealCandidate: r.ideal_candidate || '',
  selfIntroduction: r.self_introduction || '',
  createdAt: r.created_at,
  updatedAt: r.updated_at,
  interviewRecords: records[r.id] || [],
})

const toServer = (d) => ({
  title: (d.title || '').trim(),
  company_name: d.companyName || null,
  job_title: d.jobTitle || null,
  job_description: d.jobDescription || null,
  ideal_candidate: d.idealCandidate || null,
  self_introduction: d.selfIntroduction || null,
})

let loadingPromise = null

export const useResumeStore = create((set, get) => ({
  resumes: [],
  loadedFor: null,        // 어느 계정의 목록을 불러왔는지 — 계정이 바뀌면 다시 불러온다
  loading: false,
  loadError: false,

  // 내 자기소개서 목록 불러오기 (이미 이 계정 것을 불러왔으면 건너뜀)
  load: async (force = false) => {
    const userId = currentUserId()
    if (!userId) return
    if (!force && get().loadedFor === userId) return
    if (loadingPromise) return loadingPromise
    set({ loading: true, loadError: false })
    loadingPromise = resumeAPI.list()
      .then(({ data }) => {
        const records = readJSON(recordsKey(userId), {})
        set({ resumes: data.map((r) => fromServer(r, records)), loadedFor: userId, loading: false })
      })
      .catch(() => set({ loading: false, loadError: true }))
      .finally(() => { loadingPromise = null })
    return loadingPromise
  },

  // 로그아웃 시 비움 (다음 계정에 앞 계정 자기소개서가 보이지 않게)
  reset: () => set({ resumes: [], loadedFor: null, loading: false, loadError: false }),

  // 자기소개서 추가 — 서버에 저장한 뒤 목록 맨 앞에
  addResume: async (resumeData) => {
    const { data } = await resumeAPI.create(toServer(resumeData))
    const created = fromServer(data, {})
    set({ resumes: [created, ...get().resumes] })
    return created
  },

  // 자기소개서 수정
  updateResume: async (id, updates) => {
    const current = get().getResume(id)
    const { data } = await resumeAPI.update(id, toServer({ ...current, ...updates }))
    set({ resumes: get().resumes.map((r) => (r.id === id ? { ...fromServer(data, {}), interviewRecords: r.interviewRecords } : r)) })
  },

  // 자기소개서 삭제 (이미 한 면접 기록 · 분석은 서버에 남는다)
  deleteResume: async (id) => {
    await resumeAPI.remove(id)
    set({ resumes: get().resumes.filter((r) => r.id !== id) })
    const userId = currentUserId()
    if (userId) {
      const records = readJSON(recordsKey(userId), {})
      delete records[id]
      writeJSON(recordsKey(userId), records)
    }
  },

  // 단일 자기소개서 조회
  getResume: (id) => get().resumes.find((r) => r.id === id),

  // 자기소개서에 면접 기록 추가 (이 브라우저 · 이 계정에만 남는 간단한 기록)
  addInterviewRecord: (resumeId, record) => {
    const userId = currentUserId()
    const entry = { id: Date.now().toString(), createdAt: new Date().toISOString(), ...record }
    if (userId) {
      const records = readJSON(recordsKey(userId), {})
      records[resumeId] = [entry, ...(records[resumeId] || [])]
      writeJSON(recordsKey(userId), records)
    }
    set({
      resumes: get().resumes.map((r) =>
        r.id === resumeId ? { ...r, interviewRecords: [entry, ...(r.interviewRecords || [])] } : r
      ),
    })
  },

  // ── 예전(브라우저 저장) 자기소개서 옮기기 ─────────────────────────────
  legacyResumes: () => {
    const list = readJSON(LEGACY_KEY, [])
    return Array.isArray(list) ? list.filter((r) => r && r.id && r.title) : []
  },

  // 이 브라우저에 있던 자기소개서를 지금 로그인한 계정으로 옮긴다 (예전 ID 그대로 → 이미 한 면접 기록과 이어짐)
  importLegacy: async () => {
    const userId = currentUserId()
    const legacy = get().legacyResumes()
    if (!userId || legacy.length === 0) return { imported: 0, skipped: 0 }
    // 서버 길이 제한에 맞춰 자른다 (예전 화면엔 길이 제한이 없던 칸이 있다)
    const cut = (v, n) => (v ? String(v).slice(0, n) : null)
    const payload = legacy.map((r, i) => ({
      id: String(r.id).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 40) || `${Date.now()}${i}`,
      title: cut(String(r.title || '').trim(), 200) || '제목 없음',
      company_name: cut(r.companyName, 200),
      job_title: cut(r.jobTitle, 200),
      job_description: cut(r.jobDescription, 5000),
      ideal_candidate: cut(r.idealCandidate, 3000),
      self_introduction: cut(r.selfIntroduction, 3000),
      created_at: r.createdAt || null,
      updated_at: r.updatedAt || null,
    }))
    const { data } = await resumeAPI.import(payload)
    // 예전 면접 기록(interviewRecords)은 계정별 기록으로 옮긴다
    const records = readJSON(recordsKey(userId), {})
    legacy.forEach((r, i) => {
      const old = r.interviewRecords || r.interviewHistory || []
      if (old.length) records[payload[i].id] = [...(records[payload[i].id] || []), ...old]
    })
    writeJSON(recordsKey(userId), records)
    try { localStorage.removeItem(LEGACY_KEY) } catch { /* 무시 */ }
    await get().load(true)
    return data
  },

  // 옮기지 않고 이 브라우저에서 지우기
  discardLegacy: () => {
    try { localStorage.removeItem(LEGACY_KEY) } catch { /* 무시 */ }
  },
}))
