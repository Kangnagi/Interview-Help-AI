import { useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { SITE } from '@/constants/siteInfo'
import SiteFooter from '@/components/Common/SiteFooter'

/**
 * 이용약관, 개인정보처리방침, AI 분석 안내: 로그인 없이도 볼 수 있는 공개 페이지
 * 가입 화면에서는 페이지로 넘어가지 않고 PolicyModal(카드)로 같은 내용을 띄운다 (11/18)
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
        <p className="pol-sub">{SITE.name}, 시행일 {SITE.effectiveDate}</p>
        {page.body()}
      </div>
      <SiteFooter />
    </div>
  )
}

export const POLICY_PATHS = { terms: '/terms', privacy: '/privacy', ai: '/ai-notice' }

/**
 * 약관 카드 — 화면 위에 띄워 보여 준다 (가입 화면의 '보기'). 입력하던 내용은 그대로 남는다.
 * onAgree가 있으면 '동의하고 닫기' 버튼을 보여 준다.
 */
export function PolicyModal({ doc, onClose, onAgree }) {
  const page = PAGES[doc] || PAGES.terms
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'                    // 뒤 화면은 스크롤되지 않게
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = prev }
  }, [onClose])

  return (
    <div className="pol-modal-bg" onClick={onClose}>
      <style>{CSS}</style>
      <div className="pol-modal" role="dialog" aria-modal="true" aria-labelledby="pol-modal-title" onClick={(e) => e.stopPropagation()}>
        <div className="pol-modal-head">
          <div>
            <h2 id="pol-modal-title" className="pol-title" style={{ fontSize: 19, marginBottom: 2 }}>{page.title}</h2>
            <p className="pol-sub" style={{ marginBottom: 0 }}>{SITE.name}, 시행일 {SITE.effectiveDate}</p>
          </div>
          <button type="button" className="pol-modal-x" onClick={onClose} aria-label="닫기">✕</button>
        </div>
        <div className="pol-modal-body">{page.body()}</div>
        <div className="pol-modal-foot">
          {onAgree
            ? <><button type="button" className="pol-modal-btn" onClick={onClose}>닫기</button>
                <button type="button" className="pol-modal-btn on" onClick={() => { onAgree(); onClose() }} autoFocus>동의하고 닫기</button></>
            : <button type="button" className="pol-modal-btn on" onClick={onClose} autoFocus>확인</button>}
        </div>
      </div>
    </div>
  )
}

const A = ({ n, title, children }) => (
  <section className="pol-art">
    {/* 조 번호 → 다음 줄 제목 → 다음 줄 내용 (번호 없는 AI 분석 안내는 제목만) */}
    {n ? <h2><span className="pol-art-no">제{n}조</span>{title}</h2> : <h2>{title}</h2>}
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

const contact = () => (SITE.contactEmail ? <a href={`mailto:${SITE.contactEmail}`}>{SITE.contactEmail}</a> : '운영팀 문의 메일(곧 안내 예정)')

const PAGES = {
  terms: {
    path: POLICY_PATHS.terms,
    title: '이용약관',
    body: () => (
      <>
        <A n={1} title="목적">
          <p>이 약관은 {SITE.team} 팀(이하 "운영팀")이 제공하는 AI 모의면접 서비스 "{SITE.name}"(이하 "서비스")를 이용하는 조건과 절차, 그리고 운영팀과 이용자의 권리와 의무를 정합니다.</p>
        </A>
        <A n={2} title="용어">
          <ol>
            <li>"이용자"는 이 약관에 동의하고 서비스를 이용하는 사람을 말합니다.</li>
            <li>"자기소개서 자료"는 이용자가 직접 입력하거나 파일로 올린 이력서, 자기소개서, 채용공고 내용을 말합니다.</li>
            <li>"면접 기록"은 면접에서 나온 질문과 답변(글자로 바뀐 답변과 녹음), 분석 결과를 말합니다.</li>
          </ol>
        </A>
        <A n={3} title="약관의 효력과 변경">
          <ol>
            <li>이 약관은 서비스 화면에 게시한 때부터 효력이 생깁니다.</li>
            <li>약관을 바꿀 때는 시행 7일 전부터 서비스 화면에 알립니다. 이용자에게 불리하게 바뀌는 경우에는 30일 전부터 알립니다.</li>
          </ol>
        </A>
        <A n={4} title="회원가입과 계정">
          <ol>
            <li>만 14세 이상이면 이메일로 가입할 수 있으며, 가입할 때 이용약관과 개인정보 수집 및 이용에 동의해야 합니다.</li>
            <li>이용자는 본인의 정보를 정확하게 입력해야 하고, 비밀번호를 다른 사람에게 알려 주어서는 안 됩니다.</li>
            <li>로그인에 5번 연속 실패하면 15분 동안 로그인할 수 없습니다. 또한 로그인하고 24시간이 지나면 다시 로그인해야 합니다.</li>
          </ol>
        </A>
        <A n={5} title="제공하는 서비스">
          <ol>
            <li>자기소개서와 채용공고를 바탕으로 한 맞춤 면접 질문, 답변에 이어지는 꼬리 질문</li>
            <li>면접 중 시선, 표정, 자세 실시간 분석</li>
            <li>답변 내용과 목소리 분석, 결과 리포트(종합 점수, 영역별 점수, 강점과 개선점)</li>
            <li>자기소개서 없이 질문 3개로 해 보는 면접 체험, 지난 면접 기록 보기</li>
          </ol>
        </A>
        <A n={6} title="이용자의 의무">
          <p>이용자는 다음과 같은 행위를 해서는 안 됩니다.</p>
          <ol>
            <li>다른 사람의 자기소개서나 개인정보를 허락 없이 올리는 행위</li>
            <li>다른 사람의 계정을 쓰거나 다른 사람인 것처럼 가입하는 행위</li>
            <li>서버에 지나치게 많은 요청을 보내거나 보안 장치를 우회하려는 행위</li>
            <li>법령이나 공공질서에 어긋나는 목적으로 서비스를 이용하는 행위</li>
          </ol>
        </A>
        <A n={7} title="AI 분석 결과의 성격">
          <ol>
            <li>질문, 점수, 피드백은 운영팀이 학습시킨 AI 모델이 자동으로 만든 것으로, <b>면접 연습에 참고하기 위한 자료</b>입니다.</li>
            <li>조명, 카메라 각도, 마이크, 주변 소음에 따라 결과가 달라질 수 있습니다.</li>
            <li>운영팀은 분석 결과가 실제 채용 결과와 같다고 보장하지 않습니다.</li>
          </ol>
        </A>
        <A n={8} title="게시물의 권리">
          <ol>
            <li>자기소개서 자료와 답변에 대한 권리는 이용자에게 있습니다.</li>
            <li>운영팀은 이 자료를 질문 생성, 분석, 결과 표시에만 사용합니다. AI 품질을 높이기 위한 학습에는 이용자가 따로 동의한 경우에만 사용합니다.</li>
          </ol>
        </A>
        <A n={9} title="서비스의 변경과 중단">
          <ol>
            <li>이 서비스는 졸업작품으로 운영되므로 점검이나 운영 종료에 따라 내용이 바뀌거나 중단될 수 있습니다.</li>
            <li>운영을 끝낼 때는 30일 전에 서비스 화면으로 알리고, 운영을 끝낸 뒤에는 보관하던 개인정보를 모두 파기합니다.</li>
          </ol>
        </A>
        <A n={10} title="탈퇴">
          <ol>
            <li>이용자는 언제든지 설정의 데이터 관리 메뉴에서 비밀번호를 확인한 뒤 탈퇴할 수 있습니다.</li>
            <li>탈퇴하면 자기소개서 자료와 모든 면접 기록(녹음과 감점 장면 사진 포함)이 바로 삭제되고, 계정의 이메일, 이름, 비밀번호도 지워지며 되돌릴 수 없습니다.</li>
            <li>탈퇴한 뒤에도 같은 이메일로 다시 가입할 수 있습니다.</li>
          </ol>
        </A>
        <A n={11} title="책임의 제한">
          <ol>
            <li>운영팀은 천재지변, 통신 장애, 이용자의 잘못으로 생긴 손해에 대해서는 책임을 지지 않습니다.</li>
            <li>서비스는 무료로 제공되며, 운영팀의 고의나 중대한 과실이 없는 한 서비스 이용으로 생긴 손해에 대해 책임을 지지 않습니다.</li>
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
              ['회원가입(필수)', '이메일, 이름, 비밀번호', '회원 확인, 로그인, 비밀번호 재설정', '탈퇴할 때까지'],
              ['자기소개서 자료', '이력서, 자기소개서, 채용공고 내용', '맞춤 면접 질문 생성', '이용자가 지우거나 탈퇴할 때까지'],
              ['면접 기록', '질문, 글자로 바뀐 답변, 분석 결과', '결과 리포트와 면접 이력 제공', '이용자가 지우거나 탈퇴할 때까지'],
              ['답변 녹음', '답변 음성 파일', "목소리 분석(말 빠르기, 멈춤, '음', '어' 같은 추임새 등)", <b key="a">30일 뒤 자동 삭제</b>],
              ['카메라 화면', '면접 중 1초에 2장씩 찍는 작은 사진(320×240)', '시선, 표정, 자세 분석', '분석이 끝나면 바로 버림'],
              ['감점 장면 사진', '감점된 순간 앞뒤의 사진 몇 장', '결과 화면의 감점 장면 다시 보기', <span key="b"><b>30일 뒤 자동 삭제</b>(면접 전에 끄면 저장하지 않음)</span>],
              ['계정 보호 정보', '가입 시각, 로그인 연속 실패 횟수와 잠금 시각', '계정 보호(연속 실패 시 잠금)', '탈퇴할 때까지'],
            ]}
          />
          <ul>
            <li>비밀번호는 원래 글자 그대로 저장하지 않고, 되돌릴 수 없는 방식(argon2)으로 바꿔서 저장합니다.</li>
            <li>파일로 올린 이력서와 자기소개서는 글자만 뽑아서 쓰고 파일은 저장하지 않습니다. 이때 전화번호, 이메일 같은 개인정보는 자동으로 빼고 저장합니다.</li>
            <li>면접 영상 전체를 녹화하거나 저장하지 않습니다.</li>
          </ul>
        </A>
        <A n={2} title="AI 학습 활용(선택 동의)">
          <ol>
            <li>이용자가 동의한 경우에만 면접 답변(글자와 음성)과 이용자가 남긴 평가를 AI 채점과 피드백 모델을 개선하는 학습에 사용합니다. 학습은 운영팀 서버 안에서만 진행합니다.</li>
            <li>동의는 결과 화면에서 언제든지 철회할 수 있으며, 철회하면 그 뒤의 학습에서는 제외됩니다. 다만 이미 학습이 끝난 모델에서 개별 답변을 빼낼 수는 없습니다.</li>
            <li>동의하지 않아도 모든 기능을 똑같이 이용할 수 있습니다. 감점 장면 사진은 동의 여부와 관계없이 학습에 사용하지 않습니다.</li>
          </ol>
        </A>
        <A n={3} title="제3자 제공">
          <p>운영팀은 이용자의 개인정보를 다른 회사나 기관에 제공하지 않습니다. 질문 생성, 답변 채점, 목소리 분석, 카메라 분석은 모두 <b>운영팀 서버 안에서</b> 처리합니다. 다만 답변을 글자로 바꾸는 음성 인식은 제4조와 같이 브라우저의 기능을 사용합니다.</p>
        </A>
        <A n={4} title="외부 서비스 이용">
          <Table
            head={['서비스', '하는 일', '전달되는 정보']}
            rows={[
              ['브라우저 음성 인식(Chrome은 Google)', '말로 한 답변을 글자로 바꿈', '답변하는 동안의 음성'],
              ['Cloudflare', '사이트 접속 연결, https 보안, 쿠키 없는 방문 통계', '사이트와 주고받는 통신(Cloudflare를 거쳐 전달), 방문한 화면과 브라우저 종류 같은 방문 통계'],
              ['Google(Gmail)', '비밀번호 재설정 메일 발송', '메일을 받을 이메일 주소'],
            ]}
          />
          <ul>
            <li>음성 인식은 이용자의 브라우저가 처리하며, Chrome에서는 음성이 Google 서버로 전달됩니다. 원하지 않으면 답변을 글자로 직접 입력할 수 있습니다.</li>
            <li>위 서비스들은 서버가 해외에 있을 수 있습니다.</li>
          </ul>
        </A>
        <A n={5} title="파기">
          <ol>
            <li>보관 기간이 지난 녹음과 사진은 서버가 6시간마다 확인해서 자동으로 지웁니다.</li>
            <li>이용자가 면접 이력에서 기록을 지우면 그 면접의 분석 결과, 녹음, 감점 장면 사진도 함께 지워집니다.</li>
            <li>탈퇴하면 자기소개서 자료와 모든 면접 기록을 바로 지우고, 계정의 이메일, 이름, 비밀번호는 알아볼 수 없는 값으로 바꿉니다. 이후에는 계정 번호와 가입 시각만 남습니다.</li>
            <li>서비스 운영이 끝나면 남아 있는 정보를 모두 지웁니다.</li>
          </ol>
        </A>
        <A n={6} title="이용자의 권리">
          <p>이용자는 언제든지 자신의 정보와 면접 기록을 보거나 지울 수 있고(면접 이력, 면접 시작 화면), AI 학습 동의를 철회하거나(결과 화면) 탈퇴할 수 있습니다(설정의 데이터 관리). 화면에서 처리하기 어려운 요청은 {contact()}로 보내 주세요.</p>
        </A>
        <A n={7} title="개인정보를 지키기 위한 조치">
          <ol>
            <li>사이트와 주고받는 모든 통신은 https로 암호화합니다.</li>
            <li>비밀번호는 argon2 방식으로 바꿔서 저장합니다. 로그인에 5번 연속 실패하면 15분 동안 잠그고, 로그인하고 24시간이 지나면 다시 로그인하도록 합니다.</li>
            <li>녹음 파일은 웹에서 열 수 없고, 감점 장면 사진은 본인 확인을 거친 뒤에만 볼 수 있습니다.</li>
            <li>서버는 외부에서 직접 접속할 수 없도록 막고 정해진 보안 통로로만 연결합니다. 입력한 글에 섞인 위험한 코드는 걸러 냅니다.</li>
          </ol>
        </A>
        <A n={8} title="브라우저 저장소 사용">
          <p>로그인 상태와 화면 설정(튜토리얼을 봤는지, 감점 장면을 저장할지 등)은 이용자 브라우저의 저장소(localStorage)에 보관합니다. 광고나 방문 분석을 위한 쿠키는 쓰지 않으며, 방문 통계는 Cloudflare가 쿠키 없이 집계합니다. 로그인 정보는 로그아웃하면 지워지고, 나머지는 브라우저 저장소를 비우면 지워집니다.</p>
        </A>
        <A n={9} title="만 14세 미만 아동">
          <p>만 14세 미만 아동은 가입할 수 없습니다.</p>
        </A>
        <A n={10} title="개인정보 보호책임자">
          <p>책임자: {SITE.privacyOfficer}<br />연락처: {contact()}</p>
        </A>
        <A n={11} title="방침의 변경">
          <p>이 방침이 바뀌면 시행 7일 전부터 서비스 화면에 알립니다. 시행일은 {SITE.effectiveDate}입니다.</p>
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
            <li>답변 내용: 질문과 관련이 있는지, 구체적인지, 논리적인지</li>
            <li>목소리: 말 빠르기, 멈춤, '음', '어' 같은 추임새, 전반적인 전달력</li>
            <li>카메라: 시선, 표정, 자세</li>
          </ul>
        </A>
        <A title="누가 분석하나요?">
          <p>질문 생성, 답변 채점, 목소리 분석은 운영팀이 직접 학습시킨 AI 모델이 맡고, 카메라 분석에는 공개된 얼굴 인식 모델(MediaPipe)을 사용합니다. 분석은 모두 운영팀 서버 안에서 이루어지며, 답변을 글자로 바꾸는 음성 인식만 브라우저의 기능을 사용합니다.</p>
        </A>
        <A title="얼마나 정확한가요?">
          <p>점수는 사람이 매긴 점수와 평균 10점 안팎의 차이가 날 수 있고, 조명이나 카메라, 마이크 환경에 따라서도 달라집니다. 점수 자체보다는 개선점에 적힌 내용을 중심으로 참고해 주세요.</p>
        </A>
        <A title="하지 않는 일">
          <ul>
            <li>외모, 성별, 나이 같은 특성으로 평가하지 않습니다.</li>
            <li>분석 결과를 기업이나 다른 사람에게 전달하지 않습니다.</li>
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
.pol-art-no { display:block; font-size:13px; color:var(--primary); margin-bottom:2px; }
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
.pol-modal-bg { position:fixed; inset:0; z-index:1000; background:rgba(15,23,42,.45); display:flex; align-items:center; justify-content:center; padding:20px; }
.pol-modal { width:100%; max-width:640px; max-height:min(80vh, 760px); background:#fff; border-radius:var(--radius-lg); box-shadow:var(--shadow-lg); display:flex; flex-direction:column; overflow:hidden; text-align:left; }
.pol-modal-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; padding:20px 24px 14px; border-bottom:1px solid var(--border); }
.pol-modal-x { background:none; border:none; font-size:18px; line-height:1; padding:4px; cursor:pointer; color:var(--text-muted, #6B7280); }
.pol-modal-body { overflow-y:auto; padding:18px 24px 4px; overscroll-behavior:contain; }
.pol-modal-foot { display:flex; justify-content:flex-end; gap:8px; padding:12px 24px 16px; border-top:1px solid var(--border); }
.pol-modal-btn { font:inherit; font-size:14px; padding:9px 18px; border-radius:var(--radius-md); border:1.5px solid var(--border); background:#fff; cursor:pointer; color:var(--text-secondary); }
.pol-modal-btn.on { background:var(--primary); border-color:var(--primary); color:#fff; font-weight:600; }
@media (max-width:600px) { .pol-modal-head, .pol-modal-body, .pol-modal-foot { padding-left:18px; padding-right:18px; } }
@media (max-width:600px) { .pol-box { padding:22px 18px; } .pol-page { padding-top:16px; } }
`
