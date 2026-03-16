"""Upload winning experiment results back to production as a new snapshot.

Creates a NEW snapshot — never overwrites existing data.
"""

from __future__ import annotations

import gzip
from datetime import datetime, timezone

import orjson
from sqlalchemy import create_engine, text

from research.config.settings import settings


def upload_snapshot(
    dashboard_data: dict,
    name: str | None = None,
    source_description: str = "autoresearch",
) -> int:
    """Upload a new snapshot to the production database.

    Returns the new snapshot ID.
    """
    url = settings.sync_database_url
    if not url:
        raise ValueError("DATABASE_URL not set.")

    engine = create_engine(url, echo=False)

    if name is None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        name = f"Research: {source_description} ({ts})"

    tickers = dashboard_data.get("tickers", [])
    dates = dashboard_data.get("dates", [])
    industries = dashboard_data.get("industries", {})

    compressed = gzip.compress(orjson.dumps(dashboard_data), compresslevel=1)

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "INSERT INTO snapshots "
                "(name, dashboard_data_compressed, source_filename, "
                "ticker_count, date_count, industry_count) "
                "VALUES (:name, :data, :source, :tc, :dc, :ic) "
                "RETURNING id"
            ),
            {
                "name": name,
                "data": compressed,
                "source": f"autoresearch:{source_description}",
                "tc": len(tickers),
                "dc": len(dates),
                "ic": len(set(industries.values())),
            },
        )
        snap_id = result.scalar_one()
        conn.commit()

    print(f"Uploaded new snapshot: id={snap_id}, name='{name}'")
    return snap_id
