"""Statistics API for ECharts visualization."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.record import OperationRecord
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/stats", tags=["Statistics"], dependencies=[Depends(get_current_user)])


@router.get("/detections")
async def detection_stats(
    minutes: int = Query(default=60, le=1440),
    db: Session = Depends(get_db),
):
    """Detection event counts grouped by time bucket and class."""
    since = datetime.utcnow() - timedelta(minutes=minutes)

    # Group by status and step
    rows = (
        db.query(
            OperationRecord.status,
            OperationRecord.step_name,
            func.count(OperationRecord.id).label("count"),
        )
        .filter(OperationRecord.timestamp >= since)
        .group_by(OperationRecord.status, OperationRecord.step_name)
        .all()
    )

    return {
        "since": since.isoformat(),
        "data": [
            {"status": r.status, "step_name": r.step_name, "count": r.count}
            for r in rows
        ],
    }


@router.get("/timeline")
async def detection_timeline(
    minutes: int = Query(default=60, le=1440),
    bucket_seconds: int = Query(default=60, le=600),
    db: Session = Depends(get_db),
):
    """Detection events over time, bucketed for chart display."""
    since = datetime.utcnow() - timedelta(minutes=minutes)

    records = (
        db.query(OperationRecord)
        .filter(OperationRecord.timestamp >= since)
        .order_by(OperationRecord.timestamp.asc())
        .all()
    )

    # Manual bucketing (SQLite doesn't have good date truncation)
    buckets: dict[str, dict] = {}
    for r in records:
        ts = r.timestamp
        # Round to bucket
        bucket_ts = ts.replace(second=(ts.second // bucket_seconds) * bucket_seconds, microsecond=0)
        key = bucket_ts.isoformat()
        if key not in buckets:
            buckets[key] = {"time": key, "total": 0}
        buckets[key]["total"] += 1
        # Count by status
        status_key = f"{r.status}_count"
        buckets[key][status_key] = buckets[key].get(status_key, 0) + 1

    return {
        "since": since.isoformat(),
        "bucket_seconds": bucket_seconds,
        "timeline": list(buckets.values()),
    }


@router.get("/sop/{sop_id}/completion")
async def sop_completion_stats(
    sop_id: str,
    db: Session = Depends(get_db),
):
    """SOP completion statistics."""
    total = db.query(func.count(OperationRecord.id)).filter(
        OperationRecord.sop_id == sop_id
    ).scalar() or 0

    completed = db.query(func.count(OperationRecord.id)).filter(
        OperationRecord.sop_id == sop_id,
        OperationRecord.status == "completed",
    ).scalar() or 0

    errors = db.query(func.count(OperationRecord.id)).filter(
        OperationRecord.sop_id == sop_id,
        OperationRecord.status == "error",
    ).scalar() or 0

    timeouts = db.query(func.count(OperationRecord.id)).filter(
        OperationRecord.sop_id == sop_id,
        OperationRecord.status == "timeout",
    ).scalar() or 0

    # Average confidence
    avg_conf = db.query(func.avg(OperationRecord.confidence)).filter(
        OperationRecord.sop_id == sop_id,
        OperationRecord.status == "detected",
    ).scalar() or 0

    return {
        "sop_id": sop_id,
        "total_events": total,
        "completed": completed,
        "errors": errors,
        "timeouts": timeouts,
        "avg_confidence": round(float(avg_conf), 3),
        "completion_rate": round(completed / total, 3) if total > 0 else 0,
    }


@router.get("/summary")
async def overall_summary(db: Session = Depends(get_db)):
    """Overall system statistics summary."""
    total = db.query(func.count(OperationRecord.id)).scalar() or 0
    unique_sops = db.query(func.count(func.distinct(OperationRecord.sop_id))).scalar() or 0

    # Status breakdown
    status_counts = (
        db.query(OperationRecord.status, func.count(OperationRecord.id))
        .group_by(OperationRecord.status)
        .all()
    )

    return {
        "total_events": total,
        "unique_sops": unique_sops,
        "status_breakdown": {r[0]: r[1] for r in status_counts},
    }
