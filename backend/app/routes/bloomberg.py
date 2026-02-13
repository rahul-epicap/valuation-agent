from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot
from app.services.bloomberg_service import BloombergService

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
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Bloomberg fetch failed: {e}",
        )

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
