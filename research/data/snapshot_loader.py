"""One-time fetch: pulls latest snapshot from Railway PostgreSQL → local JSON cache.

This is the ONLY time we hit the production database. All subsequent research
runs operate on the local cached copy.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import orjson
from sqlalchemy import create_engine, text

from research.config.settings import settings


def _table_has_column(conn, table: str, column: str) -> bool:
    """Check if a column exists in a table (works for PostgreSQL)."""
    try:
        conn.execute(text(f"SELECT {column} FROM {table} LIMIT 0"))  # noqa: S608
        return True
    except Exception:
        conn.rollback() if hasattr(conn, "rollback") else None
        return False


def _table_exists(conn, table: str) -> bool:
    """Check if a table exists."""
    try:
        conn.execute(text(f"SELECT 1 FROM {table} LIMIT 0"))  # noqa: S608
        return True
    except Exception:
        conn.rollback() if hasattr(conn, "rollback") else None
        return False


def _get_sync_engine():
    """Create a synchronous SQLAlchemy engine for one-time DB operations."""
    url = settings.sync_database_url
    if not url:
        raise ValueError(
            "DATABASE_URL not set. Add it to research/.env or set the environment variable."
        )
    return create_engine(url, echo=False)


def fetch_latest_snapshot(output_path: Path | None = None) -> dict:
    """Fetch the latest snapshot from production DB and save to local cache.

    Returns the dashboard data dict.
    """
    output_path = output_path or settings.snapshot_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    engine = _get_sync_engine()

    with engine.connect() as conn:
        # Detect schema: some DBs have dashboard_data_compressed, some don't
        has_compressed = _table_has_column(conn, "snapshots", "dashboard_data_compressed")

        if has_compressed:
            query = (
                "SELECT id, name, dashboard_data, dashboard_data_compressed, "
                "ticker_count, date_count, industry_count "
                "FROM snapshots ORDER BY created_at DESC LIMIT 1"
            )
        else:
            query = (
                "SELECT id, name, dashboard_data, NULL AS dashboard_data_compressed, "
                "ticker_count, date_count, industry_count "
                "FROM snapshots ORDER BY created_at DESC LIMIT 1"
            )

        row = conn.execute(text(query)).fetchone()

        if row is None:
            raise RuntimeError("No snapshots found in production database")

        snap_id, name, json_data, compressed_data, n_tickers, n_dates, n_industries = row

        if compressed_data is not None:
            data = orjson.loads(gzip.decompress(compressed_data))
        elif json_data is not None:
            if isinstance(json_data, dict):
                data = json_data
            elif isinstance(json_data, str):
                data = orjson.loads(json_data.encode())
            else:
                data = orjson.loads(json_data)
        else:
            raise RuntimeError(f"Snapshot {snap_id} has no data")

        # Also fetch indices if tables exist
        indices_map: dict[str, list[str]] = {}
        if _table_exists(conn, "index_memberships") and _table_exists(conn, "indices"):
            indices_rows = conn.execute(
                text(
                    "SELECT i.short_name, im.ticker "
                    "FROM index_memberships im "
                    "JOIN indices i ON im.index_id = i.id "
                    "ORDER BY i.short_name, im.ticker"
                )
            ).fetchall()

            for short_name, ticker in indices_rows:
                indices_map.setdefault(ticker, []).append(short_name)

        # Merge indices into dashboard data if not already present
        if indices_map and ("indices" not in data or not data["indices"]):
            data["indices"] = indices_map

        # Fetch ISIN mappings for FMP ticker translation
        isin_map: dict[str, str] = {}
        if _table_exists(conn, "ticker_descriptions"):
            has_isin = _table_has_column(conn, "ticker_descriptions", "isin")
            if has_isin:
                isin_rows = conn.execute(
                    text("SELECT ticker, isin FROM ticker_descriptions WHERE isin IS NOT NULL")
                ).fetchall()
                for ticker, isin in isin_rows:
                    isin_map[ticker] = isin

        if isin_map:
            data["isin_map"] = isin_map

    # Save to local cache
    output_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

    print(f"Fetched snapshot '{name}' (id={snap_id})")
    print(f"  Tickers: {n_tickers}, Dates: {n_dates}, Industries: {n_industries}")
    print(f"  Indices: {len(indices_map)} tickers with index memberships")
    print(f"  ISINs: {len(isin_map)} tickers with ISIN mappings")
    print(f"  Saved to: {output_path}")

    return data


def load_cached_snapshot(path: Path | None = None) -> dict:
    """Load snapshot from local cache. Raises if not found."""
    path = path or settings.snapshot_path
    if not path.exists():
        raise FileNotFoundError(
            f"No cached snapshot at {path}. Run 'python -m research.cli fetch' first."
        )
    return orjson.loads(path.read_bytes())
