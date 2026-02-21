"""Index management service — seeding, membership refresh, and lookups."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Index, IndexMembership

if TYPE_CHECKING:
    from app.services.bloomberg_service import BloombergService

logger = logging.getLogger(__name__)

_INDICES_PATH = Path(__file__).resolve().parent.parent.parent / "indices.json"

# Known US exchange codes returned by Bloomberg BDS
_US_EXCHANGES = {"US", "UW", "UN", "UA", "UP", "UR", "UF"}


def _normalize_ticker(raw: str) -> str:
    """Normalize a ticker to 'XXXX US Equity' format."""
    raw = raw.strip()
    if not raw or raw.lower() == "nan":
        return ""
    if raw.endswith(" Equity"):
        parts = raw.rsplit(" ", 2)
        if len(parts) == 3:
            return f"{parts[0]} US Equity"
        return raw
    parts = raw.split()
    if len(parts) >= 2:
        ticker_sym = " ".join(parts[:-1])
        return f"{ticker_sym} US Equity"
    return f"{raw} US Equity"


def _clean_ticker(bbg_ticker: str) -> str:
    """Strip ' US Equity' suffix to get the short ticker symbol."""
    s = bbg_ticker.strip()
    if s.endswith(" US Equity"):
        return s[: -len(" US Equity")].strip()
    return s


def _generate_quarterly_dates(
    start_year: int = 2010,
    end_date: date | None = None,
) -> list[date]:
    """Generate quarter-start dates from start_year through end_date."""
    if end_date is None:
        end_date = date.today()
    dates: list[date] = []
    for year in range(start_year, end_date.year + 1):
        for month in (1, 4, 7, 10):
            d = date(year, month, 1)
            if d <= end_date:
                dates.append(d)
    return dates


def _parse_membership_df(df: pd.DataFrame) -> list[tuple[str, str, float | None]]:
    """Parse a BDS membership DataFrame into [(short_ticker, bbg_ticker, weight), ...].

    Shared helper used by both refresh_memberships and refresh_memberships_batch.
    """
    # Find ticker and weight columns
    ticker_col = None
    weight_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if "ticker" in col_lower or "member" in col_lower:
            ticker_col = col
        elif "weight" in col_lower or "percent" in col_lower:
            weight_col = col

    if ticker_col is None:
        for col in df.columns:
            sample = df[col].iloc[0] if len(df) > 0 else None
            if isinstance(sample, str):
                ticker_col = col
                break

    if ticker_col is None:
        return []

    results: list[tuple[str, str, float | None]] = []
    for _, row in df.iterrows():
        raw = row[ticker_col]
        if raw is None or not str(raw).strip():
            continue
        bbg = _normalize_ticker(str(raw))
        if not bbg:
            continue
        short = _clean_ticker(bbg)

        weight = None
        if weight_col is not None:
            try:
                weight = float(row[weight_col])
            except (ValueError, TypeError):
                pass

        results.append((short, bbg, weight))

    return results


async def _upsert_memberships(
    db: AsyncSession,
    index_id: int,
    as_of: str,
    members: list[tuple[str, str, float | None]],
) -> int:
    """Upsert membership rows, returning the count of new rows added."""
    if not members:
        return 0

    # Batch-check existing memberships
    tickers_in_batch = [m[0] for m in members]
    existing_result = await db.execute(
        select(IndexMembership.ticker).where(
            IndexMembership.index_id == index_id,
            IndexMembership.as_of_date == as_of,
            IndexMembership.ticker.in_(tickers_in_batch),
        )
    )
    existing_tickers = {row[0] for row in existing_result.all()}

    count = 0
    for short, bbg, weight in members:
        if short not in existing_tickers:
            db.add(
                IndexMembership(
                    index_id=index_id,
                    ticker=short,
                    bbg_ticker=bbg,
                    as_of_date=as_of,
                    weight=weight,
                )
            )
            count += 1

    return count


async def seed_indices(db: AsyncSession) -> list[Index]:
    """Load indices.json and upsert into the indices table."""
    with open(_INDICES_PATH) as f:
        index_configs = json.load(f)

    result: list[Index] = []
    for cfg in index_configs:
        existing = await db.execute(
            select(Index).where(Index.bbg_ticker == cfg["bbg_ticker"])
        )
        row = existing.scalar_one_or_none()
        if row is None:
            row = Index(
                bbg_ticker=cfg["bbg_ticker"],
                short_name=cfg["short_name"],
                display_name=cfg["display_name"],
            )
            db.add(row)
        else:
            row.short_name = cfg["short_name"]
            row.display_name = cfg["display_name"]
        result.append(row)

    await db.commit()
    logger.info("Seeded %d indices", len(result))
    return result


async def _fetch_and_upsert_memberships(
    bloomberg: BloombergService,
    db: AsyncSession,
    idx: Index,
    dates_to_fetch: list[date],
) -> int:
    """Fetch memberships for a single index across given dates. Returns new row count."""
    count = 0
    for qdate in dates_to_fetch:
        date_str = qdate.strftime("%Y%m%d")
        as_of = qdate.isoformat()

        try:
            df = await asyncio.to_thread(
                bloomberg.bds_sync,
                idx.bbg_ticker,
                "INDX_MWEIGHT_HIST",
                overrides=[("END_DATE_OVERRIDE", date_str)],
            )
        except Exception:
            logger.debug("BDS failed for %s at %s — skipping", idx.bbg_ticker, date_str)
            continue

        if df.empty:
            continue

        members = _parse_membership_df(df)
        count += await _upsert_memberships(db, idx.id, as_of, members)

    return count


async def refresh_memberships(
    bloomberg: BloombergService,
    db: AsyncSession,
    start_year: int = 2010,
) -> dict[str, int]:
    """For each index, fetch historical constituents and persist memberships.

    Returns {index_short_name: total_memberships_stored}.
    """
    indices_result = await db.execute(select(Index))
    indices = list(indices_result.scalars().all())
    quarterly_dates = _generate_quarterly_dates(start_year)
    summary: dict[str, int] = {}

    for idx in indices:
        count = await _fetch_and_upsert_memberships(bloomberg, db, idx, quarterly_dates)
        await db.commit()
        summary[idx.short_name] = count
        logger.info("Stored %d memberships for %s", count, idx.short_name)

    return summary


async def refresh_memberships_batch(
    bloomberg: BloombergService,
    db: AsyncSession,
    short_names: list[str],
    current_only: bool = True,
    start_year: int = 2010,
) -> dict[str, int]:
    """Refresh memberships for a specific set of indices.

    Args:
        bloomberg: Bloomberg service instance.
        db: Async database session.
        short_names: List of index short_names to refresh.
        current_only: If True, only fetch current members (no history).
        start_year: Start year for historical refresh (ignored if current_only).

    Returns {index_short_name: memberships_stored}.
    """
    summary: dict[str, int] = {}

    for sn in short_names:
        idx_result = await db.execute(select(Index).where(Index.short_name == sn))
        idx = idx_result.scalar_one_or_none()
        if idx is None:
            logger.warning("Index '%s' not found in DB — skipping", sn)
            summary[sn] = -1
            continue

        if current_only:
            dates_to_fetch = [date.today()]
        else:
            dates_to_fetch = _generate_quarterly_dates(start_year)

        count = await _fetch_and_upsert_memberships(bloomberg, db, idx, dates_to_fetch)
        await db.commit()
        summary[sn] = count
        logger.info("Stored %d memberships for %s", count, sn)

    return summary


# ---------------------------------------------------------------------------
# Subquery for latest as_of_date per index (used by all lookup functions)
# ---------------------------------------------------------------------------
def _latest_date_subquery():
    """Subquery: (index_id, max_as_of_date) for each index."""
    return (
        select(
            IndexMembership.index_id,
            sa_func.max(IndexMembership.as_of_date).label("max_date"),
        )
        .group_by(IndexMembership.index_id)
        .subquery("latest_dates")
    )


async def get_current_members(
    db: AsyncSession,
    index_short_name: str,
    as_of_date: str | None = None,
) -> list[str]:
    """Get members of an index at the latest (or specified) as_of_date."""
    idx_result = await db.execute(
        select(Index).where(Index.short_name == index_short_name)
    )
    idx = idx_result.scalar_one_or_none()
    if idx is None:
        return []

    if as_of_date is None:
        max_date_result = await db.execute(
            select(sa_func.max(IndexMembership.as_of_date)).where(
                IndexMembership.index_id == idx.id
            )
        )
        as_of_date = max_date_result.scalar()
        if as_of_date is None:
            return []

    result = await db.execute(
        select(IndexMembership.ticker).where(
            IndexMembership.index_id == idx.id,
            IndexMembership.as_of_date == as_of_date,
        )
    )
    return [row[0] for row in result.all()]


async def get_all_current_tickers(db: AsyncSession) -> list[str]:
    """Union of all index members at their latest as_of_date (single query)."""
    ld = _latest_date_subquery()

    result = await db.execute(
        select(IndexMembership.ticker)
        .join(
            ld,
            (IndexMembership.index_id == ld.c.index_id)
            & (IndexMembership.as_of_date == ld.c.max_date),
        )
        .distinct()
    )
    return sorted(row[0] for row in result.all())


async def get_ticker_indices(db: AsyncSession, ticker: str) -> list[str]:
    """Which indices a ticker belongs to (at latest membership date, single query)."""
    ld = _latest_date_subquery()

    result = await db.execute(
        select(Index.short_name)
        .join(IndexMembership, Index.id == IndexMembership.index_id)
        .join(
            ld,
            (IndexMembership.index_id == ld.c.index_id)
            & (IndexMembership.as_of_date == ld.c.max_date),
        )
        .where(IndexMembership.ticker == ticker)
    )
    return [row[0] for row in result.all()]


async def build_indices_map(db: AsyncSession) -> dict[str, list[str]]:
    """Build {ticker: [index_short_names]} for all current members (single query)."""
    ld = _latest_date_subquery()

    result = await db.execute(
        select(IndexMembership.ticker, Index.short_name)
        .join(Index, Index.id == IndexMembership.index_id)
        .join(
            ld,
            (IndexMembership.index_id == ld.c.index_id)
            & (IndexMembership.as_of_date == ld.c.max_date),
        )
    )

    ticker_map: dict[str, list[str]] = {}
    for ticker, short_name in result.all():
        ticker_map.setdefault(ticker, []).append(short_name)

    return ticker_map
