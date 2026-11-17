import { Link, useNavigate } from 'react-router-dom'
import { SITE } from '@/constants/siteInfo'
import SiteFooter from '@/components/Common/SiteFooter'

/**
 * 이용약관 · 개인정보처리방침 · AI 분석 안내 — 로그인 없이도 볼 수 있는 공개 페이지 (가입 화면에서도 연다)
 * 내용은 실제 동작과 맞춰 둔다: 보관 기간(services/vision/scenes.py · services/voice/recordings.py RETENTION_DAYS),
 * 로그인 잠금(core/config.py ACCOUNT_LOCK_*), 회원 탈퇴(services/account.py)를 바꾸면 여기도 고칠 것.
 */
export default function PolicyPage({ doc }) {
  const navigate = useNavigate()
  const page = PAGES[doc] || PAGES.terms
  const goBack = () => (window.history.length > 1 ? navigate(-1) : navigate('/'))

  return (
    <div className="pol-page">
      <style>{CSS}</style>
      <div className="pol-box">
        <div className="pol-top">
          <button type="button" className="pol-back" onClick={goBack}>← 돌아가기</button>
          <nav className="pol-tabs">
            {Object.entries(PAGES).map(([key, p]) => (
              <Link key={key} to={p.path} className={key === doc ? 'on' : ''}>{p.title}</Link>
            ))}
          </nav>
        </div>
        <h1 className="pol-title">{page.title}</h1>
        <p className="pol-sub">{SITE.name} · 시행일 {SITE.effectiveDate}</p>
        {page.body()}
      </div>
      <SiteFooter />
    </div>
  )
}

export const POLICY_PATHS = { terms: '/terms', privacy: '/privacy', ai: '/ai-notice' }

const A = ({ n, title, children }) => (
  <section className="pol-art">
    <h2>{n ? `제${n}조 (${title})` : title}</h2>
    {children}
  </section>
)

const Table = ({ head, rows }) => (
  <div className="pol-table-wrap">
    <table className="pol-table">
      <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
    </table>
  </div>
)

const contact = () => (SITE.contactEmail ? <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a> : '사이트 하단의 문의처')

const PAGES = {
  terms: {
    path: POLICY_PATHS.terms,
    title: '이용약관',
    body: () => (
      <>
        <A n={1} title="목적">
          <p>이 약관은 {SITE.team} 팀(이하 "운영팀")이 제공하는 AI 모의면접 서비스 "{SITE.name}"(이하 "서비스")의 이용 조건과 절차, 운영팀과 이용자의 권리 · 의무를 정합니다.</p>
        </A>
        <A n={2} title="용어">
          <ol>
            <li>"이용자"는 이 약관에 동의하고 서비스를 이용하는 사람입니다.</li>
            <li>"자기소개서 자료"는 이용자가 직접 입력하거나 파일로 올린 이력서 · 자기소개서 · 채용공고 내용입니다.</li>
            <li>"면접 기록"은 면접 중 생성된 질문, 답변(글자로 바꾼 내용과 녹음), 분석 결과를 말합니다.</li>
          </ol>
        </A>
        <A n={3} title="약관의 효력과 변경">
          <ol>
            <li>이 약관은 서비스 화면에 게시하면 효력이 생깁니다.</li>
            <li>약관을 바꿀 때는 시행 7일 전부터(이용자에게 불리한 변경은 30일 전부터) 서비스 화면에 알립니다.</li>
          </ol>
        </A>
        <A n={4} title="회원가입과 계정">
          <ol>
            <li>만 14세 이상이면 이메일로 가입할 수 있습니다. 가입할 때 이용약관과 개인정보 수집 · 이용에 동의해야 합니다.</li>
            <li>이용자는 본인의 정보를 정확하게 입력하고, 비밀번호를 다른 사람에게 알려서는 안 됩니다.</li>
            <li>로그인에 5번 연속 실패하면 15분 동안 로그인이 잠기고, 로그인한 뒤 24시간이 지나면 다시 로그인해야 합니다.</li>
          </ol>
        </A>
        <A n={5} title="제공하는 서비스">
          <ol>
            <li>자기소개서 · 채용공고를 바탕으로 한 맞춤 면접 질문 생성, 답변에 따른 꼬리 질문</li>
            <li>면접 중 시선 · 표정 · 자세의 실시간 분석</li>
            <li>답변 내용 · 음성 분석과 결과 리포트(종합 점수, 영역별 점수, 강점과 개선점)</li>
            <li>자기소개서 없이 질문 3개로 해 보는 '면접 체험', 면접 이력, 점수 기준표</li>
          </ol>
        </A>
        <A n={6} title="이용자의 의무">
          <p>이용자는 다음 행위를 해서는 안 됩니다.</p>
          <ol>
            <li>다른 사람의 자기소개서나 개인정보를 허락 없이 올리는 행위</li>
            <li>다른 사람의 계정을 쓰거나 다른 사람인 것처럼 가입하는 행위</li>
            <li>서버에 과도한 요청을 보내거나 보안을 우회하려는 행위</li>
            <li>서비스를 법령이나 공공질서에 어긋나는 목적으로 쓰는 행위</li>
          </ol>
        </A>
        <A n={7} title="AI 분석 결과의 성격">
          <ol>
            <li>질문, 점수, 피드백은 운영팀이 직접 학습시킨 AI 모델이 자동으로 만든 결과이며, <b>면접 연습을 돕기 위한 참고 자료</b>입니다.</li>
            <li>조명, 카메라 각도, 마이크, 주변 소음에 따라 결과가 달라질 수 있습니다.</li>
            <li>운영팀은 분석 결과가 실제 채용 합격 여부와 일치한다고 보장하지 않습니다.</li>
          </ol>
        </A>
        <A n={8} title="게시물의 권리">
          <ol>
            <li>자기소개서 자료와 답변의 권리는 이용자에게 있습니다.</li>
            <li>운영팀은 이 자료를 서비스 제공(질문 생성, 분석, 결과 표시)에만 씁니다. AI 품질 개선 학습에는 이용자가 따로 동의한 경우에만 씁니다.</li>
          </ol>
        </A>
        <A n={9} title="서비스의 변경과 중단">
          <ol>
            <li>이 서비스는 졸업작품으로 운영되므로 점검이나 운영 종료로 바뀌거나 멈출 수 있습니다.</li>
            <li>운영을 끝낼 때는 30일 전에 화면으로 알리고, 끝난 뒤에는 보관 중인 개인정보를 모두 파기합니다.</li>
          </ol>
        </A>
        <A n={10} title="탈퇴">
          <ol>
            <li>이용자는 [설정 → 데이터 관리 → 회원 탈퇴]에서 비밀번호를 확인한 뒤 언제든 탈퇴할 수 있습니다.</li>
            <li>탈퇴하면 자기소개서 자료와 모든 면접 기록(녹음 · 감점 장면 사진 포함)이 바로 삭제되고, 계정의 이메일 · 이름 · 비밀번호도 지워져 되돌릴 수 없습니다. 같은 이메일로 다시 가입할 수 있습니다.</li>
          </ol>
        </A>
        <A n={11} title="책임의 제한">
          <ol>
            <li>운영팀은 천재지변, 통신 장애, 이용자의 잘못으로 생긴 손해에는 책임지지 않습니다.</li>
            <li>무료로 제공되는 서비스의 이용과 관련하여 운영팀의 고의 또는 중대한 과실이 없는 한 책임지지 않습니다.</li>
          </ol>
        </A>
        <p className="pol-note">부칙: 이 약관은 {SITE.effectiveDate}부터 시행합니다.</p>
      </>
    ),
  },

  privacy: {
    path: POLICY_PATHS.privacy,
    title: '개인정보처리방침',
    body: () => (
      <>
        <A n={1} title="처리하는 개인정보와 보관 기간">
          <Table
            head={['구분', '항목', '목적', '보관 기간']}
            rows={[
              ['회원가입(필수)', '이메일, 이름(표시 이름), 비밀번호', '회원 확인, 로그인, 비밀번호 재설정', '탈퇴할 때까지'],
              ['자기소개서 자료', '자기소개서 · 이력서 · 채용공고 내용', '맞춤 면접 질문 생성', '이용자가 지우거나 탈퇴할 때까지'],
              ['면접 기록', '질문, 답변을 글자로 바꾼 내용, 분석 결과', '결과 리포트와 면접 이력 제공', '이용자가 지우거나 탈퇴할 때까지'],
              ['답변 녹음', '답변 음성 파일', '음성 분석(말 빠르기 · 떨림 등), 다시 듣기', <b key="a">30일 뒤 자동 삭제</b>],
              ['카메라 화면', '면접 중 1초에 2장 찍는 작은 사진(320×240)', '시선 · 표정 · 자세 분석', '분석 뒤 바로 버림'],
              ['감점 장면 사진', '감점된 순간 앞뒤의 사진 몇 장', "결과 화면의 '감점 장면 다시 보기'", <span key="b"><b>30일 뒤 자동 삭제</b> (면접 전에 끄면 저장하지 않음)</span>],
              ['계정 보호 정보', '가입 시각, 로그인 연속 실패 횟수 · 잠금 시각', '계정 보호(연속 실패 시 잠금)', '탈퇴할 때까지'],
            ]}
          />
          <ul>
            <li>비밀번호는 원래 글자로 저장하지 않고 되돌릴 수 없는 방식(argon2)으로 바꿔 저장합니다.</li>
            <li>파일로 올린 이력서 · 자기소개서는 글자만 뽑아 쓰고 파일 자체는 저장하지 않으며, 전화번호 · 이메일 같은 개인정보는 자동으로 빼고 저장합니다.</li>
            <li>면접 영상 전체를 녹화하거나 저장하지 않습니다.</li>
          </ul>
        </A>
        <A n={2} title="AI 학습 활용 (선택 동의)">
          <ol>
            <li>이용자가 동의한 경우에만 면접 답변(글자 · 음성)과 이용자가 남긴 평가를 AI 채점 · 피드백 모델을 개선하는 학습에 씁니다. 학습은 서비스 서버 안에서만 하며 외부로 보내지 않습니다.</li>
            <li>결과 화면에서 언제든 철회할 수 있고, 철회하면 이후 학습에서 빠집니다. 다만 이미 학습이 끝난 모델에서 개별 답변을 빼낼 수는 없습니다.</li>
            <li>동의하지 않아도 모든 기능을 똑같이 쓸 수 있습니다. 감점 장면 사진은 동의 여부와 관계없이 학습에 쓰지 않습니다.</li>
          </ol>
        </A>
        <A n={3} title="제3자 제공">
          <p>운영팀은 이용자의 개인정보를 다른 회사나 기관에 제공하지 않습니다. 질문 생성 · 채점 · 음성 분석은 모두 <b>운영팀 서버 안의 자체 AI 모델</b>로 처리하며, 외부 AI 서비스로 보내지 않습니다.</p>
        </A>
        <A n={4} title="외부 서비스 이용">
          <Table
            head={['서비스', '하는 일', '전달되는 정보']}
            rows={[
              ['Cloudflare', '사이트 접속 연결과 보안(https), 쿠키 없는 방문 통계', '사이트와 주고받는 통신(Cloudflare를 거쳐 전달), 방문한 화면 · 브라우저 종류 같은 방문 통계'],
              ['Google (Gmail)', '비밀번호 재설정 메일 발송', '메일을 받을 이메일 주소'],
            ]}
          />
          <p>두 서비스 모두 서버가 해외에 있을 수 있습니다.</p>
        </A>
        <A n={5} title="파기">
          <ol>
            <li>보관 기간이 지난 녹음과 사진은 서버가 6시간마다 확인해서 자동으로 지웁니다.</li>
            <li>이용자가 [면접 이력]에서 기록을 지우면 그 면접의 분석 결과, 녹음, 감점 장면 사진이 함께 지워집니다.</li>
            <li>탈퇴하면 자기소개서 자료와 모든 면접 기록을 바로 지우고, 계정의 이메일 · 이름 · 비밀번호를 알아볼 수 없는 값으로 바꿉니다(남는 것은 계정 번호와 가입 시각뿐). 서비스 운영이 끝나면 남은 정보를 모두 지웁니다.</li>
          </ol>
        </A>
        <A n={6} title="이용자의 권리">
          <p>이용자는 언제든 자기 정보와 면접 기록을 보거나 지울 수 있고(면접 이력 · 면접 시작 화면), AI 학습 동의를 철회하거나(결과 화면) 탈퇴할 수 있습니다(설정 → 데이터 관리). 화면에서 처리하기 어려우면 {contact()}로 요청해 주세요.</p>
        </A>
        <A n={7} title="안전하게 지키기 위한 조치">
          <ol>
            <li>모든 통신은 https로 암호화합니다.</li>
            <li>비밀번호는 argon2로 바꿔 저장하고, 로그인에 5번 연속 실패하면 15분 동안 잠그며, 로그인한 뒤 24시간이 지나면 다시 로그인하게 합니다.</li>
            <li>녹음과 감점 장면 사진은 본인 확인을 거친 뒤에만 볼 수 있습니다.</li>
            <li>서버는 외부에서 직접 접속할 수 없게 막고 정해진 보안 통로로만 연결하며, 입력한 글에 섞인 위험한 코드는 걸러 냅니다.</li>
          </ol>
        </A>
        <A n={8} title="브라우저 저장소 사용">
          <p>로그인 상태와 화면 설정(튜토리얼을 봤는지, 감점 장면 저장 여부 등)을 이용자 브라우저의 저장소(localStorage)에 보관합니다. 광고나 방문 분석을 위한 쿠키는 쓰지 않으며(방문 통계는 Cloudflare가 쿠키 없이 집계), 로그인 정보는 로그아웃하면 삭제되고 나머지는 브라우저 저장소를 지우면 삭제됩니다.</p>
        </A>
        <A n={9} title="만 14세 미만">
          <p>만 14세 미만 아동의 가입은 받지 않습니다.</p>
        </A>
        <A n={10} title="개인정보 보호책임자">
          <p>책임자: {SITE.privacyOfficer}<br />연락처: {contact()}</p>
        </A>
        <A n={11} title="변경">
          <p>이 방침이 바뀌면 시행 7일 전부터 서비스 화면에 알립니다. 시행일: {SITE.effectiveDate}</p>
        </A>
      </>
    ),
  },

  ai: {
    path: POLICY_PATHS.ai,
    title: 'AI 분석 안내',
    body: () => (
      <>
        <A title="무엇을 분석하나요?">
          <ul>
            <li>답변 내용 — 질문과 관련 있는지, 구체적인지, 논리적인지</li>
            <li>목소리 — 말 빠르기, 떨림, 끊김</li>
            <li>카메라 — 시선, 표정, 자세</li>
          </ul>
        </A>
        <A title="누가 분석하나요?">
          <p>운영팀이 직접 학습시킨 AI 모델(질문 생성, 답변 채점, 음성 분석)이 운영팀 서버 안에서 분석합니다. 외부 AI 서비스로 보내지 않습니다.</p>
        </A>
        <A title="얼마나 정확한가요?">
          <p>점수는 사람 평가와 평균 10점 안팎 차이가 날 수 있고, 조명 · 카메라 · 마이크 환경에 따라서도 달라집니다. 점수보다 '개선점' 내용을 중심으로 참고해 주세요. 점수 산정 방식은 <Link to="/score-guide">점수 기준표</Link>에서 볼 수 있습니다.</p>
        </A>
        <A title="하지 않는 일">
          <ul>
            <li>외모, 성별, 나이 같은 특성으로 평가하지 않습니다.</li>
            <li>결과를 기업이나 다른 사람에게 전달하지 않습니다.</li>
          </ul>
        </A>
      </>
    ),
  },
}

const CSS = `
.pol-page { min-height:100vh; background:var(--bg-page); display:flex; flex-direction:column; align-items:center; padding:32px 16px 0; }
.pol-box { width:100%; max-width:820px; background:#fff; border-radius:var(--radius-lg); box-shadow:var(--shadow-lg); padding:32px 36px; }
.pol-top { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:20px; }
.pol-back { background:none; border:1px solid var(--border); border-radius:8px; padding:6px 12px; font:inherit; font-size:13px; cursor:pointer; color:var(--text-secondary); }
.pol-tabs { display:flex; gap:6px; flex-wrap:wrap; }
.pol-tabs a { font-size:13px; padding:6px 12px; border-radius:999px; color:var(--text-secondary); text-decoration:none; background:#f3f4f6; }
.pol-tabs a.on { background:var(--primary); color:#fff; font-weight:600; }
.pol-title { font-size:24px; font-weight:700; margin-bottom:4px; }
.pol-sub { font-size:13px; color:var(--text-muted, #6B7280); margin-bottom:24px; }
.pol-art { margin-bottom:22px; }
.pol-art h2 { font-size:15px; font-weight:700; margin-bottom:8px; }
.pol-art p, .pol-art li { font-size:14px; line-height:1.75; color:var(--text-secondary); }
.pol-art ol, .pol-art ul { padding-left:20px; display:flex; flex-direction:column; gap:4px; }
.pol-art ol { list-style:decimal; } .pol-art ul { list-style:disc; }
.pol-art a { color:var(--primary); }
.pol-table-wrap { overflow-x:auto; margin-bottom:10px; }
.pol-table { width:100%; border-collapse:collapse; font-size:13px; }
.pol-table th, .pol-table td { border:1px solid var(--border); padding:8px 10px; text-align:left; vertical-align:top; line-height:1.6; }
.pol-table th { background:#f9fafb; font-weight:600; white-space:nowrap; }
.pol-table td:first-child { white-space:nowrap; font-weight:600; color:var(--text-primary); }
.pol-note { font-size:13px; color:var(--text-muted, #6B7280); margin-top:8px; }
@media (max-width:600px) { .pol-box { padding:22px 18px; } .pol-page { padding-top:16px; } }
`
