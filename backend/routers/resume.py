"""
자기소개서(이력서) API — 로그인한 계정에 저장해 다른 PC · 브라우저에서도 같은 자기소개서를 쓴다.

- GET    /resumes                 : 내 자기소개서 목록 (최신순)
- POST   /resumes                 : 새로 등록
- PUT    /resumes/{ref_id}        : 수정
- DELETE /resumes/{ref_id}        : 삭제 (이미 한 면접 기록은 남는다)
- POST   /resumes/import          : 이 브라우저에만 있던 자기소개서를 내 계정으로 옮기기 (예전 ID 유지, 이미 있는 ID는 건너뜀)

모두 본인 것만 보고 바꿀 수 있다 (다른 사람 ID를 넣으면 404).
"""
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user_id
from models.resume import Resume

router = APIRouter(prefix="/resumes", tags=["자기소개서"])

MAX_RESUMES_PER_USER = 100      # 계정당 최대 개수 (무한정 쌓이지 않게)
SELF_INTRO_MAX = 3000           # 질문 생성에 쓰는 길이와 같음 (llama_service.SELF_INTRO_MAX)


# ── 스키마 ───────────────────────────────────────────────────────────────────
class ResumeFields(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    company_name: Optional[str] = Field(default=None, max_length=200)
    job_title: Optional[str] = Field(default=None, max_length=200)
    job_description: Optional[str] = Field(default=None, max_length=5000)
    ideal_candidate: Optional[str] = Field(default=None, max_length=3000)
    self_introduction: Optional[str] = Field(default=None, max_length=SELF_INTRO_MAX)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("제목을 입력해주세요")
        return v


class ResumeImportItem(ResumeFields):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")   # 브라우저에 있던 예전 ID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ResumeImportRequest(BaseModel):
    resumes: List[ResumeImportItem] = Field(max_length=MAX_RESUMES_PER_USER)


class ResumeResponse(BaseModel):
    id: str                       # = ref_id (화면 주소 · 면접 기록 연결에 쓰는 ID)
    title: str
    company_name: Optional[str]
    job_title: Optional[str]
    job_description: Optional[str]
    ideal_candidate: Optional[str]
    self_introduction: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class ResumeImportResponse(BaseModel):
    imported: int
    skipped: int


def _to_response(r: Resume) -> ResumeResponse:
    return ResumeResponse(
        id=r.ref_id, title=r.title, company_name=r.company_name, job_title=r.job_title,
        job_description=r.job_description, ideal_candidate=r.ideal_candidate,
        self_introduction=r.self_introduction, created_at=r.created_at, updated_at=r.updated_at,
    )


def _naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


async def _count(db: AsyncSession, user_id: int) -> int:
    return (await db.execute(select(func.count()).select_from(Resume).where(Resume.user_id == user_id))).scalar_one()


async def _get_own(db: AsyncSession, user_id: int, ref_id: str) -> Resume:
    r = (await db.execute(
        select(Resume).where(Resume.user_id == user_id, Resume.ref_id == ref_id)
    )).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="자기소개서를 찾을 수 없습니다")
    return r


# ── API ──────────────────────────────────────────────────────────────────────
@router.get("", response_model=List[ResumeResponse])
async def list_resumes(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc(), Resume.id.desc())
    )).scalars().all()
    return [_to_response(r) for r in rows]


@router.post("", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def create_resume(body: ResumeFields, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    if await _count(db, user_id) >= MAX_RESUMES_PER_USER:
        raise HTTPException(status_code=400, detail=f"자기소개서는 최대 {MAX_RESUMES_PER_USER}개까지 저장할 수 있습니다")
    r = Resume(user_id=user_id, ref_id=secrets.token_hex(8), **body.model_dump())
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return _to_response(r)


@router.put("/{ref_id}", response_model=ResumeResponse)
async def update_resume(ref_id: str, body: ResumeFields, user_id: int = Depends(get_current_user_id),
                        db: AsyncSession = Depends(get_db)):
    r = await _get_own(db, user_id, ref_id)
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    r.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(r)
    return _to_response(r)


@router.delete("/{ref_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(ref_id: str, user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    r = await _get_own(db, user_id, ref_id)
    await db.delete(r)
    await db.commit()


@router.post("/import", response_model=ResumeImportResponse)
async def import_resumes(body: ResumeImportRequest, user_id: int = Depends(get_current_user_id),
                         db: AsyncSession = Depends(get_db)):
    existing = set((await db.execute(select(Resume.ref_id).where(Resume.user_id == user_id))).scalars().all())
    room = MAX_RESUMES_PER_USER - len(existing)
    imported = skipped = 0
    now = datetime.utcnow()
    for item in body.resumes:
        if item.id in existing or imported >= room:
            skipped += 1
            continue
        fields = item.model_dump(exclude={"id", "created_at", "updated_at"})
        # 시각은 시간대 없는 UTC로 저장 (다른 테이블과 같은 방식)
        created = _naive_utc(item.created_at) or now
        updated = _naive_utc(item.updated_at) or created
        db.add(Resume(user_id=user_id, ref_id=item.id, created_at=created, updated_at=updated, **fields))
        existing.add(item.id)
        imported += 1
    await db.commit()
    return ResumeImportResponse(imported=imported, skipped=skipped)
