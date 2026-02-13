from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot

router = APIRouter(tags=["dashboard"])


@router.get("/snapshots")
async def list_snapshots(db: AsyncSession = Depends(get_db)):
    """List all snapshots ordered by created_at descending.

    Returns metadata only (no dashboard_data blob).
    """
    result = await db.execute(
        select(
            Snapshot.id,
            Snapshot.name,
            Snapshot.created_at,
            Snapshot.source_filename,
            Snapshot.ticker_count,
            Snapshot.date_count,
            Snapshot.industry_count,
        ).order_by(Snapshot.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source_filename": row.source_filename,
            "ticker_count": row.ticker_count,
            "date_count": row.date_count,
            "industry_count": row.industry_count,
        }
        for row in rows
    ]


@router.get("/dashboard-data")
async def get_latest_dashboard_data(db: AsyncSession = Depends(get_db)):
    """Return the latest snapshot's dashboard_data JSON."""
    result = await db.execute(
        select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return snapshot.dashboard_data


@router.get("/dashboard-data/{snapshot_id}")
async def get_dashboard_data_by_id(
    snapshot_id: int, db: AsyncSession = Depends(get_db)
):
    """Return a specific snapshot's dashboard_data by ID."""
    result = await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot.dashboard_data
