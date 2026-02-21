import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot

logger = logging.getLogger(__name__)

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


async def _enrich_with_indices(data: dict, db: AsyncSession) -> dict:
    """Enrich dashboard data with current index memberships."""
    from app.services.index_service import build_indices_map

    try:
        indices_map = await build_indices_map(db)
        if indices_map:
            data["indices"] = indices_map
    except Exception:
        logger.debug("Could not enrich with index data", exc_info=True)
    return data


@router.get("/dashboard-data")
async def get_latest_dashboard_data(db: AsyncSession = Depends(get_db)):
    """Return the latest snapshot's dashboard_data JSON, enriched with index memberships."""
    result = await db.execute(
        select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots found")
    data = dict(snapshot.dashboard_data)
    return await _enrich_with_indices(data, db)


@router.get("/dashboard-data/{snapshot_id}")
async def get_dashboard_data_by_id(
    snapshot_id: int, db: AsyncSession = Depends(get_db)
):
    """Return a specific snapshot's dashboard_data by ID, enriched with index memberships."""
    result = await db.execute(select(Snapshot).where(Snapshot.id == snapshot_id))
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    data = dict(snapshot.dashboard_data)
    return await _enrich_with_indices(data, db)


class SnapshotImportRequest(BaseModel):
    name: str
    dashboard_data: dict


@router.post("/snapshot/import")
async def import_snapshot(
    body: SnapshotImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import raw dashboard JSON as a new snapshot.

    Used by the daily update script to sync local data to production.
    """
    data = body.dashboard_data

    # Validate required top-level keys
    required_keys = {"dates", "tickers", "industries", "fm"}
    missing = required_keys - set(data.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"dashboard_data missing required keys: {sorted(missing)}",
        )

    ticker_count = len(data.get("tickers", []))
    date_count = len(data.get("dates", []))
    industry_count = len(set(data.get("industries", {}).values()))

    snapshot = Snapshot(
        name=body.name,
        dashboard_data=data,
        source_filename="imported",
        ticker_count=ticker_count,
        date_count=date_count,
        industry_count=industry_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    logger.info(
        "Imported snapshot id=%d: %d tickers, %d dates, %d industries",
        snapshot.id,
        ticker_count,
        date_count,
        industry_count,
    )

    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "source_filename": snapshot.source_filename,
        "ticker_count": ticker_count,
        "date_count": date_count,
        "industry_count": industry_count,
    }
