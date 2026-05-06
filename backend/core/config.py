from pydantic_settings import BaseSettings   # .env 파일을 자동으로 읽어주는 설정 베이스 클래스
from pydantic import AnyHttpUrl              # HTTP URL 유효성 검사 타입
from typing import List                      # 리스트 타입 힌트
import os                                    # 디렉토리 생성 등 OS 작업


class Settings(BaseSettings):
    # ── 앱 기본 설정 ───────────────────────────────────────
    APP_NAME: str = "AI 면접 도우미"             # Swagger UI 및 로그에 표시될 앱 이름
    APP_VERSION: str = "0.1.0"                   # 앱 버전 (API 응답 / 문서에 노출)
    DEBUG: bool = True                            # True면 자세한 로그 + 서버 자동 재시작
    HOST: str = "0.0.0.0"                        # 서버 바인딩 주소 (0.0.0.0 = 외부 접근 허용)
    PORT: int = 8000                              # 서버 포트

    # ── 보안 ───────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-key-change-in-production"   # JWT 서명 비밀키 (운영 시 반드시 교체)
    ALGORITHM: str = "HS256"                     # JWT 서명 알고리즘
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60        # 액세스 토큰 유효 시간 (분)

    # ── DB ─────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./interview.db"   # 비동기 SQLite DB 경로

    # ── CORS ───────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"   # 허용할 프론트엔드 Origin (콤마 구분)

    @property
    def cors_origins(self) -> List[str]:
        # 콤마로 구분된 문자열을 리스트로 분리하여 반환
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # ── 파일 저장 ───────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"               # 업로드 파일 저장 디렉토리
    MAX_UPLOAD_SIZE_MB: int = 100               # 최대 업로드 파일 크기 (MB)

    # ── AI 모델 설정 ────────────────────────────────────────
    KOBERT_MODEL_PATH: str = "./models/kobert"
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_LANGUAGE: str = "ko"
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE: float = 0.5

    # ── Gemini ──────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    class Config:
        env_file = ".env"          # 프로젝트 루트의 .env 파일에서 환경 변수 로드
        case_sensitive = True      # 환경 변수 이름 대소문자 구분


settings = Settings()   # 전역 설정 싱글톤 — 어디서든 import해서 사용

# 업로드 디렉토리가 없으면 자동 생성 (exist_ok=True: 이미 있어도 에러 없음)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
