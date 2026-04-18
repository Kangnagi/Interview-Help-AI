# 🎤 AI 면접 도우미 (Interview Help AI)

AI 기반 실시간 면접 연습 플랫폼입니다.  
카메라·마이크를 통해 면접을 진행하고, AI가 답변·표정·음성을 분석해 피드백을 제공합니다.

---

## 🛠 기술 스택

| 영역 | 기술 |
|------|------|
| Frontend | React 18, Vite, Zustand, Recharts, Axios |
| Backend | FastAPI, SQLAlchemy (async), SQLite, JWT |
| AI (예정) | KoBERT, Whisper, MediaPipe, py-feat, Librosa |

---

## 📁 프로젝트 구조

```
Interview-Help-AI/
├── backend/
│   ├── main.py              # FastAPI 앱 진입점
│   ├── env.example          # 환경변수 템플릿
│   ├── requirements.txt     # Python 패키지 목록
│   ├── core/                # 설정, DB, 보안
│   ├── models/              # SQLAlchemy ORM 모델
│   ├── routers/             # API 라우터
│   ├── schemas/             # Pydantic 스키마
│   └── services/            # AI 모델 서비스 (Stub)
│       ├── llm/             # KoBERT 답변 분석
│       ├── voice/           # Whisper STT
│       └── vision/          # MediaPipe 표정/자세
│
└── frontend/
    ├── src/
    │   ├── pages/           # 라우트 페이지
    │   ├── components/      # 공통 컴포넌트
    │   ├── services/        # API·WebSocket 클라이언트
    │   ├── store/           # Zustand 상태관리
    │   └── styles/          # 전역 CSS
    ├── vite.config.js
    └── package.json
```

---

## ⚙️ 실행 방법

### 사전 요구사항

| | Windows | macOS |
|---|---|---|
| Python | 3.11 이상 | 3.11 이상 |
| Node.js | 18 이상 | 18 이상 |
| pip | 포함됨 | 포함됨 |

---

### 🖥️ Backend 실행

#### Windows

```cmd
:: 1. backend 폴더로 이동
cd backend

:: 2. 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate

:: 3. 패키지 설치
pip install -r requirements.txt

:: 4. 환경변수 파일 생성
copy env.example .env

:: 5. (선택) .env 파일에서 SECRET_KEY 수정

:: 6. 서버 실행
python main.py
```

#### macOS / Linux

```bash
# 1. backend 폴더로 이동
cd backend

# 2. 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 환경변수 파일 생성
cp env.example .env

# 5. (선택) .env 파일에서 SECRET_KEY 수정

# 6. 서버 실행
python main.py
```

백엔드 실행 후 접속 주소:
- **서버**: http://localhost:8000
- **API 문서 (Swagger)**: http://localhost:8000/docs

---

### 🌐 Frontend 실행

> **참고**: 압축 파일에 `node_modules`가 포함되어 있습니다.  
> macOS 또는 다른 환경에서 실행 시 `npm install`을 한 번 실행해 주세요.

#### Windows

```cmd
:: 1. frontend 폴더로 이동
cd frontend

:: 2. 패키지 설치 (node_modules가 없거나 오류 발생 시)
npm install

:: 3. 개발 서버 실행
npm run dev
```

#### macOS / Linux

```bash
# 1. frontend 폴더로 이동
cd frontend

# 2. 패키지 설치
npm install

# 3. 개발 서버 실행
npm run dev
```

프론트엔드 실행 후 접속 주소:
- **앱**: http://localhost:5173

---

### 🔄 동시 실행 순서

백엔드와 프론트엔드를 **각각 별도의 터미널**에서 실행합니다.

```
터미널 1 → backend 실행 (포트 8000)
터미널 2 → frontend 실행 (포트 5173)
```

Vite가 `/api` 요청은 `localhost:8000`으로, `/ws` WebSocket은 `ws://localhost:8000`으로 자동 프록시합니다.

---

## 🔑 환경변수 (.env)

`backend/env.example`을 복사해 `.env`로 사용합니다. 주요 항목:

```env
# 보안 (운영 환경에서 반드시 변경)
SECRET_KEY=your-secret-key-change-this-in-production

# 데이터베이스 (SQLite, 자동 생성)
DATABASE_URL=sqlite+aiosqlite:///./interview.db

# CORS 허용 주소
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# 서버 포트
PORT=8000
```

---

## 📡 API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/auth/register` | 회원가입 |
| POST | `/api/v1/auth/login` | 로그인 (JWT 발급) |
| POST | `/api/v1/interviews` | 면접 세션 생성 |
| GET | `/api/v1/interviews` | 면접 목록 조회 |
| GET | `/api/v1/interviews/{id}/questions` | 질문 목록 조회 |
| POST | `/api/v1/interviews/{id}/questions/{qid}/answer` | 답변 저장 |
| PATCH | `/api/v1/interviews/{id}/finish` | 면접 종료 |
| POST | `/api/v1/analysis/{id}/start` | 분석 시작 |
| GET | `/api/v1/analysis/{id}` | 분석 결과 조회 |
| WS | `/ws/interview/{id}` | 실시간 영상 스트림 |

---

## 🤖 AI 모델 연동 (다음 단계)

현재 AI 서비스는 Stub(더미) 상태입니다.  
아래 순서대로 `requirements.txt`의 주석을 해제하고 서비스 파일의 `TODO`를 구현하면 실제 AI가 동작합니다.

**1단계 — KoBERT (답변 내용 분석)**
```bash
# requirements.txt에서 주석 해제 후 설치
pip install transformers==4.41.0 torch==2.3.0 sentencepiece==0.2.0
# backend/services/llm/kobert_service.py 의 TODO 구현
```

**2단계 — Whisper (음성 → 텍스트)**
```bash
pip install openai-whisper==20231117 ffmpeg-python==0.2.0
# backend/services/voice/whisper_service.py 의 TODO 구현
```

**3단계 — MediaPipe (표정·자세 분석)**
```bash
pip install mediapipe==0.10.14 opencv-python==4.9.0.80 numpy==1.26.4
# backend/services/vision/mediapipe_service.py 의 TODO 구현
```

**4단계 — 고도화**
```bash
pip install py-feat==0.6.1 librosa==0.10.2
```

---

## ⚠️ 주의사항

- 압축 파일에 포함된 `.venv`는 **Windows 전용**입니다. macOS에서는 반드시 새로 생성해야 합니다.
- `interview.db`(SQLite)는 백엔드 첫 실행 시 자동 생성됩니다.
- 카메라·마이크 권한은 브라우저에서 허용해야 면접 기능이 동작합니다.
