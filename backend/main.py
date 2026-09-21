import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
#from services.llm import korbert_service

from core.config import settings
from core.database import init_db
from core.rate_limit import limiter
from core.security_middleware import SecurityHeadersMiddleware, RequestSizeLimitMiddleware
from routers import auth, interview, analysis, websocket, stt, stats
from services.vision.mediapipe_service import mediapipe_service
from services.llm.kobert_service import kobert_service

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 시작")

    await init_db()
    logger.info("DB 초기화 완료")

    # KoBERT는 로딩 시간이 길고 현재 Gemini로 대체되어 비활성화
    # await kobert_service.load_model()
  
    await mediapipe_service.initialize()
    logger.info("AI 모델 준비 완료")

    yield

    logger.info("앱 종료")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # 운영 환경(DEBUG=False)에서는 API 문서·스키마를 외부에 노출하지 않는다.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# Rate Limiting — app.state에 등록해야 @limiter.limit() 데코레이터와 예외 핸들러가 동작한다.
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요"},
    )


app.add_middleware(SlowAPIMiddleware)   # limiter.default_limits(전체 API 제한)를 실제로 적용

# 아래 미들웨어들은 등록 순서의 역순으로 요청을 감싼다 — 보안 헤더/크기 제한이
# CORS보다 먼저 실행되어, 거부된 요청에도 보안 헤더가 always 붙는다.
app.add_middleware(
    RequestSizeLimitMiddleware,
    default_max_bytes=settings.MAX_REQUEST_SIZE_MB * 1024 * 1024,
    large_upload_max_bytes=settings.MAX_UPLOAD_REQUEST_SIZE_MB * 1024 * 1024,
)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

API_PREFIX = "/api/v1"
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(interview.router, prefix=API_PREFIX)
app.include_router(analysis.router,  prefix=API_PREFIX)
app.include_router(stt.router,       prefix=API_PREFIX)
app.include_router(stats.router,     prefix=API_PREFIX)
app.include_router(websocket.router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else None,
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
