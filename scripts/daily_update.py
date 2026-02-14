"""Daily Bloomberg incremental update + production sync.

Standalone script for Windows Task Scheduler. Uses only stdlib (no pip deps).

Flow:
  1. Health-check local backend
  2. Trigger incremental update (POST /api/bloomberg/update)
  3. Read the resulting snapshot (GET /api/dashboard-data)
  4. Push to production (POST /api/snapshot/import)

Usage:
  python scripts/daily_update.py --lookback-days 5
  python scripts/daily_update.py --production-url https://myapp.up.railway.app
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_filename = f"daily_update_{datetime.now():%Y%m}.log"
log_path = LOG_DIR / log_filename

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("daily_update")


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------


def _request(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    timeout: int = 600,
) -> dict:
    """Make an HTTP request and return parsed JSON response."""
    headers = {"Content-Type": "application/json"} if data is not None else {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _retry(
    fn,
    *,
    retries: int = 3,
    backoff: float = 30.0,
    label: str = "",
):
    """Retry a callable with exponential backoff."""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:
            logger.warning("%s attempt %d/%d failed: %s", label, attempt, retries, exc)
            if attempt == retries:
                raise
            wait = backoff * attempt
            logger.info("Retrying in %.0f seconds...", wait)
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Main steps
# ---------------------------------------------------------------------------


def health_check(base_url: str) -> None:
    """Verify the local backend is reachable."""
    url = f"{base_url}/api/health"
    logger.info("Health check: %s", url)
    resp = _request(url, timeout=10)
    logger.info("Health check OK: %s", resp)


def trigger_incremental_update(
    base_url: str,
    lookback_days: int,
) -> dict:
    """POST /api/bloomberg/update and return the response."""
    url = f"{base_url}/api/bloomberg/update"
    payload = {"lookback_days": lookback_days, "periodicity": "DAILY"}
    logger.info("Triggering incremental update: %s (lookback=%d)", url, lookback_days)
    resp = _request(url, method="POST", data=payload, timeout=600)
    logger.info("Update response: %s", json.dumps(resp, indent=2))
    return resp


def fetch_latest_snapshot(base_url: str) -> dict:
    """GET /api/dashboard-data and return the full JSON."""
    url = f"{base_url}/api/dashboard-data"
    logger.info("Fetching latest snapshot from: %s", url)
    data = _request(url, timeout=120)
    date_count = len(data.get("dates", []))
    ticker_count = len(data.get("tickers", []))
    logger.info("Fetched snapshot: %d dates, %d tickers", date_count, ticker_count)
    return data


def push_to_production(production_url: str, dashboard_data: dict) -> dict:
    """POST /api/snapshot/import to push data to production."""
    url = f"{production_url}/api/snapshot/import"
    name = f"Daily Sync — {datetime.now():%Y-%m-%d %H:%M}"
    payload = {"name": name, "dashboard_data": dashboard_data}
    logger.info("Pushing snapshot to production: %s", url)
    resp = _request(url, method="POST", data=payload, timeout=120)
    logger.info("Production import response: %s", json.dumps(resp, indent=2))
    return resp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily Bloomberg incremental update + production sync"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Local backend URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--production-url",
        default=os.environ.get("PRODUCTION_API_URL", ""),
        help="Production backend URL for syncing (default: $PRODUCTION_API_URL)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="Days before last date to re-fetch (default: 5)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retry attempts per step (default: 3)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Daily Bloomberg update started")
    logger.info("Base URL: %s", args.base_url)
    logger.info("Production URL: %s", args.production_url or "(not set, skip sync)")
    logger.info("Lookback days: %d", args.lookback_days)
    logger.info("=" * 60)

    # Step 1: Health check
    try:
        _retry(
            lambda: health_check(args.base_url),
            retries=args.retries,
            backoff=10.0,
            label="Health check",
        )
    except Exception:
        logger.error("Local backend not reachable — aborting")
        sys.exit(1)

    # Step 2: Trigger incremental update
    try:
        update_resp = _retry(
            lambda: trigger_incremental_update(args.base_url, args.lookback_days),
            retries=args.retries,
            backoff=30.0,
            label="Incremental update",
        )
    except Exception:
        logger.error("Incremental update failed after retries — aborting")
        sys.exit(1)

    if update_resp.get("skipped"):
        logger.info("No new trading days — nothing to sync")
        logger.info("Daily update complete (no changes)")
        return

    # Step 3: Fetch the merged snapshot
    try:
        dashboard_data = _retry(
            lambda: fetch_latest_snapshot(args.base_url),
            retries=args.retries,
            backoff=10.0,
            label="Fetch snapshot",
        )
    except Exception:
        logger.error("Failed to fetch latest snapshot — aborting sync")
        sys.exit(1)

    # Step 4: Push to production (if URL configured)
    if args.production_url:
        try:
            _retry(
                lambda: push_to_production(args.production_url, dashboard_data),
                retries=args.retries,
                backoff=30.0,
                label="Production sync",
            )
        except Exception:
            logger.error("Production sync failed after retries")
            sys.exit(1)
    else:
        logger.info("No production URL configured — skipping sync")

    logger.info("Daily update complete")


if __name__ == "__main__":
    main()
