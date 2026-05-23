import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { interviewAPI } from '@/services/api'

const CATEGORY_LABEL = {
  general: '일반',
  technical: '기술',
  behavioral: '인성',
  self_intro: '자기소개',
}

const STATUS_CFG = {
  completed:   { label: '완료',    color: '#10b981', bg: 'rgba(16,185,129,.12)' },
  in_progress: { label: '진행 중', color: '#f59e0b', bg: 'rgba(245,158,11,.12)' },
  pending:     { label: '준비 중', color: '#6b7280', bg: 'rgba(107,114,128,.1)' },
  cancelled:   { label: '취소',    color: '#ef4444', bg: 'rgba(239,68,68,.1)' },
}

const FILTERS = [
  { key: 'all',         label: '전체' },
  { key: 'completed',   label: '완료됨' },
  { key: 'in_progress', label: '진행 중' },
]

function scoreColor(s) {
  if (s == null) return 'var(--text-muted)'
  return s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444'
}

function scoreLabel(s) {
  if (s == null) return ''
  return s >= 80 ? '우수' : s >= 60 ? '보통' : '개선 필요'
}

function fmtDate(d) {
  return new Date(d).toLocaleString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [items, setItems]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [filter, setFilter]     = useState('all')
  const [search, setSearch]     = useState('')
  const [deleteId, setDeleteId] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteErr, setDeleteErr] = useState(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const { data } = await interviewAPI.list()
        const sorted = [...data].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        if (mounted) setItems(sorted)
      } catch (e) {
        if (mounted) setError(e.response?.data?.detail || '이력을 불러오지 못했습니다')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  const filtered = useMemo(() => {
    return items
      .filter(iv => filter === 'all' || iv.status?.toLowerCase() === filter)
      .filter(iv => !search.trim() || iv.title.toLowerCase().includes(search.toLowerCase().trim()))
  }, [items, filter, search])

  const stats = useMemo(() => {
    const completed = items.filter(iv => iv.status?.toLowerCase() === 'completed')
    const scored    = completed.filter(iv => iv.total_score != null)
    const avg = scored.length
      ? (scored.reduce((a, b) => a + b.total_score, 0) / scored.length).toFixed(1)
      : null
    const best = scored.length
      ? Math.max(...scored.map(iv => iv.total_score)).toFixed(0)
      : null
    return { total: items.length, completed: completed.length, avg, best }
  }, [items])

  const handleDeleteConfirm = async () => {
    if (!deleteId) return
    setDeleting(true)
    setDeleteErr(null)
    try {
      await interviewAPI.delete(deleteId)
      setItems(prev => prev.filter(iv => iv.id !== deleteId))
      setDeleteId(null)
    } catch (e) {
      setDeleteErr(e.response?.data?.detail || '삭제에 실패했습니다. 다시 시도해 주세요.')
    } finally {
      setDeleting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <div className="spinner" style={{ margin: '0 auto 16px' }} />
        <p style={{ color: 'var(--text-secondary)' }}>면접 이력을 불러오는 중...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 0' }}>
        <p style={{ color: 'var(--danger, #ef4444)' }}>{error}</p>
        <button className="btn btn-outline btn-sm" style={{ marginTop: 12 }} onClick={() => window.location.reload()}>
          다시 시도
        </button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>

      {/* ── 헤더 ── */}
      <div className="flex justify-between items-center" style={{ marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700 }}>면접 이력</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: 4, fontSize: 14 }}>
            지금까지 진행한 모든 면접 기록을 관리합니다
          </p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => navigate('/resume')}>
          + 새 면접 시작
        </button>
      </div>

      {/* ── 통계 카드 ── */}
      {items.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 24 }}>
          {[
            { label: '전체 면접',  value: stats.total,                    icon: '📋', color: 'var(--primary)' },
            { label: '완료된 면접', value: stats.completed,               icon: '✅', color: '#10b981' },
            { label: '평균 점수',  value: stats.avg ? `${stats.avg}점` : '—', icon: '📊', color: '#f59e0b' },
            { label: '최고 점수',  value: stats.best ? `${stats.best}점` : '—', icon: '🏆', color: '#ef4444' },
          ].map(({ label, value, icon, color }) => (
            <div key={label} className="card" style={{ textAlign: 'center', padding: '16px 10px' }}>
              <div style={{ fontSize: 22 }}>{icon}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color, marginTop: 6, lineHeight: 1 }}>{value}</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── 필터 + 검색 ── */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        {/* 필터 탭 */}
        <div style={{ display: 'flex', background: 'rgba(0,0,0,.05)', borderRadius: 10, padding: 3, gap: 2 }}>
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              style={{
                padding: '6px 14px', fontSize: 13, borderRadius: 8, border: 'none', cursor: 'pointer',
                fontWeight: filter === key ? 600 : 400,
                background: filter === key ? '#fff' : 'transparent',
                color: filter === key ? '#111' : 'var(--text-secondary)',
                boxShadow: filter === key ? '0 1px 4px rgba(0,0,0,.12)' : 'none',
                transition: 'all .15s',
              }}
            >
              {label}
              {key !== 'all' && (
                <span style={{ marginLeft: 5, fontSize: 11, opacity: .6 }}>
                  ({items.filter(iv => iv.status?.toLowerCase() === key).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* 검색 */}
        <input
          type="text"
          placeholder="제목으로 검색..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            flex: 1, minWidth: 160, padding: '8px 14px', borderRadius: 10,
            border: '1.5px solid var(--border)', fontSize: 13,
            background: 'transparent', color: 'inherit', outline: 'none',
            fontFamily: 'inherit',
          }}
        />
      </div>

      {/* ── 목록 ── */}
      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '56px 0', color: 'var(--text-secondary)' }}>
          {items.length === 0 ? (
            <>
              <div style={{ fontSize: 48, marginBottom: 14 }}>📋</div>
              <p style={{ fontWeight: 600, fontSize: 16, marginBottom: 6 }}>아직 면접 기록이 없습니다</p>
              <p style={{ fontSize: 13 }}>자기소개서를 등록하고 AI 면접을 시작해보세요</p>
              <button className="btn btn-primary btn-sm" style={{ marginTop: 20 }} onClick={() => navigate('/resume')}>
                면접 시작하기
              </button>
            </>
          ) : (
            <>
              <div style={{ fontSize: 40, marginBottom: 10 }}>🔍</div>
              <p style={{ fontWeight: 500 }}>검색 결과가 없습니다</p>
              <button
                className="btn btn-outline btn-sm"
                style={{ marginTop: 12 }}
                onClick={() => { setSearch(''); setFilter('all') }}
              >
                필터 초기화
              </button>
            </>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map((iv) => {
            const status = iv.status?.toLowerCase() || 'pending'
            const cfg    = STATUS_CFG[status] || STATUS_CFG.pending
            const isCompleted = status === 'completed'
            const hasScore    = iv.total_score != null

            return (
              <div
                key={iv.id}
                className="card"
                style={{ padding: '18px 20px', transition: 'box-shadow .15s' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                  {/* ─ 좌측: 메타 정보 ─ */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
                      <span style={{ fontSize: 15, fontWeight: 600 }}>{iv.title}</span>
                      {/* 카테고리 */}
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 99,
                        background: 'rgba(79,110,247,.1)', color: 'var(--primary)',
                      }}>
                        {CATEGORY_LABEL[iv.category] || iv.category || '일반'}
                      </span>
                      {/* 상태 */}
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 99,
                        background: cfg.bg, color: cfg.color,
                      }}>
                        {cfg.label}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {fmtDate(iv.created_at)}&nbsp;·&nbsp;{iv.total_questions}문항
                    </div>
                  </div>

                  {/* ─ 우측: 점수 + 버튼 ─ */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 }}>
                    {hasScore && (
                      <div style={{ textAlign: 'center', minWidth: 48 }}>
                        <div style={{ fontSize: 24, fontWeight: 800, color: scoreColor(iv.total_score), lineHeight: 1 }}>
                          {Math.round(iv.total_score)}
                        </div>
                        <div style={{ fontSize: 10, color: scoreColor(iv.total_score), marginTop: 2, fontWeight: 600 }}>
                          {scoreLabel(iv.total_score)}
                        </div>
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 6 }}>
                      {isCompleted && (
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => navigate(`/analysis/${iv.id}`)}
                        >
                          분석 결과
                        </button>
                      )}
                      <button
                        onClick={() => { setDeleteId(iv.id); setDeleteErr(null) }}
                        style={{
                          padding: '6px 12px', fontSize: 13, borderRadius: 8,
                          border: '1.5px solid var(--border)', background: 'transparent',
                          color: 'var(--text-secondary)', cursor: 'pointer',
                        }}
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── 삭제 확인 모달 ── */}
      {deleteId && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
        }}>
          <div className="card" style={{ minWidth: 340, maxWidth: 420, padding: '32px 36px', textAlign: 'center' }}>
            <div style={{ fontSize: 40, marginBottom: 14 }}>🗑️</div>
            <h3 style={{ fontWeight: 700, fontSize: 18, marginBottom: 10 }}>면접 기록을 삭제할까요?</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.7, marginBottom: 24 }}>
              이 면접의 질문 기록, 분석 결과가 모두 삭제됩니다.<br />
              삭제한 기록은 복구할 수 없습니다.
            </p>

            {deleteErr && (
              <div style={{
                background: 'rgba(239,68,68,.08)', border: '1px solid rgba(239,68,68,.3)',
                borderRadius: 8, padding: '10px 14px', marginBottom: 16,
                fontSize: 13, color: '#ef4444',
              }}>
                {deleteErr}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button
                className="btn btn-outline"
                onClick={() => { setDeleteId(null); setDeleteErr(null) }}
                disabled={deleting}
              >
                취소
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={deleting}
                style={{
                  background: '#ef4444', color: '#fff', border: 'none',
                  borderRadius: 8, padding: '10px 24px', fontWeight: 700,
                  cursor: deleting ? 'wait' : 'pointer', fontSize: 14,
                  opacity: deleting ? 0.7 : 1,
                }}
              >
                {deleting ? '삭제 중...' : '삭제하기'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
