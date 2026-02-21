"""Similarity service — Voyage AI embeddings + TurboPuffer vector search."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TickerDescription

logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 128

# Module-level singletons (lazy-init)
_tpuf_client = None
_voyage_client = None


def _get_voyage_client():
    """Lazy-init Voyage AI client."""
    global _voyage_client
    if _voyage_client is None:
        import voyageai

        _voyage_client = voyageai.Client(api_key=settings.VOYAGEAI_API_KEY)
    return _voyage_client


def _get_tpuf_namespace():
    """Lazy-init TurboPuffer namespace (v1.16+ client API)."""
    global _tpuf_client
    if _tpuf_client is None:
        import turbopuffer as tpuf

        _tpuf_client = tpuf.Turbopuffer(
            api_key=settings.TURBOPUFFER_API_KEY,
            region=settings.TURBOPUFFER_REGION,
        )
    return _tpuf_client.namespace(settings.TURBOPUFFER_NAMESPACE)


def _embed_texts_sync(
    texts: list[str],
    input_type: str = "document",
) -> list[list[float]]:
    """Batch embed texts using Voyage AI (synchronous, for use with to_thread).

    Args:
        texts: Strings to embed.
        input_type: 'document' for upserts, 'query' for searches.

    Returns:
        List of embedding vectors.
    """
    client = _get_voyage_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[i : i + _EMBED_BATCH_SIZE]
        response = client.embed(
            batch,
            model=settings.VOYAGEAI_MODEL,
            input_type=input_type,
        )
        all_embeddings.extend(response.embeddings)

    return all_embeddings


def _upsert_vectors_sync(
    ids: list[str],
    vectors: list[list[float]],
    attributes: dict[str, list] | None = None,
) -> None:
    """Upsert vectors to TurboPuffer namespace (synchronous, for use with to_thread)."""
    ns = _get_tpuf_namespace()
    attrs = attributes or {}

    # Build row dicts for the new write API
    rows: list[dict] = []
    for idx, (doc_id, vec) in enumerate(zip(ids, vectors)):
        row: dict = {"id": doc_id, "vector": vec}
        for attr_name, attr_values in attrs.items():
            row[attr_name] = attr_values[idx]
        rows.append(row)

    ns.write(
        upsert_rows=rows,
        distance_metric="cosine_distance",
    )
    logger.info("Upserted %d vectors to TurboPuffer", len(ids))


def _query_similar_sync(
    query_vec: list[float],
    top_k: int,
) -> list[dict]:
    """Query TurboPuffer for similar vectors (synchronous, for use with to_thread)."""
    ns = _get_tpuf_namespace()
    response = ns.query(
        rank_by=("vector", "ANN", query_vec),
        top_k=top_k,
        include_attributes=["description", "ticker"],
    )
    # Return raw row data for processing by caller
    results: list[dict] = []
    for row in response.rows or []:
        extras = row.model_extra or {}
        results.append({"id": row.id, **extras})
    return results


async def sync_descriptions(db: AsyncSession) -> int:
    """Embed all unembedded descriptions and upsert to TurboPuffer.

    Returns the number of vectors upserted.
    """
    from app.services.description_service import get_unembedded_tickers

    rows = await get_unembedded_tickers(db)
    if not rows:
        logger.info("No unembedded descriptions to sync")
        return 0

    tickers = [r.ticker for r in rows]
    texts = [r.description for r in rows]

    logger.info("Embedding %d descriptions", len(texts))
    vectors = await asyncio.to_thread(_embed_texts_sync, texts, "document")

    # Build attributes
    attributes: dict[str, list] = {
        "description": texts,
        "ticker": tickers,
    }

    # Upsert to TurboPuffer
    await asyncio.to_thread(_upsert_vectors_sync, tickers, vectors, attributes)

    # Update embedded_at
    now = datetime.now(timezone.utc)
    for row in rows:
        row.embedded_at = now

    await db.commit()
    logger.info("Synced %d description embeddings", len(rows))
    return len(rows)


async def find_similar(
    query_ticker: str | None = None,
    query_text: str | None = None,
    db: AsyncSession | None = None,
    top_k: int = 20,
) -> list[dict]:
    """Find similar stocks by ticker or free text.

    Either query_ticker or query_text must be provided.
    If query_ticker is given and db is provided, looks up stored description first.

    Returns [{ticker, score, description}, ...].
    """
    text_to_embed: str | None = query_text

    if query_ticker and db:
        result = await db.execute(
            select(TickerDescription).where(TickerDescription.ticker == query_ticker)
        )
        row = result.scalar_one_or_none()
        if row and row.description:
            text_to_embed = row.description

    if not text_to_embed:
        if query_ticker:
            # Fall back to using ticker as search text
            text_to_embed = query_ticker
        else:
            return []

    # Embed the query (offloaded to thread)
    query_vec = (await asyncio.to_thread(_embed_texts_sync, [text_to_embed], "query"))[
        0
    ]

    # Query TurboPuffer (offloaded to thread)
    raw_results = await asyncio.to_thread(_query_similar_sync, query_vec, top_k + 1)

    output: list[dict] = []
    for row_data in raw_results:
        ticker = row_data.get("ticker", row_data.get("id", ""))
        # Skip self
        if query_ticker and ticker == query_ticker:
            continue

        # Distance is returned as '$dist' extra field by TurboPuffer
        dist = row_data.get("$dist")
        # Convert cosine distance to similarity score (1 - distance)
        score = round(1.0 - float(dist), 4) if dist is not None else 0.0

        output.append(
            {
                "ticker": ticker,
                "score": score,
                "description": row_data.get("description", ""),
            }
        )

        if len(output) >= top_k:
            break

    return output
