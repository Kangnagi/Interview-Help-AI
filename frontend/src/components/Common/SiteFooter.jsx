import { Link } from 'react-router-dom'
import { SITE } from '@/constants/siteInfo'

/**
 * 사이트 하단 — 약관 링크 · 운영 정보 · AI 결과 안내
 * compact: 로그인 · 가입 화면처럼 링크만 짧게 보여 줄 때
 */
export default function SiteFooter({ compact = false }) {
  const links = (
    <nav className="sf-links">
      <Link to="/terms">이용약관</Link>
      <Link to="/privacy" className="sf-strong">개인정보처리방침</Link>
      <Link to="/ai-notice">AI 분석 안내</Link>
      {!compact && <Link to="/score-guide">점수 기준표</Link>}
      {!compact && SITE.contactEmail && <a href={`mailto:${SITE.contactEmail}`}>문의하기</a>}
    </nav>
  )

  return (
    <footer className={`sf${compact ? ' sf-compact' : ''}`}>
      <style>{CSS}</style>
      {compact ? links : (
        <>
          <div className="sf-name">{SITE.name} · AI 모의면접 연습 서비스</div>
          {links}
          <div className="sf-info">
            운영: {SITE.team} 팀 ({SITE.school ? `${SITE.school} ` : ''}{SITE.year} 졸업작품)
            {SITE.contactEmail && <> · 문의: <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a></>}
          </div>
          <div className="sf-info">AI 분석 결과는 면접 연습을 위한 참고 자료이며, 실제 채용 결과를 보장하지 않습니다.</div>
          <div className="sf-copy">© {SITE.year} {SITE.team}. All rights reserved.</div>
        </>
      )}
    </footer>
  )
}

const CSS = `
.sf { width:100%; border-top:1px solid var(--border); padding:20px 28px 24px; margin-top:32px; font-size:12px; color:var(--text-muted, #6B7280); line-height:1.7; }
.sf-name { font-weight:600; color:var(--text-secondary); margin-bottom:6px; }
.sf-links { display:flex; flex-wrap:wrap; gap:4px 0; margin-bottom:6px; }
.sf-links a { color:var(--text-secondary); text-decoration:none; }
.sf-links a:hover { text-decoration:underline; }
.sf-links a + a::before { content:'|'; display:inline-block; margin:0 10px; color:var(--border); }
.sf-links .sf-strong { font-weight:700; color:var(--text-primary); }
.sf-info a { color:inherit; }
.sf-copy { margin-top:6px; }
.sf-compact { border-top:none; padding:16px 0 20px; margin-top:0; text-align:center; }
.sf-compact .sf-links { justify-content:center; margin:0; }
@media (max-width:900px) { .sf { padding:16px 16px 20px; } }
`
