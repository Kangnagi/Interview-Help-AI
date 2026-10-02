# 🎤 AI 면접 도우미 (Interview Help AI)

AI 기반 실시간 면접 연습 플랫폼입니다. 카메라·마이크로 면접을 진행하면 AI가 답변·표정·자세·음성을 분석해 점수와 피드백을 줍니다.
외부 AI API 없이 서버 PC 안의 모델만으로 동작합니다.

- 서비스 주소: https://www.neailview.com
- 개발 브랜치: `feature/release`

---

## 🛠 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | React 18, Vite 5, Zustand, Recharts, Axios |
| Backend | FastAPI, SQLAlchemy (async), SQLite(WAL), JWT |
| 답변 채점 · 질문 생성 · 총평 | Bllossom-3B (한국어 Llama-3.2-3B) + 채점 LoRA 어댑터 |
| 발화 분석 | librosa (말 속도 · 침묵 · 억양 · 음량), PyAV (브라우저 녹음 디코딩) |
| 표정 · 자세 분석 | MediaPipe (CPU) |
| 음성 → 글자 | 브라우저 Web Speech API (Chrome 권장) |
| 배포 | Cloudflare Tunnel → Vite preview(:5173) → FastAPI(:8000) |

---

## 📁 프로젝트 구조

```
Interview-Help-AI/
├── backend/
│   ├── main.py                 # FastAPI 앱 진입점 (시작할 때 모델을 GPU에 올림)
│   ├── env.example             # 환경변수 템플릿 → .env로 복사해서 사용
│   ├── requirements.txt
│   ├── migrate_db.py           # 기존 DB에 새 컬럼 추가 (새 DB는 자동 생성)
│   ├── core/                   # 설정, DB, 보안, 메일
│   ├── models/ · schemas/      # DB 모델 · 요청/응답 형식
│   ├── routers/                # API (auth, interview, analysis, feedback, stats, admin_review, websocket)
│   ├── services/
│   │   ├── llm/llama_service.py   # 채점 · 피드백 · 질문 생성 · 총평
│   │   ├── llm/question_bank.py   # 질문 생성이 모자랄 때 쓰는 직무별 기본 질문
│   │   ├── voice/librosa_service.py
│   │   └── vision/mediapipe_service.py
│   ├── training/               # 채점 모델 학습 · 평가 스크립트, 채점 기준표(claude_rubric_v3.md)
│   └── ai_models/              # 채점 어댑터 (git 제외 — 따로 전달받아 넣음)
├── frontend/
│   ├── src/                    # pages, components, services(API·WebSocket), store, hooks
│   └── vite.config.js          # /api, /ws 요청을 백엔드(:8000)로 전달
└── scripts/                    # 서버 PC 전용 실행 · 자동 시작 스크립트
```

---

## ⚙️ 개인 PC에서 실행하기 (Windows 기준)

### 1. 준비물

| 항목 | 권장 |
|------|------|
| Python | 3.11 이상 (서버 PC는 3.13) |
| Node.js | 18 이상 (22 · 24에서 확인) |
| NVIDIA GPU | 메모리 8GB 이상 — 모델이 약 7.3GB 사용. GPU가 없으면 채점이 매우 느려 실사용이 어렵습니다 |
| 디스크 | 약 15GB (가상환경 + 모델 다운로드 6.4GB) |
| 브라우저 | Chrome (음성 입력이 Web Speech API를 사용) |

### 2. 코드 받기

```cmd
git clone -b feature/release https://github.com/Kangnagi/Interview-Help-AI.git
cd Interview-Help-AI
```

이미 받아 둔 경우에는 `git checkout feature/release` 후 `git pull`.

### 3. 백엔드

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate

:: (1) GPU용 PyTorch를 먼저 설치 — 그냥 pip install torch를 하면 GPU를 못 쓰는 CPU 버전이 깔릴 수 있음
::     https://pytorch.org/get-started/locally/ 에서 본인 CUDA 버전에 맞는 명령을 고르세요. 예:
pip install torch --index-url https://download.pytorch.org/whl/cu128

:: (2) 나머지 패키지
pip install -r requirements.txt

:: (3) GPU 인식 확인 — True가 나와야 함
python -c "import torch; print(torch.cuda.is_available())"

:: (4) 환경변수 파일
copy env.example .env
```

`.env`에서 `SECRET_KEY`를 아무 긴 문자열로 바꾸세요. 모델 설정은 `env.example` 그대로 쓰면 됩니다.

```env
LLAMA_BASE_MODEL=Bllossom/llama-3.2-Korean-Bllossom-3B
LLAMA_ADAPTER_PATH=
LLAMA_SCORE_ADAPTER_PATH=./ai_models/bllossom-score-adapter-b3
TEXT_MODEL=
```

### 4. 채점 어댑터 넣기

채점 어댑터(`bllossom-score-adapter-b3.zip`, 약 90MB)는 저장소에 없으므로 LLM 담당에게 받아서 압축을 풉니다. 아래 경로가 되면 정상입니다.

```
backend/ai_models/bllossom-score-adapter-b3/adapter_model.safetensors
```

`ai_models/bllossom-score-adapter-b3/bllossom-score-adapter-b3/...`처럼 폴더가 두 번 겹치지 않게 주의하세요.
어댑터가 없어도 서버는 켜지지만 점수가 답변 길이 기반 기본값(45 · 55 · 65점)으로만 나옵니다.

### 5. 백엔드 실행

```cmd
python main.py
```

- 처음 실행할 때 Bllossom-3B(약 6.4GB)를 Hugging Face에서 자동으로 내려받습니다 (한 번만).
- 모델을 GPU에 올리는 데 30초 정도 걸리고, 로그에 `AI 모델 준비 완료`가 나오면 준비된 것입니다.
- DB(`backend/interview.db`)는 처음 실행할 때 자동으로 만들어집니다.
- API 문서: http://localhost:8000/docs (`.env`의 `DEBUG=true`일 때)

### 6. 프런트엔드 (새 터미널)

```cmd
cd frontend
npm ci
npm run dev
```

http://localhost:5173 으로 접속합니다. 화면 코드를 고치면 바로 반영됩니다.

> `npm run serve`는 운영용입니다 (빌드 후 실행). 코드를 고칠 때마다 다시 실행해야 반영되므로 개발할 때는 `npm run dev`를 쓰세요.

### 7. 동작 확인

1. 회원가입 → 로그인 → 연습면접 시작 → 질문 5개가 3~8초 안에 나오면 질문 생성 정상
2. 답변 후 면접 종료 → 10~15초 뒤 결과 화면에 질문별 점수와 피드백 3줄이 나오면 채점 정상
3. 모든 질문이 45 · 55 · 65점에 피드백도 똑같다면 어댑터를 못 읽은 것 → 4번의 폴더 위치를 확인

---

## 🔑 환경변수 (.env) 주요 항목

| 항목 | 설명 |
|------|------|
| `SECRET_KEY` | 로그인 토큰 서명 키 — 반드시 바꿀 것 |
| `DATABASE_URL` | 기본 `sqlite+aiosqlite:///./interview.db` (자동 생성) |
| `ALLOWED_ORIGINS` | 접속을 허용할 화면 주소 (개인 PC는 `http://localhost:5173` 포함) |
| `LLAMA_*`, `TEXT_MODEL` | 모델 설정 (위 3번 참고, 예전 구성으로 되돌리는 방법은 env.example 주석) |
| `SMTP_*`, `FRONTEND_URL` | 비밀번호 재설정 메일 — 메일을 시험할 때만 필요 |
| `ADMIN_EMAILS` | 관리자 검토 화면을 쓸 계정 이메일 (쉼표로 구분) |

`.env`에는 비밀값이 들어가므로 절대 커밋하지 마세요 (`.gitignore`에 등록되어 있음).

---

## 📡 주요 API (`/api/v1`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/auth/register` · `/auth/login` | 회원가입 · 로그인 (JWT) |
| POST | `/auth/password-reset/request` · `/confirm` | 비밀번호 재설정 |
| POST · GET | `/interviews` | 면접 생성(질문 생성 포함) · 목록 |
| POST | `/interviews/{id}/questions/{qid}/answer` | 답변 저장 |
| PATCH | `/interviews/{id}/finish` | 면접 종료 |
| POST · GET | `/analysis/{id}/start` · `/analysis/{id}` | 분석 시작 · 결과 |
| GET · PUT | `/users/me/training-consent` | AI 학습 활용 동의 |
| PUT | `/interviews/{id}/questions/{qid}/rating` | 질문별 AI 채점 평가 |
| GET | `/stats/dashboard` | 통계 대시보드 |
| GET · PUT | `/admin/review/...` | 관리자 검토 (ADMIN_EMAILS 계정만) |
| WS | `/ws/interview/{id}` · `/ws/interview_audio/{id}` | 실시간 영상 · 녹음 (토큰 + 면접 소유자 확인) |

---

## 🖥️ 서버 PC 운영 (서버 담당 전용)

| 스크립트 | 역할 |
|----------|------|
| `scripts/start_all.ps1` | 백엔드 · 프런트엔드(운영 빌드) · Cloudflare 터널을 감시 루프로 시작 (`-Dev`면 개발 서버) |
| `scripts/stop_all.ps1` | 모두 중지 |
| `scripts/restart_frontend.ps1` | 프런트엔드만 다시 빌드 · 재시작 (화면 코드 수정 후 반영할 때) |
| `scripts/register_autostart.ps1` | 로그온 시 자동 실행 작업 등록 |
| `scripts/backup.ps1 -Dest E:\` | git에 없는 것(.env · 터널 인증 · DB · 어댑터 · 학습 데이터)을 USB로 백업 (`-Full`이면 예전 어댑터 전부까지) |

이 스크립트들은 저장소의 `.tools/`(git 제외)에 둔 node · cloudflared와 서버 PC의 터널 인증 정보를 쓰므로 개인 PC에서는 쓰지 않습니다.

---

## ⚠️ 주의사항

- git에 없는 것: `.env`, DB, 업로드 파일(녹화 · 녹음), 채점 어댑터(`ai_models/`), 학습 데이터, 터널 인증 정보
- 학교 와이파이에서는 neailview.com 접속이 차단됩니다 (학교 방화벽). 휴대폰 데이터 · 핫스팟으로 접속하세요.
- 카메라 · 마이크 권한을 브라우저에서 허용해야 면접 기능이 동작합니다.
