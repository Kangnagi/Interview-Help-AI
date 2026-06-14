import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
#from services.llm import korbert_service

from core.config import settings
from core.database import init_db
from routers import auth, interview, analysis, websocket, stt
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
    docs_url="/docs",
    redoc_url="/redoc",
)

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
