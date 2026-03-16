"""Bloomberg full update — standalone script for complete data refresh.

Connects directly to Bloomberg Terminal + production PostgreSQL to update
everything: core valuation metrics, index memberships, and ticker descriptions.
No running backend needed.

Flow:
  0. Parse CLI args, setup logging
  1. Ensure DB tables exist
  2. Seed indices from indices.json
  3. Start Bloomberg session
  4. Refresh index memberships (current constituents)
  5. Build full ticker universe (index members ∪ tickers.json)
  6. Load latest snapshot from DB
  7. Incremental Bloomberg fetch + merge
  8. Save new snapshot to DB
  9. Fetch missing ticker descriptions
 10. Cleanup + summary

Usage:
  python scripts/bloomberg_update.py
  python scripts/bloomberg_update.py --database-url "postgresql://user:pass@host:5432/db"
  python scripts/bloomberg_update.py --skip-descriptions --skip-memberships
  python scripts/bloomberg_update.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup (must happen before any app imports)
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_filename = f"bloomberg_update_{datetime.now():%Y%m}.log"
log_path = LOG_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("bloomberg_update")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bloomberg full update — standalone complete data refresh"
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="Days before last date to re-fetch (default: 5)",
    )
    parser.add_argument(
        "--periodicity",
        default="DAILY",
        choices=["DAILY", "WEEKLY", "MONTHLY"],
        help="BDH periodicity (default: DAILY)",
    )
    parser.add_argument(
        "--skip-descriptions",
        action="store_true",
        help="Skip fetching ticker descriptions",
    )
    parser.add_argument(
        "--skip-isins",
        action="store_true",
        help="Skip fetching missing ISINs",
    )
    parser.add_argument(
        "--skip-memberships",
        action="store_true",
        help="Skip refreshing index memberships",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't write to DB",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Override DATABASE_URL (injected before app imports)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    # Step 0: Inject DATABASE_URL before importing app modules
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
        logger.info("DATABASE_URL overridden from CLI arg")

    # Add backend/ to sys.path so app.* imports work
    backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    # Change cwd to backend/ so pydantic-settings reads backend/.env
    # (the root .env contains NEXT_PUBLIC_API_URL which is not in Settings)
    os.chdir(backend_dir)

    # Deferred imports — after env is set and sys.path is patched
    from sqlalchemy import select, text

    from app.db import AsyncSessionLocal, Base, engine
    from app.models import Snapshot, TickerDescription
    from app.services.bloomberg_service import BloombergService, _clean_ticker
    from app.services import description_service, index_service

    logger.info("=" * 60)
    logger.info("Bloomberg full update started")
    logger.info("Lookback days: %d", args.lookback_days)
    logger.info("Periodicity: %s", args.periodicity)
    logger.info("Skip memberships: %s", args.skip_memberships)
    logger.info("Skip descriptions: %s", args.skip_descriptions)
    logger.info("Skip ISINs: %s", args.skip_isins)
    logger.info("Dry run: %s", args.dry_run)
    logger.info("=" * 60)

    bloomberg: BloombergService | None = None

    try:
        # Step 1: Ensure DB tables exist
        logger.info("Step 1: Ensuring database tables exist")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables OK")

        # Step 2: Seed indices
        logger.info("Step 2: Seeding indices from indices.json")
        async with AsyncSessionLocal() as db:
            indices = await index_service.seed_indices(db)
            short_names = [idx.short_name for idx in indices]
            logger.info("Seeded %d indices", len(indices))

        # Step 3: Start Bloomberg
        logger.info("Step 3: Starting Bloomberg session")
        try:
            bloomberg = BloombergService()
            bloomberg.start()
        except Exception:
            logger.exception("Failed to start Bloomberg session")
            sys.exit(1)

        # Step 4: Refresh index memberships
        membership_summary: dict[str, int] = {}
        if not args.skip_memberships:
            logger.info(
                "Step 4: Refreshing index memberships (%d indices)",
                len(short_names),
            )
            async with AsyncSessionLocal() as db:
                membership_summary = await index_service.refresh_memberships_batch(
                    bloomberg,
                    db,
                    short_names=short_names,
                    current_only=True,
                )
            total_new = sum(v for v in membership_summary.values() if v > 0)
            failed = sum(1 for v in membership_summary.values() if v < 0)
            logger.info(
                "Membership refresh: %d new rows, %d indices failed",
                total_new,
                failed,
            )
        else:
            logger.info("Step 4: Skipping membership refresh (--skip-memberships)")

        # Step 5: Build full ticker universe
        logger.info("Step 5: Building full ticker universe")
        async with AsyncSessionLocal() as db:
            index_tickers = await index_service.get_all_current_tickers(db)

        # Convert short tickers to Bloomberg format
        index_bbg = [f"{t} US Equity" for t in index_tickers]

        # Load tickers.json for manual additions
        tickers_path = Path(backend_dir) / "tickers.json"
        with open(tickers_path) as f:
            manual_tickers: list[str] = json.load(f)

        # Union and deduplicate
        combined = sorted(set(index_bbg) | set(manual_tickers))
        bloomberg.set_ticker_universe(combined)
        logger.info(
            "Universe: %d index members + %d manual -> %d combined",
            len(index_bbg),
            len(manual_tickers),
            len(combined),
        )

        # Step 6: Load latest snapshot
        logger.info("Step 6: Loading latest snapshot from DB")
        existing_data: dict = {}
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
            )
            latest = result.scalar_one_or_none()
            if latest is not None:
                existing_data = latest.get_data()
                logger.info(
                    "Loaded snapshot #%d: %d dates, %d tickers",
                    latest.id,
                    len(existing_data.get("dates", [])),
                    len(existing_data.get("tickers", [])),
                )
            else:
                logger.info("No existing snapshot — will do full fetch")

        # Step 7: Incremental Bloomberg fetch
        logger.info("Step 7: Fetching Bloomberg data (incremental)")
        merged_data = await bloomberg.fetch_incremental(
            existing_data,
            lookback_days=args.lookback_days,
            periodicity=args.periodicity,
        )
        new_dates = merged_data.get("dates", [])
        new_tickers = merged_data.get("tickers", [])
        new_industries = merged_data.get("industries", {})
        logger.info(
            "Merged result: %d dates, %d tickers, %d industries",
            len(new_dates),
            len(new_tickers),
            len(new_industries),
        )

        # Step 8: Save snapshot
        if not args.dry_run:
            logger.info("Step 8: Saving new snapshot to DB")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            compressed = Snapshot.compress(merged_data)
            logger.info(
                "Compressed snapshot: %.1f MB",
                len(compressed) / (1024 * 1024),
            )
            async with AsyncSessionLocal() as db:
                snapshot = Snapshot(
                    name=f"Bloomberg Full Update -- {now_str}",
                    dashboard_data_compressed=compressed,
                    source_filename="bloomberg-full-update",
                    ticker_count=len(new_tickers),
                    date_count=len(new_dates),
                    industry_count=len(new_industries),
                )
                db.add(snapshot)
                await db.commit()
                await db.refresh(snapshot)
                logger.info("Saved snapshot #%d", snapshot.id)
        else:
            logger.info("Step 8: Dry run — skipping snapshot save")

        # Step 9: Fetch missing descriptions
        desc_count = 0
        if not args.skip_descriptions and not args.dry_run:
            logger.info("Step 9: Fetching missing ticker descriptions")
            async with AsyncSessionLocal() as db:
                # Find tickers that don't have descriptions yet
                existing_result = await db.execute(select(TickerDescription.ticker))
                described = {row[0] for row in existing_result.all()}
                all_short = {t.replace(" US Equity", "").strip() for t in combined}
                missing = sorted(all_short - described)

                if missing:
                    missing_bbg = [f"{t} US Equity" for t in missing]
                    logger.info(
                        "Fetching descriptions for %d tickers without descriptions",
                        len(missing_bbg),
                    )
                    fetched = await description_service.fetch_descriptions(
                        bloomberg, db, tickers=missing_bbg
                    )
                    desc_count = len(fetched)
                else:
                    logger.info("All tickers already have descriptions")
        else:
            logger.info(
                "Step 9: Skipping descriptions (%s)",
                "dry run" if args.dry_run else "--skip-descriptions",
            )

        # Step 9.5: Fetch missing ISINs
        isin_count = 0
        if not args.skip_isins and not args.dry_run:
            logger.info("Step 9.5: Fetching missing ISINs")
            # Ensure isin column exists (create_all won't add to existing tables)
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "ALTER TABLE ticker_descriptions "
                        "ADD COLUMN IF NOT EXISTS isin VARCHAR(20)"
                    )
                )
            async with AsyncSessionLocal() as db:
                existing_result = await db.execute(
                    select(
                        TickerDescription.ticker,
                        TickerDescription.bbg_ticker,
                    ).where(TickerDescription.isin.is_(None))
                )
                missing_isin_rows = existing_result.all()

                if missing_isin_rows:
                    missing_bbg = [row.bbg_ticker for row in missing_isin_rows]
                    existing_tickers = {row.ticker for row in missing_isin_rows}
                    logger.info(
                        "Fetching ISINs for %d tickers without ISINs",
                        len(missing_bbg),
                    )
                    isins = await bloomberg.fetch_isins(missing_bbg)
                    logger.info("Bloomberg returned ISINs for %d tickers", len(isins))

                    for bbg_ticker, isin in isins.items():
                        short = _clean_ticker(bbg_ticker)
                        if short in existing_tickers:
                            result = await db.execute(
                                select(TickerDescription).where(
                                    TickerDescription.ticker == short
                                )
                            )
                            td = result.scalar_one_or_none()
                            if td is not None:
                                td.isin = isin
                                isin_count += 1
                        else:
                            td = TickerDescription(
                                ticker=short,
                                bbg_ticker=bbg_ticker,
                                isin=isin,
                            )
                            db.add(td)
                            isin_count += 1

                    await db.commit()
                    logger.info("Wrote %d ISINs to DB", isin_count)
                else:
                    logger.info("All tickers already have ISINs")
        else:
            logger.info(
                "Step 9.5: Skipping ISINs (%s)",
                "dry run" if args.dry_run else "--skip-isins",
            )

        # Step 10: Summary
        logger.info("=" * 60)
        logger.info("Bloomberg full update complete")
        logger.info("  Universe size: %d tickers", len(combined))
        logger.info(
            "  Dates: %d (existing) -> %d (merged)",
            len(existing_data.get("dates", [])),
            len(new_dates),
        )
        if not args.skip_memberships:
            logger.info(
                "  Memberships: %d new rows across %d indices",
                sum(v for v in membership_summary.values() if v > 0),
                len(membership_summary),
            )
        if not args.skip_descriptions and not args.dry_run:
            logger.info("  Descriptions: %d newly fetched", desc_count)
        if not args.skip_isins and not args.dry_run:
            logger.info("  ISINs: %d newly fetched", isin_count)
        if args.dry_run:
            logger.info("  (DRY RUN — no data written to DB)")
        logger.info("=" * 60)

    except Exception:
        logger.exception("Bloomberg full update failed")
        sys.exit(1)

    finally:
        # Cleanup
        if bloomberg is not None:
            bloomberg.stop()
        await engine.dispose()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
