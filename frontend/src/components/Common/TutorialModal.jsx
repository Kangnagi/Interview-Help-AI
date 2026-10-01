import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const STEPS = [
  {
    icon: '📝',
    title: '자기소개서 등록',
    desc: '면접을 시작하려면 먼저 자기소개서를 등록해야 합니다. 지원 회사, 직무, 자기소개서 내용을 입력하면 AI가 맞춤형 면접 질문을 생성해드립니다.',
    tip: '자기소개서를 자세하게 작성할수록 질문의 질이 높아집니다.',
  },
  {
    icon: '🎙️',
    title: 'AI 면접 진행',
    desc: '연습 면접과 실전 면접 두 가지 모드가 있습니다. 카메라와 마이크를 켜고 실제 면접처럼 답변하면, AI가 음성·자세·시선까지 분석합니다.',
    tip: '밝은 조명과 조용한 환경에서 진행하면 더 정확한 분석이 가능합니다.',
  },
  {
    icon: '📊',
    title: '결과 분석 확인',
    desc: '면접이 끝나면 내용·말하기·자세·시선 4개 항목별 점수와 AI 피드백을 받습니다. 대시보드에서 점수 추이와 역량 균형도 한눈에 볼 수 있습니다.',
    tip: '피드백을 바탕으로 부족한 항목을 집중 연습해보세요.',
  },
]

export default function TutorialModal({ userId, onClose }) {
  const [step, setStep] = useState(0)
  const navigate = useNavigate()
  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  const handleClose = (goToResume = false) => {
    localStorage.setItem(`tutorial_done_${userId}`, '1')
    onClose()
    if (goToResume) navigate('/resume/new')
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.55)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 20,
    }}>
      <div style={{
        background: 'var(--bg-card, #fff)',
        borderRadius: 'var(--radius-lg, 16px)',
        width: '100%', maxWidth: 480,
        padding: '36px 40px',
        boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
        position: 'relative',
      }}>
        {/* 닫기 */}
        <button
          onClick={() => handleClose(false)}
          style={{
            position: 'absolute', top: 16, right: 20,
            background: 'none', border: 'none', fontSize: 20,
            cursor: 'pointer', color: 'var(--text-muted, #9ca3af)',
            lineHeight: 1,
          }}
          aria-label="닫기"
        >✕</button>

        {/* 진행 도트 */}
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginBottom: 28 }}>
          {STEPS.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 24 : 8, height: 8,
              borderRadius: 4,
              background: i === step ? 'var(--primary, #4f6ef7)' : 'var(--border, #e5e7eb)',
              transition: 'all 0.3s',
            }} />
          ))}
        </div>

        {/* 아이콘 */}
        <div style={{ fontSize: 52, textAlign: 'center', marginBottom: 16 }}>{current.icon}</div>

        {/* 제목 */}
        <h2 style={{ fontSize: 20, fontWeight: 700, textAlign: 'center', marginBottom: 12 }}>
          {`Step ${step + 1}. ${current.title}`}
        </h2>

        {/* 설명 */}
        <p style={{
          fontSize: 14, lineHeight: 1.7,
          color: 'var(--text-secondary, #6b7280)',
          textAlign: 'center', marginBottom: 16,
        }}>
          {current.desc}
        </p>

        {/* 팁 */}
        <div style={{
          background: 'rgba(79,110,247,0.07)',
          borderRadius: 'var(--radius-md, 8px)',
          padding: '10px 16px',
          marginBottom: 28,
        }}>
          <p style={{ fontSize: 13, color: 'var(--primary, #4f6ef7)', margin: 0 }}>
            💡 {current.tip}
          </p>
        </div>

        {/* 버튼 */}
        <div style={{ display: 'flex', gap: 10 }}>
          {step > 0 && (
            <button
              className="btn btn-outline"
              style={{ flex: 1 }}
              onClick={() => setStep(s => s - 1)}
            >
              이전
            </button>
          )}
          {!isLast ? (
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              onClick={() => setStep(s => s + 1)}
            >
              다음
            </button>
          ) : (
            <button
              className="btn btn-primary"
              style={{ flex: 1 }}
              onClick={() => handleClose(true)}
            >
              자기소개서 작성하러 가기 →
            </button>
          )}
        </div>

        {step === 0 && (
          <p style={{ textAlign: 'center', marginTop: 14, fontSize: 13, color: 'var(--text-muted, #9ca3af)' }}>
            <button
              onClick={() => handleClose(false)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', textDecoration: 'underline', fontSize: 'inherit' }}
            >
              건너뛰기
            </button>
          </p>
        )}
      </div>
    </div>
  )
}
