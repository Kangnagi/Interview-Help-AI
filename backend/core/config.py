from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, model_validator
from typing import List, Optional
import os

# 운영 환경(DEBUG=False)에서 절대 써서는 안 되는 SECRET_KEY 값들
_INSECURE_SECRET_KEYS = {
    "dev-secret-key-change-in-production",
    "changeme",
    "secret",
    "",
}


class Settings(BaseSettings):
    # ── 앱 기본 설정 ───────────────────────────────────────
    APP_NAME: str = "AI 면접 도우미"             # Swagger UI 및 로그에 표시될 앱 이름
    APP_VERSION: str = "2.0.0"                   # 앱 버전 (API 응답 / 문서에 노출)
    DEBUG: bool = True                            # True면 자세한 로그 + 서버 자동 재시작
    HOST: str = "0.0.0.0"                        # 서버 바인딩 주소 (0.0.0.0 = 외부 접근 허용)
    PORT: int = 8000                              # 서버 포트

    # ── 보안 ───────────────────────────────────────────────
    SECRET_KEY: str = "dev-secret-key-change-in-production"   # JWT 서명 비밀키 (운영 시 반드시 교체)
    ALGORITHM: str = "HS256"                     # JWT 서명 알고리즘
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60        # 액세스 토큰 유효 시간 (분)
    GEMINI_API_KEY: Optional[str] = None        # .env 파일에 GEMINI_API_KEY= 로 설정
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ── Rate Limiting / 계정 잠금 ───────────────────────────────
    LOGIN_RATE_LIMIT: str = "5/minute"           # POST /auth/login IP당 제한
    REGISTER_RATE_LIMIT: str = "3/minute"        # POST /auth/register IP당 제한
    GLOBAL_RATE_LIMIT: str = "100/minute"        # 그 외 전체 API IP당 제한
    ACCOUNT_LOCK_THRESHOLD: int = 5              # 연속 로그인 실패 허용 횟수
    ACCOUNT_LOCK_MINUTES: int = 15               # 잠금 유지 시간(분)

    # ── 요청 크기 제한 ───────────────────────────────────────────
    MAX_REQUEST_SIZE_MB: int = 10                # 일반 API 요청 본문 최대 크기
    MAX_UPLOAD_REQUEST_SIZE_MB: int = 200        # 업로드 경로(STT 등) 최대 크기

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

    # ── 이메일 설정 (비밀번호 재설정) ──────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None       # .env 에서 설정: SMTP_USER=your@gmail.com
    SMTP_PASSWORD: Optional[str] = None   # .env 에서 설정: SMTP_PASSWORD=앱비밀번호
    FRONTEND_URL: str = "http://localhost:5173"   # 재설정 링크에 사용할 프론트 주소

    # ── AI 모델 설정 ────────────────────────────────────────
    KOBERT_MODEL_PATH: str = "./models/kobert"              # KoBERT 로컬 모델 경로 (미사용 시 HuggingFace 자동 다운)
    WHISPER_MODEL_SIZE: str = "base"                        # Whisper 모델 크기 (tiny/base/small/medium/large)
    WHISPER_LANGUAGE: str = "ko"                            # Whisper 인식 언어 (한국어 고정)
    MEDIAPIPE_MIN_DETECTION_CONFIDENCE: float = 0.5        # MediaPipe 얼굴 감지 최소 신뢰도 (0~1)

    class Config:
        env_file = ".env"          # 프로젝트 루트의 .env 파일에서 환경 변수 로드
        case_sensitive = True      # 환경 변수 이름 대소문자 구분

    @model_validator(mode="after")
    def _enforce_strong_secret_key_in_production(self) -> "Settings":
        """
        DEBUG=False(운영 환경)에서 기본값·짧은 SECRET_KEY로 뜨는 것을 원천 차단한다.

        안전한 키 생성 방법:
            python -c "import secrets; print(secrets.token_hex(32))"
        생성한 값은 코드가 아니라 반드시 .env 파일의 SECRET_KEY= 에만 설정한다.
        """
        if not self.DEBUG:
            if self.SECRET_KEY in _INSECURE_SECRET_KEYS or len(self.SECRET_KEY) < 32:
                raise RuntimeError(
                    "안전하지 않은 SECRET_KEY입니다. 운영 환경(DEBUG=False)에서는 "
                    ".env 파일에 32자 이상의 랜덤 SECRET_KEY를 설정해야 합니다.\n"
                    '생성 방법: python -c "import secrets; print(secrets.token_hex(32))"'
                )
        return self


settings = Settings()   # 전역 설정 싱글톤 — 어디서든 import해서 사용

# 업로드 디렉토리가 없으면 자동 생성 (exist_ok=True: 이미 있어도 에러 없음)
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
