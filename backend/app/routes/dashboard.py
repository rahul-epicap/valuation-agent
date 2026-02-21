import gzip
import logging
from collections import OrderedDict

import orjson
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

# ---------------------------------------------------------------------------
# In-memory response cache (capped at 5 snapshots).
# Stores pre-serialized bytes to avoid re-serializing 200+ MB dicts on every hit.
# Per-process: each uvicorn worker gets its own copy.
# ---------------------------------------------------------------------------
_MAX_CACHE = 5
_cache: OrderedDict[int, tuple[bytes, bytes]] = OrderedDict()  # (raw, gzipped)
_cache_version: int = 0
_latest_snapshot_id: int | None = None


def invalidate_cache() -> None:
    """Clear cached data so next request re-fetches from DB."""
    global _latest_snapshot_id, _cache_version
    _latest_snapshot_id = None
    _cache.clear()
    _cache_version += 1


async def _resolve_latest_id(db: AsyncSession) -> int:
    """Return the latest snapshot ID, using a lightweight query."""
    global _latest_snapshot_id
    if _latest_snapshot_id is not None:
        return _latest_snapshot_id
    result = await db.execute(
        select(Snapshot.id).order_by(Snapshot.created_at.desc()).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No snapshots found")
    _latest_snapshot_id = row
    return row


async def _enrich_with_indices(data: dict, db: AsyncSession) -> dict:
    """Enrich dashboard data with current index memberships."""
    from app.services.index_service import build_indices_map

    try:
        indices_map = await build_indices_map(db)
        if indices_map:
            data["indices"] = indices_map
    except Exception:
        logger.debug("Could not enrich with index data", exc_info=True)
    return data


def _compact_data(data: dict) -> dict:
    """Round all fm numbers to 4dp and strip all-null tickers.

    Applied once on cache miss so existing (unrounded) snapshots benefit
    without requiring a re-upload.
    """
    fm = data.get("fm")
    if not fm:
        return data

    metric_keys = ("er", "eg", "pe", "rg", "xg", "fe")
    empty_tickers: list[str] = []

    for ticker, metrics in fm.items():
        all_null = True
        for key in metric_keys:
            arr = metrics.get(key)
            if arr is None:
                continue
            for i, v in enumerate(arr):
                if v is not None:
                    all_null = False
                    if isinstance(v, float):
                        arr[i] = round(v, 4)
            metrics[key] = arr
        if all_null:
            empty_tickers.append(ticker)

    for t in empty_tickers:
        del fm[t]

    if empty_tickers:
        removed = set(empty_tickers)
        data["tickers"] = [t for t in data.get("tickers", []) if t not in removed]
        industries = data.get("industries")
        if industries:
            for t in empty_tickers:
                industries.pop(t, None)
        logger.info("Compacted: stripped %d all-null tickers", len(empty_tickers))

    return data


async def _get_enriched_data(
    snapshot_id: int | None, db: AsyncSession
) -> tuple[int, bytes, bytes]:
    """Return (snapshot_id, raw_bytes, gzipped_bytes), using cache when available."""
    sid = snapshot_id if snapshot_id is not None else await _resolve_latest_id(db)

    if sid in _cache:
        _cache.move_to_end(sid)
        raw, gz = _cache[sid]
        return sid, raw, gz

    if snapshot_id is not None:
        result = await db.execute(select(Snapshot).where(Snapshot.id == sid))
    else:
        result = await db.execute(
            select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
        )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    data = dict(snapshot.dashboard_data)
    # Deep-copy fm so _compact_data's in-place mutations don't touch the ORM object
    if "fm" in data:
        data["fm"] = {
            t: {k: list(v) for k, v in m.items()} for t, m in data["fm"].items()
        }
    data = await _enrich_with_indices(data, db)
    data = _compact_data(data)

    serialized = orjson.dumps(data)
    # Pre-compress once at level 1 (~20x faster than level 9, ~10-15% larger)
    compressed = gzip.compress(serialized, compresslevel=1)
    logger.info(
        "Cached snapshot %d: %d KB raw, %d KB gzipped",
        sid,
        len(serialized) // 1024,
        len(compressed) // 1024,
    )

    _cache[sid] = (serialized, compressed)
    if len(_cache) > _MAX_CACHE:
        _cache.popitem(last=False)

    return sid, serialized, compressed


def _make_cached_response(
    request: Request,
    raw: bytes,
    compressed: bytes,
    snapshot_id: int,
) -> Response:
    """Return 304 if ETag matches, otherwise full JSON with cache headers.

    Serves pre-compressed bytes when the client accepts gzip, bypassing
    GZipMiddleware's per-request re-compression of the ~100 MB payload.
    """
    etag = f'"{snapshot_id}-{_cache_version}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    accept_encoding = request.headers.get("accept-encoding", "")
    if "gzip" in accept_encoding:
        return Response(
            content=compressed,
            media_type="application/json",
            headers={
                "Content-Encoding": "gzip",
                "ETag": etag,
                "Cache-Control": "no-cache",
            },
        )
    return Response(
        content=raw,
        media_type="application/json",
        headers={
            "ETag": etag,
            "Cache-Control": "no-cache",
        },
    )


@router.get("/snapshots")
async def list_snapshots(db: AsyncSession = Depends(get_db)):
    """List all snapshots ordered by created_at descending.

    Returns metadata only (no dashboard_data blob).
    """
    result = await db.execute(
        select(
            Snapshot.id,
            Snapshot.name,
            Snapshot.created_at,
            Snapshot.source_filename,
            Snapshot.ticker_count,
            Snapshot.date_count,
            Snapshot.industry_count,
        ).order_by(Snapshot.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "source_filename": row.source_filename,
            "ticker_count": row.ticker_count,
            "date_count": row.date_count,
            "industry_count": row.industry_count,
        }
        for row in rows
    ]


@router.get("/dashboard-data")
async def get_latest_dashboard_data(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the latest snapshot's dashboard_data JSON, enriched with index memberships."""
    sid, raw, compressed = await _get_enriched_data(None, db)
    return _make_cached_response(request, raw, compressed, sid)


@router.get("/dashboard-data/{snapshot_id}")
async def get_dashboard_data_by_id(
    snapshot_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return a specific snapshot's dashboard_data by ID, enriched with index memberships."""
    sid, raw, compressed = await _get_enriched_data(snapshot_id, db)
    return _make_cached_response(request, raw, compressed, sid)


class SnapshotImportRequest(BaseModel):
    name: str
    dashboard_data: dict


@router.post("/snapshot/import")
async def import_snapshot(
    body: SnapshotImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import raw dashboard JSON as a new snapshot.

    Used by the daily update script to sync local data to production.
    """
    data = body.dashboard_data

    # Validate required top-level keys
    required_keys = {"dates", "tickers", "industries", "fm"}
    missing = required_keys - set(data.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"dashboard_data missing required keys: {sorted(missing)}",
        )

    ticker_count = len(data.get("tickers", []))
    date_count = len(data.get("dates", []))
    industry_count = len(set(data.get("industries", {}).values()))

    snapshot = Snapshot(
        name=body.name,
        dashboard_data=data,
        source_filename="imported",
        ticker_count=ticker_count,
        date_count=date_count,
        industry_count=industry_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)

    invalidate_cache()

    logger.info(
        "Imported snapshot id=%d: %d tickers, %d dates, %d industries",
        snapshot.id,
        ticker_count,
        date_count,
        industry_count,
    )

    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "source_filename": snapshot.source_filename,
        "ticker_count": ticker_count,
        "date_count": date_count,
        "industry_count": industry_count,
    }
