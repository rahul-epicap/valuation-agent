"""Backfill ISINs for all tickers in ticker_descriptions.

Connects to Bloomberg Terminal + production PostgreSQL. Fetches ID_ISIN
via BDP for every ticker that has isin IS NULL and upserts the values.
Also creates rows for tickers in the universe that lack a ticker_descriptions
entry entirely.

Usage:
  python scripts/fetch_isins.py
  python scripts/fetch_isins.py --database-url "postgresql://user:pass@host:5432/db"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_filename = f"fetch_isins_{datetime.now():%Y%m%d_%H%M}.log"
log_path = LOG_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("fetch_isins")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill ISINs for tickers in ticker_descriptions"
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Override DATABASE_URL (injected before app imports)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch ISINs but don't write to DB",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # Inject DATABASE_URL before importing app modules
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
        logger.info("DATABASE_URL overridden from CLI arg")

    # Add backend/ to sys.path so app.* imports work
    backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Change cwd to backend/ so pydantic-settings reads backend/.env
    os.chdir(backend_dir)

    # Deferred imports
    from sqlalchemy import select, text

    from app.db import AsyncSessionLocal, engine
    from app.models import TickerDescription
    from app.services.bloomberg_service import BloombergService, _clean_ticker

    logger.info("=" * 60)
    logger.info("ISIN backfill started")
    logger.info("Dry run: %s", args.dry_run)
    logger.info("=" * 60)

    bloomberg: BloombergService | None = None

    try:
        # Step 1: Add isin column if missing (create_all won't add to existing tables)
        logger.info("Step 1: Ensuring isin column exists")
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "ALTER TABLE ticker_descriptions "
                    "ADD COLUMN IF NOT EXISTS isin VARCHAR(20)"
                )
            )
        logger.info("Column check OK")

        # Step 2: Start Bloomberg
        logger.info("Step 2: Starting Bloomberg session")
        bloomberg = BloombergService()
        bloomberg.start()

        # Step 3: Find tickers needing ISINs
        logger.info("Step 3: Finding tickers with missing ISINs")
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TickerDescription.ticker, TickerDescription.bbg_ticker).where(
                    TickerDescription.isin.is_(None)
                )
            )
            missing_rows = result.all()

        if not missing_rows:
            logger.info("All tickers already have ISINs -- nothing to do")
            return

        missing_bbg = [row.bbg_ticker for row in missing_rows]
        logger.info("%d tickers need ISINs", len(missing_bbg))

        # Step 4: Fetch ISINs from Bloomberg
        logger.info("Step 4: Fetching ISINs from Bloomberg")
        isins = await bloomberg.fetch_isins(missing_bbg)
        logger.info("Bloomberg returned ISINs for %d tickers", len(isins))

        if not isins:
            logger.info("No ISINs returned -- done")
            return

        if args.dry_run:
            for bbg, isin in sorted(isins.items()):
                logger.info("  %s -> %s", bbg, isin)
            logger.info("DRY RUN -- no DB writes")
            return

        # Step 5: Upsert ISINs into ticker_descriptions
        logger.info("Step 5: Writing ISINs to DB")
        written = 0
        created = 0
        existing_tickers = {row.ticker for row in missing_rows}

        async with AsyncSessionLocal() as db:
            for bbg_ticker, isin in isins.items():
                short = _clean_ticker(bbg_ticker)
                if short in existing_tickers:
                    # Update existing row
                    result = await db.execute(
                        select(TickerDescription).where(
                            TickerDescription.ticker == short
                        )
                    )
                    td = result.scalar_one_or_none()
                    if td is not None:
                        td.isin = isin
                        written += 1
                else:
                    # Create new row with just ticker + bbg_ticker + isin
                    td = TickerDescription(
                        ticker=short,
                        bbg_ticker=bbg_ticker,
                        isin=isin,
                    )
                    db.add(td)
                    created += 1
                    written += 1

            await db.commit()

        logger.info(
            "Done: %d ISINs written (%d updated, %d created)",
            written,
            written - created,
            created,
        )

    except Exception:
        logger.exception("ISIN backfill failed")
        sys.exit(1)

    finally:
        if bloomberg is not None:
            bloomberg.stop()
        await engine.dispose()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
