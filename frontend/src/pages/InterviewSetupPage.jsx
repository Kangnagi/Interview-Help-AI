import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useInterviewStore } from '@/store/interviewStore'
import toast from 'react-hot-toast'

const CATEGORIES = [
  { value: 'general',    label: '일반 면접',   icon: '💼', desc: '자기소개, 지원동기, 강약점 등' },
  { value: 'technical',  label: '기술 면접',   icon: '💻', desc: '기술 스택, 프로젝트 경험 등' },
  { value: 'behavioral', label: '인성 면접',   icon: '🤝', desc: '팀워크, 갈등 해결, 리더십 등' },
  { value: 'self_intro', label: '자기소개',    icon: '🙋', desc: '1분 자기소개 집중 연습' },
]

export default function InterviewSetupPage() {
  const [title, setTitle]       = useState('')
  const [category, setCategory] = useState('general')
  const { createInterview, loading } = useInterviewStore()
  const navigate = useNavigate()

  const handleStart = async () => {
    if (!title.trim()) return toast.error('면접 제목을 입력해주세요')
    const interview = await createInterview(title, category)
    if (interview) {
      toast.success('면접이 생성되었습니다')
      navigate(`/interview/${interview.id}`)
    }
  }

  return (
    <div style={{ maxWidth: 640, margin: '0 auto' }}>
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>면접 설정</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 28 }}>면접 유형과 제목을 설정해주세요</p>

      {/* 제목 */}
      <div className="card" style={{ marginBottom: 20 }}>
        <h3 style={{ fontWeight: 600, marginBottom: 12 }}>면접 제목</h3>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="예) 네이버 프론트엔드 면접 연습"
          style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-md)',
            border: '1.5px solid var(--border)', fontSize: 14 }}
        />
      </div>

      {/* 카테고리 */}
      <div className="card" style={{ marginBottom: 28 }}>
        <h3 style={{ fontWeight: 600, marginBottom: 16 }}>면접 유형</h3>
        <div className="grid-2">
          {CATEGORIES.map((cat) => (
            <div
              key={cat.value}
              onClick={() => setCategory(cat.value)}
              style={{
                padding: 16,
                border: `2px solid ${category === cat.value ? 'var(--primary)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                background: category === cat.value ? 'var(--primary-light)' : '#fff',
                transition: 'all .15s',
              }}
            >
              <p style={{ fontSize: 24, marginBottom: 6 }}>{cat.icon}</p>
              <p style={{ fontWeight: 600, fontSize: 14 }}>{cat.label}</p>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{cat.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 안내 */}
      <div style={{ background: 'var(--primary-light)', borderRadius: 'var(--radius-md)',
        padding: 16, marginBottom: 24, fontSize: 13, color: '#1D4ED8' }}>
        <p style={{ fontWeight: 600, marginBottom: 4 }}>📌 면접 진행 방식</p>
        <ul style={{ paddingLeft: 16, lineHeight: 1.8 }}>
          <li>카메라와 마이크를 사용하여 실제 면접처럼 진행됩니다</li>
          <li>AI가 실시간으로 표정과 자세를 분석합니다</li>
          <li>면접 종료 후 KoBERT 기반 답변 분석 결과를 제공합니다</li>
        </ul>
      </div>

      <button
        className="btn btn-primary btn-lg w-full"
        onClick={handleStart}
        disabled={loading}
      >
        {loading ? '생성 중...' : '🎤 면접 시작하기'}
      </button>
    </div>
  )
}
