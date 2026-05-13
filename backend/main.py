"""
AI 면접 도우미 — FastAPI 진입점
- lifespan: DB 초기화 + AI 모델 사전 로딩 (Stub)
- /api/v1 prefix 라우터 등록
- /ws WebSocket 라우터 등록
- CORS, 정적 업로드 디렉토리 마운트
"""
import logging                                          # 서버 로그 출력용 모듈
from contextlib import asynccontextmanager              # 비동기 lifespan 컨텍스트 관리자
from fastapi import FastAPI                             # FastAPI 메인 클래스
from fastapi.middleware.cors import CORSMiddleware      # 브라우저 CORS 허용 미들웨어
from fastapi.staticfiles import StaticFiles             # 정적 파일 서빙 (업로드 폴더)

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

# 로그 레벨: DEBUG 모드면 INFO, 아니면 WARNING
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("app")   # 이 모듈 전용 로거


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 시작")

    # 1) DB 테이블 생성 (없으면 자동 생성)
    await init_db()
    logger.info("DB 초기화 완료")

    # 2) AI 모델 사전 로딩 (현재 모두 Stub — 실제 모델 교체 예정)
    await kobert_service.load_model()       # KoBERT 토크나이저 + 모델 로드
    await whisper_service.load_model()      # Whisper 음성 인식 모델 로드
    await mediapipe_service.initialize()    # MediaPipe 얼굴/자세 감지 초기화
    logger.info("AI 모델 준비 완료 (Stub)")

    yield   # 서버 실행 중 (요청 처리 시작)

    # ── Shutdown ─────────────────────────────
    logger.info("앱 종료")


# FastAPI 앱 인스턴스 생성 — Swagger 문서 자동 제공
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",     # Swagger UI 경로
    redoc_url="/redoc",   # ReDoc 문서 경로
)

# CORS 설정 — 프론트엔드(localhost:5173 등)에서 API 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,    # 허용할 Origin 목록 (.env에서 관리)
    allow_credentials=True,                 # 쿠키/인증 헤더 허용
    allow_methods=["*"],                    # 모든 HTTP 메서드 허용
    allow_headers=["*"],                    # 모든 헤더 허용
)

# 업로드 파일을 /uploads URL로 정적 서빙 (개발용 — 운영에서는 S3/CDN 권장)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# REST 라우터 등록 — 모두 /api/v1 prefix 아래에 묶음
API_PREFIX = "/api/v1"
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(interview.router, prefix=API_PREFIX)
app.include_router(analysis.router,  prefix=API_PREFIX)
app.include_router(auth.router,      prefix=API_PREFIX)   # /api/v1/auth
app.include_router(interview.router, prefix=API_PREFIX)   # /api/v1/interviews
app.include_router(analysis.router,  prefix=API_PREFIX)   # /api/v1/analysis
app.include_router(stt.router,       prefix=API_PREFIX)   # /api/v1/stt

# WebSocket은 별도 prefix 없이 /ws/... 경로 사용
app.include_router(websocket.router)


@app.get("/", tags=["Health"])
async def root():
    # 서버 상태 확인용 루트 엔드포인트
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    # 헬스체크 — 로드밸런서/모니터링 도구가 서버 생존 여부 확인
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    # 직접 실행 시 uvicorn으로 서버 구동 (DEBUG=True면 코드 변경 시 자동 재시작)
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
