"""Description and similarity search endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import TickerDescription
from app.services import description_service, index_service, similarity_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["descriptions"])

# Bloomberg service reference — set by main.py lifespan
_bbg_service = None


def set_service(service: object) -> None:
    """Inject the Bloomberg service from main.py."""
    global _bbg_service
    _bbg_service = service


@router.post("/descriptions/fetch")
async def fetch_descriptions_endpoint(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Fetch business descriptions from Bloomberg for all tickers in the index universe."""
    if _bbg_service is None:
        raise HTTPException(
            status_code=503,
            detail="Bloomberg service unavailable — Bloomberg Terminal may not be running.",
        )

    # Use the full index universe (all current SPX + NDX members)
    universe_tickers = await index_service.get_all_current_tickers(db)
    if universe_tickers:
        # Convert short tickers to Bloomberg format
        bbg_tickers = [f"{t} US Equity" for t in universe_tickers]
        logger.info(
            "Fetching descriptions for %d tickers from index universe",
            len(bbg_tickers),
        )
    else:
        # Fallback to bloomberg service's default ticker list
        bbg_tickers = None
        logger.info("No index universe found, using default ticker list")

    result = await description_service.fetch_descriptions(
        _bbg_service, db, tickers=bbg_tickers
    )
    return {"status": "ok", "fetched_count": len(result)}


@router.get("/descriptions/{ticker}")
async def get_description(
    ticker: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get stored description for a ticker."""
    result = await db.execute(
        select(TickerDescription).where(TickerDescription.ticker == ticker)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Description for '{ticker}' not found"
        )

    return {
        "ticker": row.ticker,
        "bbg_ticker": row.bbg_ticker,
        "description": row.description,
        "source_field": row.source_field,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        "embedded_at": row.embedded_at.isoformat() if row.embedded_at else None,
    }


@router.post("/descriptions/sync-embeddings")
async def sync_embeddings_endpoint(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Embed all unembedded descriptions and upsert to TurboPuffer."""
    count = await similarity_service.sync_descriptions(db)
    return {"status": "ok", "synced_count": count}


class SimilaritySearchRequest(BaseModel):
    ticker: str | None = None
    text: str | None = None
    top_k: int = 20


@router.post("/similarity/search")
async def search_similar(
    body: SimilaritySearchRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Find similar stocks by ticker or free text."""
    if not body.ticker and not body.text:
        raise HTTPException(
            status_code=422,
            detail="Either 'ticker' or 'text' must be provided",
        )

    results = await similarity_service.find_similar(
        query_ticker=body.ticker,
        query_text=body.text,
        db=db,
        top_k=body.top_k,
    )
    return {"query_ticker": body.ticker, "query_text": body.text, "results": results}
