"""Index management endpoints — list, members, refresh, universe."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Index, IndexMembership
from app.services import index_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["indices"])

# Bloomberg service reference — set by main.py lifespan
_bbg_service = None


def set_service(service: object) -> None:
    """Inject the Bloomberg service from main.py."""
    global _bbg_service
    _bbg_service = service


@router.get("/indices")
async def list_indices(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """List configured indices with member counts."""
    indices_result = await db.execute(select(Index))
    indices = list(indices_result.scalars().all())

    result = []
    for idx in indices:
        # Count latest members
        max_date_result = await db.execute(
            select(sa_func.max(IndexMembership.as_of_date)).where(
                IndexMembership.index_id == idx.id
            )
        )
        max_date = max_date_result.scalar()
        member_count = 0
        if max_date:
            count_result = await db.execute(
                select(sa_func.count(IndexMembership.id)).where(
                    IndexMembership.index_id == idx.id,
                    IndexMembership.as_of_date == max_date,
                )
            )
            member_count = count_result.scalar() or 0

        result.append(
            {
                "id": idx.id,
                "bbg_ticker": idx.bbg_ticker,
                "short_name": idx.short_name,
                "display_name": idx.display_name,
                "member_count": member_count,
                "latest_as_of_date": max_date,
            }
        )

    return result


@router.get("/indices/{short_name}/members")
async def get_index_members(
    short_name: str,
    as_of_date: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Members of an index at the latest or specified as_of_date."""
    members = await index_service.get_current_members(db, short_name, as_of_date)
    if not members:
        # Check if index exists
        idx_result = await db.execute(
            select(Index).where(Index.short_name == short_name)
        )
        if idx_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=404, detail=f"Index '{short_name}' not found"
            )

    return {"short_name": short_name, "as_of_date": as_of_date, "members": members}


@router.post("/indices/refresh")
async def refresh_index_memberships(
    start_year: int = 2010,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger Bloomberg constituent refresh for all indices."""
    if _bbg_service is None:
        raise HTTPException(
            status_code=503,
            detail="Bloomberg service unavailable — Bloomberg Terminal may not be running.",
        )

    summary = await index_service.refresh_memberships(_bbg_service, db, start_year)
    return {"status": "ok", "memberships_added": summary}


class BatchRefreshRequest(BaseModel):
    short_names: list[str]
    current_only: bool = True
    start_year: int = 2010


@router.post("/indices/refresh-batch")
async def refresh_batch(
    body: BatchRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh memberships for a specific batch of indices."""
    if _bbg_service is None:
        raise HTTPException(
            status_code=503,
            detail="Bloomberg service unavailable.",
        )

    summary = await index_service.refresh_memberships_batch(
        _bbg_service, db, body.short_names, body.current_only, body.start_year
    )
    return {"status": "ok", "memberships_added": summary}


@router.post("/indices/seed")
async def seed_indices_endpoint(db: AsyncSession = Depends(get_db)) -> dict:
    """Re-seed indices from indices.json (adds new ones, updates existing)."""
    result = await index_service.seed_indices(db)
    return {"status": "ok", "indices_count": len(result)}


@router.get("/indices/universe")
async def get_universe(db: AsyncSession = Depends(get_db)) -> dict:
    """Full union ticker universe across all indices."""
    tickers = await index_service.get_all_current_tickers(db)
    return {"ticker_count": len(tickers), "tickers": tickers}


@router.get("/tickers/{ticker}/indices")
async def get_ticker_index_memberships(
    ticker: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Which indices a ticker belongs to."""
    indices = await index_service.get_ticker_indices(db, ticker)
    return {"ticker": ticker, "indices": indices}
