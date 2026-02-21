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

# Both BDS fields to pull — concatenated for maximum description info
_DESC_FIELDS = ("CIE_DES_BULK", "LONG_COMP_DESC_BULK")


def _clean_ticker(bbg_ticker: str) -> str:
    """Strip ' US Equity' suffix to get the short ticker symbol."""
    s = bbg_ticker.strip()
    if s.endswith(" US Equity"):
        return s[: -len(" US Equity")].strip()
    return s


def _extract_text(df) -> str:
    """Extract text content from a Bloomberg BDS DataFrame."""
    parts: list[str] = []
    for col in df.columns:
        for val in df[col]:
            if val is not None and str(val).strip():
                parts.append(str(val).strip())
    return " ".join(parts)


async def fetch_descriptions(
    bloomberg: BloombergService,
    db: AsyncSession,
    tickers: list[str] | None = None,
) -> dict[str, str]:
    """Fetch business descriptions from Bloomberg BDS and store in DB.

    Pulls both CIE_DES_BULK (short company description) and
    LONG_COMP_DESC_BULK (long company description) and concatenates them
    for maximum context.

    Args:
        bloomberg: Bloomberg service instance.
        db: Async database session.
        tickers: Bloomberg-format tickers (e.g. 'AAPL US Equity').
            If None, uses bloomberg.tickers.

    Returns:
        {short_ticker: description} dict of successfully fetched descriptions.
    """
    ticker_universe = tickers or bloomberg.tickers
    result: dict[str, str] = {}
    total = len(ticker_universe)

    for idx, bbg_ticker in enumerate(ticker_universe):
        short = _clean_ticker(bbg_ticker)

        # Fetch both description fields and combine
        texts: list[str] = []
        source_fields: list[str] = []

        for field in _DESC_FIELDS:
            try:
                df = await asyncio.to_thread(
                    bloomberg.bds_sync,
                    bbg_ticker,
                    field,
                )
            except Exception:
                logger.debug("BDS %s failed for %s — skipping field", field, bbg_ticker)
                continue

            if df.empty:
                continue

            text = _extract_text(df)
            if text:
                texts.append(text)
                source_fields.append(field)

        if not texts:
            logger.debug("No description found for %s", bbg_ticker)
            continue

        # Combine all description texts, deduplicate if identical
        if len(texts) == 2 and texts[0] == texts[1]:
            description = texts[0]
        else:
            description = "\n\n".join(texts)

        source_field = "+".join(source_fields)
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
            # Reset embedded_at so re-embedding picks up the new text
            row.embedded_at = None

        # Periodic commit + log every 100 tickers
        if (idx + 1) % 100 == 0:
            await db.commit()
            logger.info(
                "Description fetch progress: %d / %d (%d found)",
                idx + 1,
                total,
                len(result),
            )

    await db.commit()
    logger.info("Fetched descriptions for %d / %d tickers", len(result), total)
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
