"""
자기소개서(이력서) API — 로그인한 계정에 저장해 다른 PC · 브라우저에서도 같은 자기소개서를 쓴다.

- GET    /resumes                 : 내 자기소개서 목록 (최신순)
- POST   /resumes                 : 새로 등록
- PUT    /resumes/{ref_id}        : 수정
- DELETE /resumes/{ref_id}        : 삭제 (이미 한 면접 기록은 남는다)
- POST   /resumes/import          : 이 브라우저에만 있던 자기소개서를 내 계정으로 옮기기 (예전 ID 유지, 이미 있는 ID는 건너뜀)
- POST   /resumes/parse-file      : 파일(PDF · HWP · HWPX · DOCX · TXT)을 읽어 작성 칸에 채울 내용을 돌려줌
                                   kind=posting(채용공고 → 제목 · 채용 정보 · 직무 수행 업무 · 인재상) / intro(이력서 · 자기소개서 → 자기소개서 내용)
- POST   /resumes/parse-text      : 붙여넣은 채용공고 글로 같은 일을 함
  (파일 · 글은 저장하지 않음, 화면에서 확인 후 '등록하기'를 눌러야 저장)

모두 본인 것만 보고 바꿀 수 있다 (다른 사람 ID를 넣으면 404).
"""
import asyncio
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.rate_limit import limiter
from core.security import get_current_user_id
from models.resume import Resume
from services.document import resume_parser
from services.document.resume_parser import DocumentError
from services.llm.llama_service import extract_company_job

logger = logging.getLogger(__name__)

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


ParseKind = Literal["posting", "intro"]
PASTE_MAX_CHARS = 20_000        # 붙여넣기 최대 글자 수 (채용공고는 길어야 수천 자)


class ParsedResume(BaseModel):
    kind: str                    # posting | intro
    title: str
    company_name: str
    job_title: str
    job_description: str
    ideal_candidate: str
    self_introduction: str
    truncated: bool              # 자기소개서가 3,000자를 넘어 앞부분만 넣었는지
    removed_personal: int        # 지운 전화번호 · 이메일 · 주민등록번호 개수


class ParseTextRequest(BaseModel):
    kind: ParseKind = "posting"
    text: str = Field(min_length=1, max_length=PASTE_MAX_CHARS)


async def _fields_from_text(text: str, kind: str, user_id: int) -> ParsedResume:
    prepared, _ = resume_parser.prepare(text)
    guess = {}
    if kind == "posting":
        found = resume_parser.posting_fields(prepared)
        if not found["company_name"] or not found["job_title"]:
            # 구역 제목이 없는 공고 — 모델이 찾되 원문에 그대로 있는 값만 (개인정보를 지운 글을 보냄)
            guess = await extract_company_job(resume_parser.clean_text(prepared))
    fields = resume_parser.build_fields("", text, guess, kind=kind)
    return ParsedResume(kind=kind, **fields)


@router.post("/parse-file", response_model=ParsedResume)
@limiter.limit("10/minute")
async def parse_resume_file(request: Request, file: UploadFile = File(...), kind: ParseKind = Form("intro"),
                            user_id: int = Depends(get_current_user_id)):
    data = await file.read(resume_parser.MAX_FILE_BYTES + 1)
    try:
        # 글자 추출은 CPU 작업이라 이벤트 루프를 막지 않게 스레드에서, 오래 걸리는 파일은 20초에 끊는다
        text = await asyncio.wait_for(asyncio.to_thread(resume_parser.extract_text, file.filename or "", data), 20)
        return await _fields_from_text(text, kind, user_id)
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except asyncio.TimeoutError:
        raise HTTPException(status_code=400, detail="파일을 읽는 데 너무 오래 걸립니다. 필요한 부분만 따로 저장해서 올려 주세요.")
    except Exception:
        # 내용은 개인정보라 남기지 않고 형식 · 크기만 기록
        logger.exception(f"파일 읽기 실패 (kind={kind}, user={user_id}, size={len(data)}, name_ext={(file.filename or '').rsplit('.', 1)[-1][:8]})")
        raise HTTPException(status_code=400, detail="파일을 읽지 못했습니다. 다른 형식(PDF · DOCX · HWPX)으로 저장해서 올려 주세요.")


@router.post("/parse-text", response_model=ParsedResume)
@limiter.limit("20/minute")
async def parse_resume_text(request: Request, body: ParseTextRequest, user_id: int = Depends(get_current_user_id)):
    try:
        return await _fields_from_text(body.text, body.kind, user_id)
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception(f"붙여넣은 글 읽기 실패 (kind={body.kind}, user={user_id}, chars={len(body.text)})")
        raise HTTPException(status_code=400, detail="내용을 읽지 못했습니다. 잠시 후 다시 시도해 주세요.")
