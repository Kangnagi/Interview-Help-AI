import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { interviewAPI } from '@/services/api'

/**
 * 면접 이력 페이지
 * - 내가 진행한 면접 목록을 최신순으로 표시
 * - 각 행에서 결과 화면으로 진입
 */
export default function HistoryPage() {
  const [items, setItems]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const { data } = await interviewAPI.list()
        if (mounted) setItems(data)
      } catch (e) {
        if (mounted) setError(e.response?.data?.detail || '이력을 불러오지 못했습니다')
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => { mounted = false }
  }, [])

  if (loading) return <div className="page"><p>불러오는 중…</p></div>
  if (error)   return <div className="page"><p className="error">{error}</p></div>

  return (
    <div className="page">
      <h1>면접 이력</h1>
      {items.length === 0 ? (
        <p>아직 진행한 면접이 없습니다.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>제목</th>
              <th>카테고리</th>
              <th>상태</th>
              <th>질문 수</th>
              <th>생성일</th>
              <th>결과</th>
            </tr>
          </thead>
          <tbody>
            {items.map((iv) => (
              <tr key={iv.id}>
                <td>{iv.title}</td>
                <td>{iv.category}</td>
                <td>{iv.status}</td>
                <td>{iv.total_questions}</td>
                <td>{new Date(iv.created_at).toLocaleString('ko-KR')}</td>
                <td>
                  {iv.status === 'completed' ? (
                    <Link to={`/interview/${iv.id}/result`}>보기</Link>
                  ) : (
                    <span>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
