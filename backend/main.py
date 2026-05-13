"""
AI 면접 도우미 — FastAPI 진입점

앱 시작 순서:
  1. lifespan: DB 테이블 생성 → AI 모델 3종 사전 로딩
  2. 미들웨어: CORS 허용 (프론트 Origin 화이트리스트)
  3. 라우터:   /api/v1/auth · /api/v1/interviews · /api/v1/analysis · /ws/...
  4. 정적 파일: /uploads → 로컬 업로드 디렉토리 서빙
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import init_db
from routers import auth, interview, analysis, websocket
from services.llm.kobert_service import kobert_service
from services.voice.whisper_service import whisper_service
from services.vision.mediapipe_service import mediapipe_service
from core.config import settings                        # 환경 변수 / 앱 설정 객체
from core.database import init_db                       # 앱 시작 시 DB 테이블 생성 함수
from routers import auth, interview, analysis, websocket, stt   # 각 기능별 라우터
from services.llm.kobert_service import kobert_service          # KoBERT 답변 분석 서비스
from services.voice.whisper_service import whisper_service      # Whisper STT 서비스
from services.vision.mediapipe_service import mediapipe_service # MediaPipe 비전 분석 서비스
from core.config import settings                          # 환경 변수 / 앱 설정 객체
from core.database import init_db                         # 앱 시작 시 DB 테이블 생성 함수
from routers import auth, interview, analysis, websocket  # 각 기능별 라우터
from services.llm.kobert_service import kobert_service    # KoBERT 답변 분석 서비스 싱글톤
from services.voice.whisper_service import whisper_service        # Whisper STT 서비스 싱글톤
from services.vision.mediapipe_service import mediapipe_service   # MediaPipe 비전 분석 서비스 싱글톤

# DEBUG=True면 INFO 레벨 이상 출력, 운영 환경에서는 WARNING 이상만 출력
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan 핸들러 — 서버 시작/종료 시 딱 1회 실행되는 코드 블록.

    yield 이전: Startup (DB 초기화, AI 모델 로딩)
    yield 이후: Shutdown (리소스 정리)

    @app.on_event("startup") 대신 lifespan을 쓰는 이유:
    FastAPI 권장 방식이며 startup/shutdown을 한 블록으로 관리할 수 있음.
    """
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 시작")

    # 1) DB 테이블 생성 — ORM 모델을 읽어 없는 테이블만 CREATE TABLE (기존 데이터 유지)
    await init_db()
    logger.info("DB 초기화 완료")

    # 2) AI 모델 사전 로딩 — 첫 요청 때 지연 없이 응답하기 위해 서버 시작 시 미리 로드
    await kobert_service.load_model()       # KoBERT 토크나이저 + 모델 (HuggingFace)
    await whisper_service.load_model()      # Whisper 음성 인식 모델 (현재 Stub)
    await mediapipe_service.initialize()    # MediaPipe FaceMesh + Pose 초기화
    logger.info("AI 모델 준비 완료")

    yield   # ← 서버가 실제 요청을 처리하는 구간

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("앱 종료")


# ─── FastAPI 앱 인스턴스 ──────────────────────────────────────────────────────
# lifespan 주입으로 시작/종료 훅 연결, /docs·/redoc는 개발용 Swagger UI
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",    # Swagger UI: http://localhost:8000/docs
    redoc_url="/redoc",  # ReDoc UI:   http://localhost:8000/redoc
)

# ─── CORS 미들웨어 ────────────────────────────────────────────────────────────
# 브라우저는 다른 Origin(포트/도메인)의 API 호출을 기본 차단함.
# 프론트엔드(localhost:5173 등)에서 백엔드(localhost:8000)를 호출할 수 있도록 허용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # .env의 ALLOWED_ORIGINS에서 관리 (쉼표 구분)
    allow_credentials=True,               # Authorization 헤더 / 쿠키 포함 요청 허용
    allow_methods=["*"],                  # GET·POST·PUT·PATCH·DELETE 전체 허용
    allow_headers=["*"],                  # Content-Type·Authorization 등 전체 허용
)

# ─── 정적 파일 서빙 ───────────────────────────────────────────────────────────
# /uploads/{파일명} URL로 업로드된 영상/오디오에 직접 접근 가능.
# 운영 환경에서는 S3 + CloudFront 같은 CDN으로 교체 권장.
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# ─── 라우터 등록 ─────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(interview.router, prefix=API_PREFIX)
app.include_router(analysis.router,  prefix=API_PREFIX)
app.include_router(auth.router,      prefix=API_PREFIX)   # /api/v1/auth
app.include_router(interview.router, prefix=API_PREFIX)   # /api/v1/interviews
app.include_router(analysis.router,  prefix=API_PREFIX)   # /api/v1/analysis
app.include_router(stt.router,       prefix=API_PREFIX)   # /api/v1/stt
app.include_router(auth.router,      prefix=API_PREFIX)   # /api/v1/auth      — 회원가입·로그인
app.include_router(interview.router, prefix=API_PREFIX)   # /api/v1/interviews — 면접 CRUD
app.include_router(analysis.router,  prefix=API_PREFIX)   # /api/v1/analysis   — AI 분석

# WebSocket은 REST prefix 없이 /ws/... 경로 직접 사용
app.include_router(websocket.router)                      # /ws/interview/{id} — 실시간 분석


# ─── 헬스체크 엔드포인트 ──────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    """서버 정보 반환 — Swagger 링크 포함."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    """로드밸런서·모니터링 도구가 서버 생존 여부를 확인하는 엔드포인트."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # python main.py 직접 실행 시 uvicorn 서버 구동
    # DEBUG=True면 코드 변경 감지 시 자동 재시작 (reload=True)
    uvicorn.run(
        "main:app",
        host=settings.HOST,   # 0.0.0.0 → 외부 접근 허용
        port=settings.PORT,   # 기본 8000
        reload=settings.DEBUG,
    )
