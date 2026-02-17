"""
Index constituent discovery via Bloomberg BDS.

Uses INDX_MWEIGHT_HIST to fetch historical membership for SPX Index and
NDX Index at quarterly intervals, building the full universe of tickers
that have ever been in either index since a given start year.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.bloomberg_service import BloombergService

logger = logging.getLogger(__name__)

# Indices to query for constituent membership
_INDICES = ["SPX Index", "NDX Index"]


def generate_quarterly_dates(
    start_year: int = 2010,
    end_date: date | None = None,
) -> list[date]:
    """Generate quarter-start dates from start_year through end_date.

    Returns dates for Jan 1, Apr 1, Jul 1, Oct 1 of each year.
    """
    if end_date is None:
        end_date = date.today()

    dates: list[date] = []
    for year in range(start_year, end_date.year + 1):
        for month in (1, 4, 7, 10):
            d = date(year, month, 1)
            if d <= end_date:
                dates.append(d)

    return dates


# Known US exchange codes returned by Bloomberg BDS
_US_EXCHANGES = {"US", "UW", "UN", "UA", "UP", "UR", "UF"}


def _normalize_ticker(raw: str) -> str:
    """Normalize a ticker to 'XXXX US Equity' format.

    BDS returns tickers as 'AAPL UW' or 'AAPL US' etc.
    All SPX/NDX constituents are US-listed, so we normalize the exchange
    code to 'US Equity'.  Returns empty string for invalid input.
    """
    raw = raw.strip()
    if not raw or raw.lower() == "nan":
        return ""

    # Already in full format (e.g. "AAPL UW Equity")
    if raw.endswith(" Equity"):
        parts = raw.rsplit(" ", 2)
        if len(parts) == 3:
            return f"{parts[0]} US Equity"
        return raw

    # Has exchange code like "AAPL UW" or "AAPL US"
    parts = raw.split()
    if len(parts) >= 2:
        exchange = parts[-1]
        ticker_sym = " ".join(parts[:-1])
        if exchange not in _US_EXCHANGES:
            logger.debug(
                "Unexpected exchange code '%s' for ticker '%s', normalizing to US Equity",
                exchange,
                raw,
            )
        return f"{ticker_sym} US Equity"

    # Just a bare ticker
    return f"{raw} US Equity"


async def fetch_all_constituents(
    service: BloombergService,
    start_year: int = 2010,
) -> tuple[list[str], dict[str, list[str]]]:
    """Discover all unique tickers from SPX and NDX historical membership.

    Args:
        service: A BloombergService instance with a _bds_sync() method.
        start_year: First year for quarterly snapshots.

    Returns:
        (unique_tickers, membership_log) where:
          - unique_tickers: sorted deduplicated list of 'XXXX US Equity' strings
          - membership_log: {index_date_key: [tickers]} for auditing
    """
    quarterly_dates = generate_quarterly_dates(start_year)
    all_tickers: set[str] = set()
    membership_log: dict[str, list[str]] = {}

    logger.info(
        "Fetching constituents for %d quarterly dates × %d indices",
        len(quarterly_dates),
        len(_INDICES),
    )

    for i, qdate in enumerate(quarterly_dates):
        date_str = qdate.strftime("%Y%m%d")

        for index in _INDICES:
            log_key = f"{index}@{qdate.isoformat()}"
            try:
                df = await asyncio.to_thread(
                    service._bds_sync,
                    index,
                    "INDX_MWEIGHT_HIST",
                    overrides=[("END_DATE_OVERRIDE", date_str)],
                )
            except Exception:
                logger.exception("BDS failed for %s at %s — skipping", index, date_str)
                membership_log[log_key] = []
                continue

            if df.empty:
                logger.warning("BDS returned empty for %s at %s", index, date_str)
                membership_log[log_key] = []
                continue

            # Find the ticker column — common names from Bloomberg BDS
            ticker_col = None
            for col in df.columns:
                col_lower = str(col).lower()
                if "ticker" in col_lower or "member" in col_lower:
                    ticker_col = col
                    break

            if ticker_col is None:
                # Fallback: use the first string column
                for col in df.columns:
                    sample = df[col].iloc[0] if len(df) > 0 else None
                    if isinstance(sample, str):
                        ticker_col = col
                        break

            if ticker_col is None:
                logger.warning(
                    "BDS result for %s has no ticker column. Columns: %s",
                    log_key,
                    list(df.columns),
                )
                membership_log[log_key] = []
                continue

            tickers = [
                t
                for v in df[ticker_col]
                if v is not None and str(v).strip()
                for t in [_normalize_ticker(str(v))]
                if t  # filter out empty results from NaN/invalid values
            ]
            all_tickers.update(tickers)
            membership_log[log_key] = tickers

        if (i + 1) % 10 == 0:
            logger.info(
                "Constituent discovery progress: %d/%d quarters, %d unique tickers so far",
                i + 1,
                len(quarterly_dates),
                len(all_tickers),
            )

    unique_sorted = sorted(all_tickers)
    logger.info(
        "Constituent discovery complete: %d unique tickers from %d quarterly snapshots",
        len(unique_sorted),
        len(quarterly_dates),
    )

    return unique_sorted, membership_log
