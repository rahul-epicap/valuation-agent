import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot
from app.services.bloomberg_service import BloombergService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bloomberg"])

# Singleton set by main.py lifespan
_service: BloombergService | None = None


def set_service(service: BloombergService) -> None:
    """Called by main.py to inject the shared BloombergService instance."""
    global _service  # noqa: PLW0603
    _service = service


def _get_service() -> BloombergService:
    if _service is None:
        raise HTTPException(
            status_code=503,
            detail="Bloomberg service is not available. Ensure Bloomberg Terminal is running.",
        )
    return _service


class BloombergFetchRequest(BaseModel):
    name: str | None = None
    start_date: str = "2015-01-01"
    end_date: str | None = None
    periodicity: Literal["DAILY", "WEEKLY", "MONTHLY"] = "DAILY"

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format '{v}', expected YYYY-MM-DD")
        return v


class BloombergUpdateRequest(BaseModel):
    lookback_days: int = 5
    periodicity: Literal["DAILY", "WEEKLY", "MONTHLY"] = "DAILY"
    name: str | None = None


@router.post("/bloomberg/fetch")
async def fetch_bloomberg_data(
    body: BloombergFetchRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Fetch data from Bloomberg DAPI and create a new snapshot."""
    service = _get_service()

    if body is None:
        body = BloombergFetchRequest()

    # Fetch all metrics from Bloomberg
    try:
        dashboard_data = await service.fetch_all(
            start_date=body.start_date,
            end_date=body.end_date,
            periodicity=body.periodicity,
        )
    except Exception as e:
        logger.exception("Bloomberg fetch failed")
        raise HTTPException(
            status_code=502,
            detail=f"Bloomberg fetch failed: {e}",
        ) from e

    # Generate name if not provided
    name = body.name
    if not name:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        name = f"Bloomberg Fetch — {timestamp}"

    # Compute summary stats
    ticker_count = len(dashboard_data.get("tickers", []))
    date_count = len(dashboard_data.get("dates", []))
    industry_count = len(set(dashboard_data.get("industries", {}).values()))

    # Create snapshot (same pattern as upload.py)
    snapshot = Snapshot(
        name=name,
        dashboard_data=dashboard_data,
        source_filename="bloomberg-dapi",
        ticker_count=ticker_count,
        date_count=date_count,
        industry_count=industry_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "source_filename": snapshot.source_filename,
        "ticker_count": ticker_count,
        "date_count": date_count,
        "industry_count": industry_count,
    }


@router.post("/bloomberg/update")
async def update_bloomberg_data(
    body: BloombergUpdateRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Incremental Bloomberg update: fetch only recent data and merge with latest snapshot."""
    service = _get_service()

    if body is None:
        body = BloombergUpdateRequest()

    # Load the latest snapshot as the base for merging
    from sqlalchemy import select

    result = await db.execute(
        select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
    )
    latest_snapshot = result.scalar_one_or_none()
    existing_data = latest_snapshot.dashboard_data if latest_snapshot else {}

    try:
        merged_data = await service.fetch_incremental(
            existing_data=existing_data,
            lookback_days=body.lookback_days,
            periodicity=body.periodicity,
        )
    except Exception as e:
        logger.exception("Bloomberg incremental fetch failed")
        raise HTTPException(
            status_code=502,
            detail=f"Bloomberg incremental fetch failed: {e}",
        ) from e

    # Skip snapshot creation if no new trading days were added
    existing_dates = existing_data.get("dates", [])
    merged_dates = merged_data.get("dates", [])
    if merged_dates == existing_dates:
        logger.info("No new trading days — skipping snapshot creation")
        return {
            "id": latest_snapshot.id if latest_snapshot else None,
            "skipped": True,
            "message": "No new trading days since last snapshot",
            "date_count": len(existing_dates),
        }

    # Generate name
    name = body.name
    if not name:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        name = f"Bloomberg Update — {timestamp}"

    ticker_count = len(merged_data.get("tickers", []))
    date_count = len(merged_dates)
    industry_count = len(set(merged_data.get("industries", {}).values()))

    snapshot = Snapshot(
        name=name,
        dashboard_data=merged_data,
        source_filename="bloomberg-incremental",
        ticker_count=ticker_count,
        date_count=date_count,
        industry_count=industry_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    prev_date_count = len(existing_dates)
    logger.info(
        "Incremental snapshot created: id=%d, dates %d→%d",
        snapshot.id,
        prev_date_count,
        date_count,
    )

    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "source_filename": snapshot.source_filename,
        "ticker_count": ticker_count,
        "date_count": date_count,
        "industry_count": industry_count,
        "previous_date_count": prev_date_count,
        "skipped": False,
    }
