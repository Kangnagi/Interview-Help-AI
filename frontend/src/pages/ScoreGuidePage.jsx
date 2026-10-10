import { useState } from 'react'                                    // 예시 답변 선택 상태

// 면접 점수 기준표 — AI 면접관이 점수를 매기는 순서를 N-S 차트로 보여 준다.
// 기준 출처: 답변 점수 = 채점 모델 학습 기준(backend/training/generate_teacher_scores.py, 관리자 검토 화면 RUBRIC과 같은 구간)
//            음성 점수 = backend/services/voice/librosa_service.py score_speech
//            종합 점수 = backend/routers/analysis.py
// 위 기준이 바뀌면 이 페이지도 같이 고친다.

const BANDS = [
  { range: '0~10',   color: '#D9383A' },
  { range: '11~30',  color: '#E8742A' },
  { range: '31~50',  color: '#C99A06' },
  { range: '51~65',  color: '#7FA51E' },
  { range: '66~80',  color: '#1E9E6A' },
  { range: '81~100', color: '#4F6EF7' },
]
const C = Object.fromEntries(BANDS.map((b) => [b.range, b.color]))

// 예시 답변 — 기준을 설명하려고 만든 답변 (path: 지나가는 차트 칸)
const EXAMPLES = [
  { label: '"잘 모르겠습니다"', q: '팀 프로젝트에서 갈등을 해결한 경험을 말씀해 주세요.', a: '음… 잘 모르겠습니다.',
    band: '0~10', why: '관련된 내용이 없어 첫 판단에서 끝납니다.', path: ['start', 'd1n'] },
  { label: '좋은 말만 나열', q: '팀 프로젝트에서 갈등을 해결한 경험을 말씀해 주세요.',
    a: '저는 소통을 가장 중요하게 생각합니다. 팀원들의 의견을 존중하고, 갈등이 생기면 대화로 풀려고 늘 노력하는 편입니다.',
    band: '31~50', why: '질문과 관련은 있지만 실제로 겪은 사례가 없어 세 번째 판단에서 끝납니다.', path: ['start', 'd1y', 'd2y', 'd3n'] },
  { label: '설계형 · 근거 없음', q: '신규 기능의 우선순위를 정할 때 어떤 기준을 사용하시겠습니까?',
    a: '먼저 요청된 기능을 모두 모으고, 중요한 것부터 순서를 정한 뒤 팀과 공유하겠습니다.',
    band: '51~65', why: "방법은 있지만 무엇을 '중요하다'고 볼지 근거가 없어 설계형 판단에서 끝납니다.", path: ['start', 'd1y', 'd2y', 'd3y', 'd4d', 'd4dn'] },
  { label: '경험 · 행동과 결과', q: '팀 프로젝트에서 갈등을 해결한 경험을 말씀해 주세요.',
    a: '졸업 프로젝트에서 백엔드와 프런트엔드 담당이 API 형식 때문에 계속 부딪혔습니다. 제가 회의를 열어 요청·응답 예시를 문서로 정리하자고 제안했고, 그 뒤로는 같은 문제로 다투는 일이 없었습니다.',
    band: '66~80', why: '상황 · 본인 행동 · 결과가 구체적입니다. 수치나 직무 연결이 없어 마지막 판단에서 66~80점입니다.', path: ['start', 'd1y', 'd2y', 'd3y', 'd4e', 'd4ey', 'd5n'] },
  { label: '경험 · 수치와 직무 연결', q: '팀 프로젝트에서 갈등을 해결한 경험을 말씀해 주세요.',
    a: '졸업 프로젝트에서 API 형식 문제로 갈등이 반복되자, 제가 요청·응답 예시를 문서로 정리하자고 제안했습니다. 연동 오류가 주 8건에서 1건으로 줄었고, 입사 후에도 협업 부서와 인터페이스부터 맞춰 두는 방식으로 일하고 싶습니다.',
    band: '81~100', why: '구체적인 경험에 수치 결과와 직무 연결까지 있어 모든 판단을 통과합니다.', path: ['start', 'd1y', 'd2y', 'd3y', 'd4e', 'd4ey', 'd5y'] },
]

const SPEECH_CHECKS = [
  { q: '말 속도가 초당 3.5~5.5음절을 벗어났는가?', pen: '−최대 20', note: '벗어난 1음절당 15점' },
  { q: '말하는 시간이 답변 시간의 60%보다 적은가?', sub: '침묵이 긴 답변', pen: '−최대 15', note: '모자란 비율 10%당 5점' },
  { q: '2초 이상 멈춘 구간이 있는가?', pen: '−최대 12', note: '한 번에 4점' },
  { q: '억양 변화가 적은가?', sub: '음높이 변화 2.5반음 미만', pen: '−5 또는 −10', note: '1.5반음 미만이면 10점' },
  { q: '목소리 크기가 들쭉날쭉한가?', sub: '크기 변화 12dB 초과', pen: '−5' },
  { q: '"음", "어" 같은 추임새가 100음절당 3번을 넘는가?', pen: '−최대 15', note: '넘은 1번당 2점' },
]

// N-S 차트의 판단 칸 (위 삼각형 + 왼쪽 '아니오' / 오른쪽 '예')
function Cond({ q, sub, left = '아니오', right = '예', node, on, small }) {
  return (
    <div className={`sg-cond${small ? ' sm' : ''}${on?.(node) ? ' on' : ''}`}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <line x1="0" y1="0" x2="50" y2="100" /><line x1="100" y1="0" x2="50" y2="100" />
      </svg>
      <div className="sg-q">{q}{sub && <small>{sub}</small>}</div>
      <span className="sg-lab l">{left}</span><span className="sg-lab r">{right}</span>
    </div>
  )
}

function Result({ score, color, text, end = true }) {
  return (
    <div className="sg-res" style={{ '--c': color }}>
      <div className="sg-score">{score}{end && <span>끝</span>}</div>
      {text && <p>{text}</p>}
    </div>
  )
}

function Cell({ node, on, children }) {
  return <div className={`sg-cell${on?.(node) ? ' on' : ''}`}>{children}</div>
}

const Next = ({ children = '다음 판단' }) => <div className="sg-next">{children}</div>

export default function ScoreGuidePage() {
  const [ex, setEx] = useState(3)                                   // 처음엔 66~80점 예시 경로를 보여 줌
  const sample = EXAMPLES[ex]
  const on = (node) => sample.path.includes(node)                   // 예시 답변이 지나가는 칸 강조

  return (
    <div className="sg">
      <style>{CSS}</style>

      <header>
        <h2 className="sg-title">면접 점수 기준표</h2>
        <p className="sg-lead">AI 면접관이 답변 하나에 점수를 매기는 순서를 N-S 차트로 정리했습니다. 위에서부터 차례로 판단하고, '아니오'가 나오는 곳에서 점수 구간이 정해집니다. 모든 '예'를 통과하면 가장 높은 구간입니다.</p>
      </header>

      {/* ── 1. 답변 점수 ── */}
      <section className="card sg-sec">
        <h3 className="sg-h">1. 답변 점수 <small>질문 하나당 0~100점</small></h3>
        <p className="sg-lead">채점 모델이 학습한 기준과 같은 6개 구간입니다. 구간 안에서는 답변 내용에 따라 정수로 세밀하게 매깁니다.</p>
        <div className="sg-bands">
          {BANDS.map((b) => <span key={b.range} className="sg-band" style={{ '--c': b.color }}><i />{b.range}</span>)}
        </div>

        <div className="sg-scroll">
          <div className="sg-ns">
            <div className={`sg-proc${on('start') ? ' on' : ''}`}>
              <span className="sg-tag">시작</span><b>질문 유형을 먼저 정합니다</b> — 경험형(지난 경험을 묻는 질문) 또는 가정·설계·지식형("어떻게 하시겠습니까", "무엇이 중요한가요")
              <span className="sg-sub">말투(구어체), 문장부호, 음성 인식 오타는 감점하지 않고 내용만 봅니다.</span>
            </div>

            <div className="sg-if">
              <Cond q="질문과 관련된 내용을 말했는가?" sub={`"모르겠습니다"만 말하거나 질문과 다른 이야기는 '아니오'`} />
              <Cell node="d1n" on={on}><Result score="0~10" color={C['0~10']} text="무의미하거나 질문과 무관한 답변" /></Cell>
              <Cell node="d1y" on={on}><Next /></Cell>
            </div>

            <div className="sg-if">
              <Cond q="성의 있게 답했는가?" sub={`"경험이 없습니다", 한 문장 수준, 이름만 말하기는 '아니오'`} />
              <Cell node="d2n" on={on}><Result score="11~30" color={C['11~30']} text="경험·지식이 없다고 솔직히 말한 답변은 학습 계획을 덧붙여도 30점 이하" /></Cell>
              <Cell node="d2y" on={on}><Next /></Cell>
            </div>

            <div className="sg-if">
              <Cond q="질문 의도에 맞게 실제 사례나 구체적인 방법을 들었는가?" sub="좋은 말·용어·경력을 많이 나열해도 사례와 근거가 없으면 '아니오'" />
              <Cell node="d3n" on={on}><Result score="31~50" color={C['31~50']} text="관련은 있지만 일반론·포부뿐인 답변. 아무리 그럴듯해도 50점을 넘지 않음" /></Cell>
              <Cell node="d3y" on={on}><Next>50점 이상 · 유형별 판단</Next></Cell>
            </div>

            <div className="sg-if sg-case">
              <Cond q="질문 유형은?" left="경험형" right="가정·설계·지식형" />
              <div className="sg-cell">
                <div className="sg-if">
                  <Cond small node="d4e" on={on} q="상황 · 본인 행동 · 결과가 구체적인가?" sub="수치가 없어도 됨" />
                  <Cell node="d4en" on={on}><Result score="51~65" color={C['51~65']} text="사례는 있지만 구체성·결과가 약함" /></Cell>
                  <Cell node="d4ey" on={on}><Next /></Cell>
                </div>
              </div>
              <div className="sg-cell">
                <div className="sg-if">
                  <Cond small node="d4d" on={on} q="단계별 방법과 선택 근거가 있는가?" sub="지난 경험의 수치 성과는 요구하지 않음" />
                  <Cell node="d4dn" on={on}><Result score="51~65" color={C['51~65']} text="방법은 있지만 단계·근거가 약함" /></Cell>
                  <Cell node="d4dy" on={on}><Next /></Cell>
                </div>
              </div>
            </div>

            <div className="sg-if">
              <Cond q="수치 결과, 트레이드오프 분석, 직무와의 연결까지 탁월한가?" sub="세 가지가 모두 필요하진 않지만 답변이 한 단계 더 깊어야 '예'" />
              <Cell node="d5n" on={on}><Result score="66~80" color={C['66~80']} text="구체적인 상황·행동·결과 / 단계와 근거가 있는 좋은 답변" /></Cell>
              <Cell node="d5y" on={on}><Result score="81~100" color={C['81~100']} text="위 조건에 더해 수치·비교·직무 연결까지 갖춘 탁월한 답변" /></Cell>
            </div>
          </div>
        </div>

        <div className="sg-examples">
          <h4 className="sg-h4">예시 답변으로 경로 보기</h4>
          <div className="sg-chips" role="group" aria-label="예시 답변">
            {EXAMPLES.map((e, i) => (
              <button key={e.label} type="button" aria-pressed={i === ex} onClick={() => setEx(i)}>{e.label}</button>
            ))}
          </div>
          <div className="sg-quote" aria-live="polite">
            <div className="sg-qq">Q. {sample.q}</div>
            <p>“{sample.a}”</p>
            <p className="sg-why"><b style={{ color: C[sample.band] }}>{sample.band}점</b> — {sample.why}</p>
          </div>
          <p className="sg-note">예시는 기준을 설명하려고 만든 답변입니다. 실제 점수는 이 기준으로 학습한 채점 모델이 매기므로 구간 경계 근처에서는 몇 점 차이가 날 수 있습니다.</p>
        </div>
      </section>

      {/* ── 2. 음성 점수 ── */}
      <section className="card sg-sec">
        <h3 className="sg-h">2. 음성 점수 <small>녹음 분석 · 100점에서 감점</small></h3>
        <p className="sg-lead">답변 녹음을 분석해 아래 여섯 가지를 차례로 확인합니다. 해당하면 감점하고, 결과 화면의 음성 코칭에는 가장 크게 감점된 항목 하나가 나옵니다.</p>
        <div className="sg-scroll">
          <div className="sg-ns">
            <div className="sg-proc"><span className="sg-tag">시작</span><b>음성 점수 = 100점</b><span className="sg-sub">녹음이 없거나 분석할 수 없으면 기본 80점</span></div>
            {SPEECH_CHECKS.map((s) => (
              <div className="sg-if" key={s.q}>
                <Cond q={s.q} sub={s.sub} />
                <div className="sg-cell"><Next>감점 없음</Next></div>
                <div className="sg-cell"><Result score={s.pen} color={C['11~30']} text={s.note} end={false} /></div>
              </div>
            ))}
            <div className="sg-proc"><span className="sg-tag">끝</span><b>음성 점수 = 100 − 감점 합계</b><span className="sg-sub">아무리 감점이 많아도 30점 아래로는 내려가지 않습니다.</span></div>
          </div>
        </div>
      </section>

      {/* ── 3. 종합 점수 ── */}
      <section className="card sg-sec">
        <h3 className="sg-h">3. 종합 점수 <small>결과 화면 맨 위 점수</small></h3>
        <p className="sg-lead">질문마다 매긴 점수를 여섯 개 항목으로 모은 뒤 평균을 냅니다.</p>
        <div className="sg-scroll">
          <div className="sg-ns">
            <div className="sg-proc"><span className="sg-tag">1</span><b>질문마다 답변 점수를 매깁니다</b> (1번 차트)<span className="sg-sub">답변이 10자 미만이거나 세 단어 미만이면 그 질문은 30점을 넘지 않습니다.</span></div>
            <div className="sg-proc"><span className="sg-tag">2</span><b>내용 · 관련성 · 명확성</b> = 질문별 답변 점수의 평균<span className="sg-pill">지금은 세 항목이 같은 값</span><span className="sg-sub">채점 모델이 답변마다 점수를 하나만 내기 때문입니다.</span></div>
            <div className="sg-proc"><span className="sg-tag">3</span><b>음성</b> = 질문별 음성 점수의 평균 (2번 차트)</div>
            <div className="sg-if">
              <Cond q="카메라 영상 분석 결과가 있는가?" sub="자세 · 시선" />
              <div className="sg-cell"><Result score="추정값" color={C['31~50']} end={false} text="자세 = 답변 평균 × 0.9 + 10 / 시선 = 답변 평균 × 0.85 + 12 (최대 100)" /></div>
              <div className="sg-cell"><Result score="실측값" color={C['66~80']} end={false} text="영상 분석이 잰 자세 · 시선 점수" /></div>
            </div>
            <div className="sg-proc"><span className="sg-tag">끝</span><b>종합 점수 = 내용 · 관련성 · 명확성 · 음성 · 자세 · 시선의 평균</b></div>
          </div>
        </div>
        <p className="sg-calc">예) 답변 평균 <b>70</b> · 음성 <b>85</b> · 영상 없음 → 자세 70×0.9+10 = <b>73</b>, 시선 70×0.85+12 = <b>71.5</b><br />
          종합 = (70 + 70 + 70 + 85 + 73 + 71.5) ÷ 6 = <b>73.3점</b></p>
      </section>
    </div>
  )
}

const CSS = `
.sg { max-width: 880px; margin: 0 auto; display: grid; gap: 20px; }
.sg-title { font-size: 22px; font-weight: 700; }
.sg-lead { color: var(--text-secondary); font-size: 14px; line-height: 1.7; margin-top: 6px; max-width: 68ch; }
.sg-sec { display: grid; gap: 14px; min-width: 0; }
.sg-h { font-size: 17px; font-weight: 700; }
.sg-h small { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-left: 8px; }
.sg-h4 { font-size: 14px; font-weight: 600; }
.sg-bands { display: flex; flex-wrap: wrap; gap: 8px; }
.sg-band { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; padding: 5px 10px; border-radius: 999px;
           border: 1.5px solid var(--c); color: var(--c); font-variant-numeric: tabular-nums; }
.sg-band i { width: 8px; height: 8px; border-radius: 50%; background: var(--c); }

.sg-scroll { overflow-x: auto; }
.sg-ns { min-width: 600px; border: 2px solid var(--text-primary); background: var(--bg-card); }
.sg-ns > * + * { border-top: 2px solid var(--text-primary); }
.sg-proc { padding: 12px 16px; font-size: 14px; line-height: 1.6; }
.sg-sub { display: block; color: var(--text-secondary); font-size: 13px; }
.sg-tag { font-size: 11px; font-weight: 700; letter-spacing: .05em; color: var(--text-secondary); margin-right: 8px; }
.sg-pill { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 999px; background: var(--primary-light); color: var(--primary); margin-left: 6px; }

.sg-if { display: grid; grid-template-columns: 1fr 1fr; }
.sg-cond { grid-column: 1 / -1; position: relative; min-height: 104px; padding: 12px 22% 34px; text-align: center; border-bottom: 2px solid var(--text-primary); }
.sg-cond.sm { min-height: 96px; padding-inline: 18%; }
.sg-cond svg { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.sg-cond line { stroke: var(--text-primary); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.sg-q { position: relative; font-size: 15px; font-weight: 600; line-height: 1.45; text-wrap: balance; }
.sg-cond.sm .sg-q { font-size: 14px; }
.sg-q small { display: block; font-size: 12.5px; font-weight: 400; color: var(--text-secondary); margin-top: 2px; }
.sg-lab { position: absolute; bottom: 8px; font-size: 12.5px; font-weight: 600; color: var(--text-secondary); }
.sg-lab.l { left: 14px; } .sg-lab.r { right: 14px; }
.sg-cell { padding: 12px 14px; min-width: 0; }
.sg-cell + .sg-cell { border-left: 2px solid var(--text-primary); }
.sg-case > .sg-cell { padding: 0; }
.sg-next { color: var(--text-secondary); font-size: 13px; display: flex; align-items: center; gap: 6px; }
.sg-next::before { content: "↓"; color: var(--primary); font-weight: 700; }
.sg-res { border-left: 5px solid var(--c); margin: -12px 0 -12px -14px; padding: 12px 14px 12px 12px; display: grid; gap: 4px; }
.sg-score { font-size: 18px; font-weight: 800; color: var(--c); font-variant-numeric: tabular-nums; }
.sg-score span { font-size: 12px; font-weight: 500; color: var(--text-secondary); margin-left: 6px; }
.sg-res p { font-size: 13px; color: var(--text-secondary); line-height: 1.55; }
.sg-ns .on { background: #FFF4C2; transition: background-color .25s ease; }
@media (prefers-reduced-motion: reduce) { .sg-ns .on { transition: none; } }

.sg-examples { display: grid; gap: 10px; }
.sg-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.sg-chips button { font-size: 13px; padding: 7px 12px; border-radius: 8px; border: 1.5px solid var(--border); background: var(--bg-card); color: var(--text-primary); cursor: pointer; }
.sg-chips button:hover { border-color: var(--primary); }
.sg-chips button[aria-pressed="true"] { border-color: var(--primary); background: var(--primary-light); color: var(--primary); font-weight: 600; }
.sg-chips button:focus-visible { outline: 3px solid var(--primary); outline-offset: 2px; }
.sg-quote { border: 1.5px solid var(--border); border-radius: 10px; padding: 14px 16px; display: grid; gap: 6px; font-size: 14px; line-height: 1.65; background: var(--bg-page); }
.sg-qq { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
.sg-why { font-size: 13px; color: var(--text-secondary); }
.sg-note { font-size: 12.5px; color: var(--text-muted); }
.sg-calc { font-size: 13px; color: var(--text-secondary); line-height: 1.8; font-variant-numeric: tabular-nums; }
.sg-calc b { color: var(--text-primary); }
`
