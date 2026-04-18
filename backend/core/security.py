from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from core.config import settings

# 🔥 bcrypt → argon2로 변경
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

bearer_scheme = HTTPBearer()


# 🔥 비밀번호 해싱
def hash_password(password: str):
    return pwd_context.hash(password)


# 🔥 비밀번호 검증
def verify_password(password: str, hashed_password: str):
    return pwd_context.verify(password, hashed_password)


# 🔐 JWT 생성
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# 🔐 JWT 디코딩
def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )


# 🔐 현재 사용자 ID 추출
async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> int:
    payload = decode_token(credentials.credentials)
    user_id: int = payload.get("sub")

    if user_id is None:
        raise HTTPException(status_code=401, detail="토큰에 사용자 정보가 없습니다")

    return int(user_id)
