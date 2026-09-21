from datetime import datetime, timedelta         # 토큰 만료 시간 계산용
from typing import Optional                      # 선택적 타입 힌트
from jose import JWTError, jwt                   # JWT 생성/디코딩 라이브러리
from passlib.context import CryptContext         # 비밀번호 해싱 컨텍스트
from fastapi import Depends, HTTPException, status   # FastAPI DI, HTTP 예외, 상태 코드
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials   # Bearer 토큰 추출
from sqlalchemy.ext.asyncio import AsyncSession   # 계정 잠금 상태 갱신 시 사용
from core.config import settings                 # SECRET_KEY, ALGORITHM 등 설정

# 비밀번호 해싱 알고리즘: argon2 사용 (bcrypt보다 메모리 집약적 → 무차별 대입 공격 방어)
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"   # 구식 알고리즘으로 해시된 비밀번호는 자동으로 최신 알고리즘으로 재해시
)

# HTTP Authorization 헤더에서 Bearer 토큰 자동 추출
bearer_scheme = HTTPBearer()


def hash_password(password: str):
    # 평문 비밀번호를 argon2 해시로 변환하여 DB에 저장
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str):
    # 입력한 평문 비밀번호와 DB의 해시를 비교하여 일치 여부 반환
    return pwd_context.verify(password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    # JWT 액세스 토큰 생성
    to_encode = data.copy()   # 원본 데이터 딕셔너리 복사 (원본 수정 방지)
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )   # 만료 시간 계산 (기본값: 설정의 ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})   # 페이로드에 만료 시간 추가
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)   # JWT 서명 후 반환


def decode_token(token: str) -> dict:
    # JWT 토큰 검증 및 페이로드 디코딩
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        # 토큰이 위조되었거나 만료된 경우 401 반환
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},   # 클라이언트에게 Bearer 인증 요구 안내
        )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    # FastAPI Dependency — Authorization 헤더의 Bearer 토큰에서 사용자 ID 추출
    payload = decode_token(credentials.credentials)   # 토큰 검증 및 페이로드 추출
    user_id: int = payload.get("sub")                 # JWT sub 클레임에서 사용자 ID 가져오기

    if user_id is None:
        # sub 클레임이 없는 경우 (잘못된 토큰 구조)
        raise HTTPException(status_code=401, detail="토큰에 사용자 정보가 없습니다")

    return int(user_id)   # 문자열로 저장된 ID를 정수로 변환하여 반환


def is_account_locked(user) -> bool:
    """현재 시각 기준으로 계정이 잠금 상태인지 확인한다 (locked_until이 미래 시각이면 잠김)."""
    return bool(user.locked_until and user.locked_until > datetime.utcnow())


async def register_failed_login(user, db: AsyncSession) -> None:
    """
    로그인 실패 1회를 기록한다.

    누적 실패 횟수가 ACCOUNT_LOCK_THRESHOLD에 도달하면 ACCOUNT_LOCK_MINUTES 동안 잠근다.
    """
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

    if user.failed_login_attempts >= settings.ACCOUNT_LOCK_THRESHOLD:
        user.locked_until = datetime.utcnow() + timedelta(minutes=settings.ACCOUNT_LOCK_MINUTES)

    db.add(user)
    await db.commit()


async def reset_failed_login(user, db: AsyncSession) -> None:
    """로그인 성공 시 실패 횟수·잠금 상태를 초기화한다."""
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    await db.commit()
