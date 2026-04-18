"""
AI 면접 도우미 — FastAPI 진입점
- lifespan: DB 초기화 + AI 모델 사전 로딩 (Stub)
- /api/v1 prefix 라우터 등록
- /ws WebSocket 라우터 등록
- CORS, 정적 업로드 디렉토리 마운트
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

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 시작")

    # 1) DB 테이블 생성
    await init_db()
    logger.info("DB 초기화 완료")

    # 2) AI 모델 사전 로딩 (현재 모두 Stub)
    await kobert_service.load_model()
    await whisper_service.load_model()
    await mediapipe_service.initialize()
    logger.info("AI 모델 준비 완료 (Stub)")

    yield

    # ── Shutdown ─────────────────────────────
    logger.info("앱 종료")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 업로드 정적 서빙 (개발용 — 운영에서는 S3/CDN 권장)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 라우터 등록 — REST는 /api/v1 prefix
API_PREFIX = "/api/v1"
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(interview.router, prefix=API_PREFIX)
app.include_router(analysis.router,  prefix=API_PREFIX)

# WebSocket은 별도 prefix
app.include_router(websocket.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
