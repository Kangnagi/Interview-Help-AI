from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
from typing import List
import os


class Settings(BaseSettings):
    # 앱 기본 설정
    APP_NAME: str = "AI 면접 도우미"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 보안
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # DB
    DATABASE_URL: str = "sqlite+aiosqlite:///./interview.db"

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # 파일 저장
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    # ---- AI 모델 (다음 단계에서 로드) ----
    KOBERT_MODEL_PATH: str = "./models/kobert"
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_LANGUAGE: str = "ko"
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE: float = 0.5

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# 업로드 디렉토리 생성
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
