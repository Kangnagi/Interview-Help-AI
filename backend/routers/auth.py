"""
인증 라우터 — /api/v1/auth

엔드포인트:
  POST /auth/register  — 회원가입
  POST /auth/login     — 로그인 → JWT 액세스 토큰 발급
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.security import hash_password, verify_password, create_access_token
from models.user import User
from schemas.schemas import UserCreate, UserLogin, UserResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    회원가입.

    이메일 중복 확인 후 argon2 해시된 비밀번호로 User 레코드 생성.
    성공 시 생성된 사용자 정보를 반환 (비밀번호 제외).
    """
    # 동일 이메일이 이미 있으면 400 반환 — 이메일은 로그인 식별자이므로 유일해야 함
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다")

    user = User(
        email=body.email,
        username=body.username,
        hashed_password=hash_password(body.password),  # 평문 비밀번호를 argon2 해시로 변환
    )
    db.add(user)
    await db.flush()    # DB에 INSERT 실행하여 auto-increment id 확보 (commit은 get_db가 처리)
    await db.refresh(user)  # DB에서 최신 상태(id, created_at 등)를 다시 읽어옴
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    로그인.

    이메일로 사용자 조회 → 비밀번호 검증 → JWT 발급.
    사용자 미존재와 비밀번호 불일치 모두 동일한 401 메시지 반환
    (어느 쪽이 틀렸는지 노출하지 않아 열거 공격 방어).
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # 사용자 없거나 비밀번호 불일치 — 두 케이스를 하나의 조건으로 처리
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")

    # JWT 페이로드에 user_id를 "sub"(subject) 클레임으로 저장 — OAuth2 관례
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, user=user)
