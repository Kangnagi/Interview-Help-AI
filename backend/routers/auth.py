"""
인증 라우터 — /api/v1/auth

엔드포인트:
  POST /auth/register                — 회원가입
  POST /auth/login                   — 로그인 → JWT 액세스 토큰 발급
  POST /auth/password-reset/request  — 비밀번호 재설정 이메일 요청
  POST /auth/password-reset/confirm  — 토큰 검증 후 새 비밀번호 저장
"""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.config import settings
from core.database import get_db
from core.rate_limit import limiter
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    is_account_locked,
    register_failed_login,
    reset_failed_login,
)
from core.email_service import send_password_reset_email
from models.user import User
from schemas.schemas import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    PasswordResetRequest, PasswordResetConfirm,
)

router = APIRouter(prefix="/auth", tags=["인증"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def register(request: Request, body: UserCreate, db: AsyncSession = Depends(get_db)):
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
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request: Request, body: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    로그인.

    이메일로 사용자 조회 → 계정 잠금 확인 → 비밀번호 검증 → JWT 발급.
    사용자 미존재와 비밀번호 불일치 모두 동일한 401 메시지 반환
    (어느 쪽이 틀렸는지 노출하지 않아 열거 공격 방어).

    ACCOUNT_LOCK_THRESHOLD회 연속 실패 시 ACCOUNT_LOCK_MINUTES분 동안 로그인이 잠긴다.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # 잠금 상태면 비밀번호 검증 자체를 하지 않고 즉시 차단
    if user and is_account_locked(user):
        raise HTTPException(
            status_code=423,
            detail=f"계정이 잠겼습니다. {settings.ACCOUNT_LOCK_MINUTES}분 후 다시 시도해주세요",
        )

    # 사용자 없거나 비밀번호 불일치 — 두 케이스를 하나의 조건으로 처리
    if not user or not verify_password(body.password, user.hashed_password):
        if user:
            await register_failed_login(user, db)
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")

    await reset_failed_login(user, db)

    # JWT 페이로드에 user_id를 "sub"(subject) 클레임으로 저장 — OAuth2 관례
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, user=user)


@router.post("/password-reset/request", status_code=200)
async def request_password_reset(body: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    """
    비밀번호 재설정 이메일 요청.

    이메일이 존재하지 않아도 동일한 응답을 반환해 계정 존재 여부를 노출하지 않음.
    """
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(minutes=30)
        db.add(user)
        await db.commit()
        await send_password_reset_email(user.email, token)

    return {"message": "비밀번호 재설정 링크를 이메일로 발송했습니다. 받은 편지함을 확인해주세요."}


@router.post("/password-reset/confirm", status_code=200)
async def confirm_password_reset(body: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    """
    토큰 검증 후 새 비밀번호 저장.
    """
    result = await db.execute(select(User).where(User.reset_token == body.token))
    user = result.scalar_one_or_none()

    if not user or user.reset_token_expires is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 재설정 링크입니다.")

    if datetime.utcnow() > user.reset_token_expires:
        raise HTTPException(status_code=400, detail="재설정 링크가 만료되었습니다. 다시 요청해주세요.")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 최소 8자 이상이어야 합니다.")

    user.hashed_password = hash_password(body.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.add(user)
    await db.commit()

    return {"message": "비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해주세요."}
