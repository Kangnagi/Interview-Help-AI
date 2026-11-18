import { Link } from 'react-router-dom'
import { SITE } from '@/constants/siteInfo'

/**
 * 사이트 하단 — 약관 링크 · 운영 정보 · AI 결과 안내
 * 로그인 · 가입 화면에는 넣지 않는다 (11/18 사용자 요청 — 가입 화면의 약관은 동의 항목의 '보기' 카드로 본다)
 */
export default function SiteFooter() {
  const links = (
    <nav className="sf-links">
      <Link to="/terms">이용약관</Link>
      <Link to="/privacy" className="sf-strong">개인정보처리방침</Link>
      <Link to="/ai-notice">AI 분석 안내</Link>
      {SITE.contactEmail && <a href={`mailto:${SITE.contactEmail}`}>문의하기</a>}
    </nav>
  )

  return (
    <footer className="sf">
      <style>{CSS}</style>
      <div className="sf-name">{SITE.name}, AI 모의면접 연습 서비스</div>
      {links}
      <div className="sf-info">
        운영: {SITE.team} 팀 ({SITE.school ? `${SITE.school} ` : ''}{SITE.year} 졸업작품)
        {SITE.contactEmail && <>, 문의: <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a></>}
      </div>
      <div className="sf-info">AI 분석 결과는 면접 연습을 위한 참고 자료이며, 실제 채용 결과를 보장하지 않습니다.</div>
      <div className="sf-copy">© {SITE.year} {SITE.team}. All rights reserved.{SITE.version && <span className="sf-ver">{SITE.version}</span>}</div>
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
.sf-ver { margin-left:12px; font-size:11px; opacity:.7; }
@media (max-width:900px) { .sf { padding:16px 16px 20px; } }
`
