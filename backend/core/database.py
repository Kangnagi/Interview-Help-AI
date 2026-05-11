from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession   # 비동기 SQLAlchemy 핵심 컴포넌트
from sqlalchemy.orm import DeclarativeBase   # ORM 모델 베이스 클래스
from core.config import settings             # DB URL 등 설정값


# 비동기 DB 엔진 생성 — echo=True면 실행 SQL을 콘솔에 출력 (DEBUG 모드 디버깅용)
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,   # DEBUG 모드에서 SQL 로그 출력
    future=True,           # SQLAlchemy 2.0 스타일 API 사용
)

# 세션 팩토리 — 요청마다 새 AsyncSession 생성
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,   # commit 후에도 객체 속성 유효 유지 (lazy load 방지)
    class_=AsyncSession,      # 비동기 세션 클래스 사용
)


class Base(DeclarativeBase):
    # 모든 ORM 모델이 상속받는 베이스 클래스 — 테이블 메타데이터 등록
    pass


async def get_db() -> AsyncSession:
    """FastAPI Dependency — 각 HTTP 요청에 DB 세션 주입"""
    async with AsyncSessionLocal() as session:
        try:
            yield session               # 라우터 함수에 세션 전달
            await session.commit()      # 요청 처리 성공 시 자동 커밋
        except Exception:
            await session.rollback()    # 예외 발생 시 롤백으로 데이터 정합성 유지
            raise
        finally:
            await session.close()       # 항상 세션 반환 (커넥션 풀 반환)


async def init_db():
    """앱 시작 시 테이블 생성 — 없는 테이블만 생성, 기존 데이터 유지"""
    async with engine.begin() as conn:
        # ORM 모델 임포트 → Base.metadata에 테이블 정의 등록 (noqa: 사용 안 해도 import 필요)
        from models import user, interview, analysis  # noqa
        await conn.run_sync(Base.metadata.create_all)   # 동기 DDL을 비동기 컨텍스트에서 실행
