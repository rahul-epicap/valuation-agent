"""Ticker description management — fetch from Bloomberg, store in DB."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TickerDescription

if TYPE_CHECKING:
    from app.services.bloomberg_service import BloombergService

logger = logging.getLogger(__name__)


def _clean_ticker(bbg_ticker: str) -> str:
    """Strip ' US Equity' suffix to get the short ticker symbol."""
    s = bbg_ticker.strip()
    if s.endswith(" US Equity"):
        return s[: -len(" US Equity")].strip()
    return s


async def fetch_descriptions(
    bloomberg: BloombergService,
    db: AsyncSession,
    tickers: list[str] | None = None,
) -> dict[str, str]:
    """Fetch business descriptions from Bloomberg BDS and store in DB.

    Args:
        bloomberg: Bloomberg service instance.
        db: Async database session.
        tickers: Bloomberg-format tickers (e.g. 'AAPL US Equity').
            If None, uses bloomberg._tickers.

    Returns:
        {short_ticker: description} dict of successfully fetched descriptions.
    """
    ticker_universe = tickers or bloomberg.tickers
    result: dict[str, str] = {}

    for bbg_ticker in ticker_universe:
        short = _clean_ticker(bbg_ticker)
        description = None
        source_field = None

        # Try primary field first
        for field in ("CIE_DES_BULK", "LONG_COMP_DESC_BULK"):
            try:
                df = await asyncio.to_thread(
                    bloomberg._bds_sync,
                    bbg_ticker,
                    field,
                )
            except Exception:
                logger.debug(
                    "BDS %s failed for %s — trying next field", field, bbg_ticker
                )
                continue

            if df.empty:
                continue

            # Concatenate all rows into a single description string
            text_parts: list[str] = []
            for col in df.columns:
                for val in df[col]:
                    if val is not None and str(val).strip():
                        text_parts.append(str(val).strip())

            if text_parts:
                description = " ".join(text_parts)
                source_field = field
                break

        if not description:
            logger.debug("No description found for %s", bbg_ticker)
            continue

        result[short] = description

        # Upsert into DB
        existing = await db.execute(
            select(TickerDescription).where(TickerDescription.ticker == short)
        )
        row = existing.scalar_one_or_none()
        if row is None:
            db.add(
                TickerDescription(
                    ticker=short,
                    bbg_ticker=bbg_ticker,
                    description=description,
                    source_field=source_field,
                )
            )
        else:
            row.description = description
            row.source_field = source_field
            row.bbg_ticker = bbg_ticker

    await db.commit()
    logger.info("Fetched descriptions for %d tickers", len(result))
    return result


async def get_all_descriptions(db: AsyncSession) -> dict[str, str]:
    """Return {ticker: description} for all stored descriptions."""
    rows = await db.execute(select(TickerDescription))
    return {
        row.ticker: row.description for row in rows.scalars().all() if row.description
    }


async def get_unembedded_tickers(db: AsyncSession) -> list[TickerDescription]:
    """Return TickerDescription rows where embedded_at is NULL."""
    result = await db.execute(
        select(TickerDescription).where(
            TickerDescription.embedded_at.is_(None),
            TickerDescription.description.isnot(None),
        )
    )
    return list(result.scalars().all())
