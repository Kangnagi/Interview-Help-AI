import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { analysisAPI } from '@/services/api';

export default function InterviewResultPage() {
  const { id } = useParams();
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const fetchAnalysis = async () => {
      try {
        const { data } = await analysisAPI.get(id);
        if (mounted) setResult(data);
      } catch (err) {
        if (mounted) {
          setError(err.response?.data?.detail || '분석 결과를 불러오지 못했습니다. 분석이 완료되었는지 확인해주세요.');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchAnalysis();
    return () => { mounted = false; };
  }, [id]);

  if (loading) return <div className="page"><p>분석 결과를 불러오는 중입니다...</p></div>;
  if (error) return <div className="page"><p className="error" style={{ color: 'red' }}>{error}</p><Link to="/history" className="btn btn-outline">목록으로 돌아가기</Link></div>;
  if (!result) return null;

  return (
    <div className="page" style={{ maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <h1>면접 분석 결과 리포트</h1>
        <Link to="/history" className="btn btn-outline">목록으로</Link>
      </div>

      {/* 종합 평가 카드 */}
      <div className="card" style={{ marginBottom: '24px', backgroundColor: '#f8f9fa', padding: '24px', borderRadius: '8px' }}>
        <h2 style={{ marginTop: 0, fontSize: '20px' }}>종합 평가</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginTop: '16px' }}>
          <div style={{ textAlign: 'center', flexShrink: 0 }}>
            <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>총점</p>
            <p style={{ margin: 0, fontSize: '48px', fontWeight: 'bold', color: 'var(--primary)' }}>
              {result.total_score ? Math.round(result.total_score) : '-'}점
            </p>
          </div>
          <div style={{ flexGrow: 1 }}>
            <p style={{ lineHeight: '1.6' }}><strong>AI 면접관의 총평:</strong><br/>{result.feedback_summary}</p>
          </div>
        </div>
      </div>

      {/* 세부 점수 영역 */}
      <div className="card" style={{ marginBottom: '24px', padding: '24px', borderRadius: '8px' }}>
        <h3 style={{ marginTop: 0 }}>답변 역량 분석 (KoBERT)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginTop: '16px', textAlign: 'center' }}>
          <div style={{ padding: '16px', border: '1px solid #eee', borderRadius: '8px' }}>
            <p style={{ margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>내용 적절성</p>
            <p style={{ margin: 0, fontSize: '24px', fontWeight: 'bold' }}>{result.content_score || '-'}점</p>
          </div>
          <div style={{ padding: '16px', border: '1px solid #eee', borderRadius: '8px' }}>
            <p style={{ margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>질문 관련성</p>
            <p style={{ margin: 0, fontSize: '24px', fontWeight: 'bold' }}>{result.relevance_score || '-'}점</p>
          </div>
          <div style={{ padding: '16px', border: '1px solid #eee', borderRadius: '8px' }}>
            <p style={{ margin: '0 0 8px 0', color: 'var(--text-secondary)' }}>명확성</p>
            <p style={{ margin: 0, fontSize: '24px', fontWeight: 'bold' }}>{result.clarity_score || '-'}점</p>
          </div>
        </div>
      </div>

      {/* 질문별 상세 피드백 영역 */}
      <div className="card" style={{ padding: '24px', borderRadius: '8px' }}>
        <h3 style={{ marginTop: 0 }}>상세 피드백 (Gemini)</h3>
        {result.improvements && result.improvements.length > 0 ? (
          <ul style={{ paddingLeft: '20px', lineHeight: '1.8' }}>
            {result.improvements.map((feedback, index) => (
              <li key={index} style={{ marginBottom: '16px' }}>{feedback}</li>
            ))}
          </ul>
        ) : (
          <p style={{ color: 'var(--text-secondary)' }}>아직 상세 피드백이 생성되지 않았습니다.</p>
        )}
      </div>
    </div>
  );
}
