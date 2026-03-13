"""Fix EPS growth (xg) and add GAAP EPS metrics to production snapshot.

Recomputes xg using Adjusted (excl. SBC) basis for ALL tickers:
  xg = BEST_EPS(BF) / TRAIL_12M_EST_COMP_EPS_EXCL_STK - 1

Also computes new GAAP EPS metrics for every ticker:
  xg_gaap = BEST_EPS_GAAP(BF) / TRAIL_12M_COMPARABLE_EPS_GAAP - 1
  fe_gaap = BEST_EPS_GAAP (BF override)
  pe_gaap = pe * fe / fe_gaap  (derived)

Usage:
  python scripts/fix_eps_growth.py --dry-run
  python scripts/fix_eps_growth.py --dry-run --test-tickers
  python scripts/fix_eps_growth.py --database-url "postgresql://..."
  python scripts/fix_eps_growth.py  # writes to production
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_filename = f"fix_eps_growth_{datetime.now():%Y%m%d_%H%M}.log"
log_path = LOG_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("fix_eps_growth")

# Test tickers with expected xg % (from Bloomberg terminal, latest date)
# Used with --test-tickers to validate before full run
EXPECTED_XG: dict[str, int] = {
    "ADBE": 12,
    "META": 26,
    "MSFT": 24,
    "CRM": 5,
    "AAPL": 14,
    "XYZ": 49,
    "LLY": 43,
    "NVDA": 74,
    "AVGO": 60,
    "DUOL": -58,
    "AXON": 14,
    "AMD": 61,
    "INTC": 26,
    "TOST": 58,
    "VRT": 45,
    "DDOG": 7,
    "NET": 21,
    "HOOD": 17,
    "KLAC": 10,
}
TEST_TICKERS = list(EXPECTED_XG.keys())

# BDP batch size (same as BloombergService)
_BATCH_SIZE = 40


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fix EPS growth (xg) and add GAAP EPS metrics"
    )
    parser.add_argument(
        "--snapshot-id",
        type=int,
        default=None,
        help="Snapshot ID to fix (default: latest)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to DB",
    )
    parser.add_argument(
        "--test-tickers",
        action="store_true",
        help="Only process ~20 test tickers for validation",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="Override DATABASE_URL",
    )
    return parser.parse_args()


def _safe_float(val: object) -> float | None:
    """Convert a value to float or None, handling NaN/Inf/missing."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(float(val), 4)
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 4)
    except (ValueError, TypeError):
        return None


async def main() -> None:
    args = parse_args()

    # Step 0: Inject DATABASE_URL before importing app modules
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
        logger.info("DATABASE_URL overridden from CLI arg")

    # Add backend/ to sys.path
    backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    os.chdir(backend_dir)

    # Deferred imports
    from sqlalchemy import select, update

    from app.db import AsyncSessionLocal, engine
    from app.models import Snapshot
    from app.services.bloomberg_service import BloombergService

    logger.info("=" * 60)
    logger.info("Fix EPS Growth + Add GAAP EPS Metrics")
    logger.info("Dry run: %s", args.dry_run)
    logger.info("Test tickers only: %s", args.test_tickers)
    logger.info("=" * 60)

    bloomberg: BloombergService | None = None

    try:
        # Step 1: Load snapshot
        logger.info("Step 1: Loading snapshot from DB")
        async with AsyncSessionLocal() as db:
            if args.snapshot_id:
                result = await db.execute(
                    select(Snapshot).where(Snapshot.id == args.snapshot_id)
                )
            else:
                result = await db.execute(
                    select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
                )
            snapshot = result.scalar_one_or_none()

            if snapshot is None:
                logger.error("No snapshot found")
                sys.exit(1)

            snapshot_id = snapshot.id
            data = snapshot.dashboard_data

        dates: list[str] = data["dates"]
        tickers: list[str] = data["tickers"]
        fm: dict = data["fm"]

        logger.info(
            "Loaded snapshot #%d: %d dates, %d tickers",
            snapshot_id,
            len(dates),
            len(tickers),
        )

        # Step 2: Identify tickers with at least one non-null fe value
        tickers_with_fe: list[str] = []
        for ticker in tickers:
            fe_arr = fm.get(ticker, {}).get("fe", [])
            if any(v is not None for v in fe_arr):
                tickers_with_fe.append(ticker)

        logger.info(
            "Tickers with fe data: %d / %d (skipping %d without fe)",
            len(tickers_with_fe),
            len(tickers),
            len(tickers) - len(tickers_with_fe),
        )

        # Optionally restrict to test tickers
        if args.test_tickers:
            tickers_to_fetch = [t for t in TEST_TICKERS if t in tickers_with_fe]
            logger.info(
                "Test mode: restricted to %d tickers: %s",
                len(tickers_to_fetch),
                tickers_to_fetch,
            )
        else:
            tickers_to_fetch = tickers_with_fe

        # Step 3: Start Bloomberg
        logger.info("Step 3: Starting Bloomberg session")
        bloomberg = BloombergService()
        bloomberg.start()

        # Convert to Bloomberg format
        bbg_tickers = [f"{t} US Equity" for t in tickers_to_fetch]

        # Step 4: Fetch trailing EPS from Bloomberg (both Adj and GAAP)
        first_date = dates[0]
        last_date = dates[-1]
        start_year = int(first_date[:4])
        fetch_start = f"{start_year - 1}-01-01"

        logger.info(
            "Step 4a: Fetching TRAIL_12M_EST_COMP_EPS_EXCL_STK for %d tickers "
            "(%s to %s)",
            len(bbg_tickers),
            fetch_start,
            last_date,
        )
        trail_excl_raw = await bloomberg._fetch_bdh_metric(
            "TRAIL_12M_EST_COMP_EPS_EXCL_STK",
            fetch_start,
            last_date,
            tickers=bbg_tickers,
        )

        logger.info(
            "Step 4b: Fetching TRAIL_12M_COMPARABLE_EPS_GAAP for %d tickers (%s to %s)",
            len(bbg_tickers),
            fetch_start,
            last_date,
        )
        trail_gaap_raw = await bloomberg._fetch_bdh_metric(
            "TRAIL_12M_COMPARABLE_EPS_GAAP",
            fetch_start,
            last_date,
            tickers=bbg_tickers,
        )

        logger.info(
            "Step 4c: Fetching BEST_EPS_GAAP (BF) for %d tickers (%s to %s)",
            len(bbg_tickers),
            fetch_start,
            last_date,
        )
        fwd_gaap_raw = await bloomberg._fetch_bdh_metric(
            "BEST_EPS_GAAP",
            fetch_start,
            last_date,
            overrides=[("BEST_FPERIOD_OVERRIDE", "BF")],
            periodicity="WEEKLY",
            tickers=bbg_tickers,
        )

        # Forward-fill trailing sets to monthly date grid
        logger.info("Step 5: Forward-filling trailing EPS to date grid")
        trail_excl_arrays = BloombergService._forward_fill_yearly_to_monthly(
            trail_excl_raw, dates
        )
        trail_gaap_arrays = BloombergService._forward_fill_yearly_to_monthly(
            trail_gaap_raw, dates
        )

        # Convert GAAP forward EPS to arrays aligned to snapshot date grid
        fwd_gaap_arrays: dict[str, list[float | None]] = {}
        for bbg_ticker, date_vals in fwd_gaap_raw.items():
            short = bbg_ticker.replace(" US Equity", "").strip()
            fwd_gaap_arrays[short] = [date_vals.get(d) for d in dates]

        # Fetch BEST_EPS_MARKET_TYPE via BDP
        logger.info(
            "Step 5d: Fetching BEST_EPS_MARKET_TYPE for %d tickers",
            len(bbg_tickers),
        )
        eps_market_type = await bloomberg._fetch_eps_market_type(tickers=bbg_tickers)

        got_excl = sum(1 for v in trail_excl_arrays.values() if v)
        got_gaap = sum(1 for v in trail_gaap_arrays.values() if v)
        got_fwd_gaap = sum(1 for v in fwd_gaap_arrays.values() if v)
        logger.info(
            "Forward-filled arrays: %d excl-SBC, %d GAAP trailing, %d GAAP forward",
            got_excl,
            got_gaap,
            got_fwd_gaap,
        )

        # Step 6: Recompute xg (Adj) + compute xg_gaap, fe_gaap, pe_gaap
        logger.info("Step 6: Recomputing xg, xg_gaap, fe_gaap, pe_gaap")

        xg_changes = 0
        gaap_additions = 0
        tickers_changed = 0
        validation_results: list[
            tuple[str, float | None, float | None, int | None]
        ] = []

        for ticker in tickers_to_fetch:
            # --- Adj EPS growth (xg) ---
            fwd_arr = fm.get(ticker, {}).get("fe", [])
            old_xg = fm.get(ticker, {}).get("xg", [])
            trail_arr = trail_excl_arrays.get(ticker, [])

            new_xg: list[float | None] = []
            ticker_xg_changed = False

            for i in range(len(dates)):
                fe_val = fwd_arr[i] if i < len(fwd_arr) else None
                trail_val = trail_arr[i] if i < len(trail_arr) else None

                if fe_val is not None and trail_val is not None and trail_val != 0:
                    val = round(fe_val / trail_val - 1.0, 4)
                else:
                    val = None

                new_xg.append(val)

                old_val = old_xg[i] if i < len(old_xg) else None
                if val != old_val:
                    ticker_xg_changed = True
                    xg_changes += 1

            # Collect validation data for tickers with expected values
            if ticker in EXPECTED_XG:
                last_new: float | None = None
                last_old: float | None = None
                for check_i in range(len(dates) - 1, -1, -1):
                    if check_i < len(new_xg) and new_xg[check_i] is not None:
                        last_new = new_xg[check_i]
                        last_old = old_xg[check_i] if check_i < len(old_xg) else None
                        break
                validation_results.append(
                    (ticker, last_old, last_new, EXPECTED_XG[ticker])
                )

            if ticker_xg_changed:
                tickers_changed += 1
                fm[ticker]["xg"] = new_xg

            # --- GAAP metrics ---
            fwd_gaap_arr = fwd_gaap_arrays.get(ticker, [])
            trail_gaap_arr = trail_gaap_arrays.get(ticker, [])
            pe_arr = fm.get(ticker, {}).get("pe", [])
            fe_adj_arr = fm.get(ticker, {}).get("fe", [])

            new_xg_gaap: list[float | None] = []
            new_fe_gaap: list[float | None] = []
            new_pe_gaap: list[float | None] = []

            for i in range(len(dates)):
                fwd_gaap = fwd_gaap_arr[i] if i < len(fwd_gaap_arr) else None
                trail_gaap = trail_gaap_arr[i] if i < len(trail_gaap_arr) else None
                pe_val = pe_arr[i] if i < len(pe_arr) else None
                fe_adj = fe_adj_arr[i] if i < len(fe_adj_arr) else None

                # fe_gaap
                new_fe_gaap.append(fwd_gaap)

                # xg_gaap
                if fwd_gaap is not None and trail_gaap is not None and trail_gaap != 0:
                    new_xg_gaap.append(round(fwd_gaap / trail_gaap - 1.0, 4))
                else:
                    new_xg_gaap.append(None)

                # pe_gaap = pe * fe / fe_gaap
                if (
                    pe_val is not None
                    and fe_adj is not None
                    and fwd_gaap is not None
                    and fwd_gaap != 0
                ):
                    new_pe_gaap.append(round(pe_val * fe_adj / fwd_gaap, 4))
                else:
                    new_pe_gaap.append(None)

            # Check if any GAAP data was produced
            has_gaap = any(v is not None for v in new_xg_gaap) or any(
                v is not None for v in new_fe_gaap
            )

            if has_gaap:
                gaap_additions += 1

            fm[ticker]["xg_gaap"] = new_xg_gaap
            fm[ticker]["fe_gaap"] = new_fe_gaap
            fm[ticker]["pe_gaap"] = new_pe_gaap
            if ticker in eps_market_type:
                fm[ticker]["epsMarketType"] = eps_market_type[ticker]

        # Print validation table
        if validation_results:
            logger.info("")
            logger.info(
                "  %-8s %12s %12s %12s %8s",
                "TICKER",
                "OLD xg",
                "NEW xg",
                "EXPECTED",
                "DELTA",
            )
            logger.info("  %s", "-" * 56)
            for ticker, old_v, new_v, expected in sorted(validation_results):
                old_str = f"{old_v * 100:+.0f}%" if old_v is not None else "N/A"
                new_str = f"{new_v * 100:+.0f}%" if new_v is not None else "N/A"
                exp_str = f"{expected:+d}%"
                if new_v is not None:
                    delta = abs(round(new_v * 100) - expected)
                    delta_str = f"{delta}pp" if delta > 0 else "OK"
                else:
                    delta_str = "???"
                logger.info(
                    "  %-8s %12s %12s %12s %8s",
                    ticker,
                    old_str,
                    new_str,
                    exp_str,
                    delta_str,
                )
            logger.info("")

        logger.info(
            "Recomputed xg: %d value changes across %d tickers",
            xg_changes,
            tickers_changed,
        )
        logger.info(
            "GAAP metrics added for %d tickers (xg_gaap, fe_gaap, pe_gaap)",
            gaap_additions,
        )

        # Step 7: Write back to DB
        if not args.dry_run:
            logger.info("Step 7: Updating snapshot #%d in DB", snapshot_id)
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Snapshot)
                    .where(Snapshot.id == snapshot_id)
                    .values(dashboard_data=data)
                )
                await db.commit()
            logger.info("Snapshot #%d updated successfully", snapshot_id)
        else:
            logger.info("Step 7: DRY RUN — no changes written to DB")

        # Summary
        logger.info("=" * 60)
        logger.info("Fix EPS Growth + GAAP Metrics complete")
        logger.info("  Snapshot: #%d", snapshot_id)
        logger.info("  Tickers fetched from Bloomberg: %d", len(tickers_to_fetch))
        logger.info("  Tickers with changed xg: %d", tickers_changed)
        logger.info("  Total xg value changes: %d", xg_changes)
        logger.info("  Tickers with GAAP data: %d", gaap_additions)
        if args.dry_run:
            logger.info("  (DRY RUN — no data written to DB)")
        logger.info("=" * 60)

    except Exception:
        logger.exception("Fix EPS Growth failed")
        sys.exit(1)

    finally:
        if bloomberg is not None:
            bloomberg.stop()
        await engine.dispose()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
