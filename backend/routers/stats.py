from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from core.security import get_current_user_id
from models.interview import Interview, InterviewStatus
from models.analysis import Analysis

router = APIRouter(prefix="/stats", tags=["통계"])


@router.get("/dashboard")
async def get_dashboard_stats(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # 완료된 면접 + 분석 조인
    result = await db.execute(
        select(Interview, Analysis)
        .outerjoin(Analysis, Analysis.interview_id == Interview.id)
        .where(
            Interview.user_id == user_id,
            Interview.status == InterviewStatus.COMPLETED,
        )
        .order_by(Interview.created_at.asc())
    )
    rows = result.all()

    trend = []
    for iv, an in rows:
        if an and an.total_score is not None:
            trend.append({
                "interview_id": iv.id,
                "date": iv.created_at.strftime("%m/%d"),
                "total_score":       round(an.total_score, 1),
                "content_score":     round(an.content_score, 1) if an.content_score else None,
                "speech_score":      round(an.speech_score, 1) if an.speech_score else None,
                "posture_score":     round(an.posture_score, 1) if an.posture_score else None,
                "eye_contact_score": round(an.eye_contact_score, 1) if an.eye_contact_score else None,
            })

    def safe_avg(values):
        v = [x for x in values if x is not None]
        return round(sum(v) / len(v), 1) if v else None

    avg = {
        "total":       safe_avg([t["total_score"] for t in trend]),
        "content":     safe_avg([t["content_score"] for t in trend]),
        "speech":      safe_avg([t["speech_score"] for t in trend]),
        "posture":     safe_avg([t["posture_score"] for t in trend]),
        "eye_contact": safe_avg([t["eye_contact_score"] for t in trend]),
    }

    total_iv = await db.execute(
        select(func.count()).where(Interview.user_id == user_id)
    )

    return {
        "total_interviews": total_iv.scalar(),
        "completed_interviews": len(rows),
        "analyzed_count": len(trend),
        "averages": avg,
        "trend": trend,
    }
