"""Similarity service — Voyage AI embeddings + TurboPuffer vector search."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TickerDescription

logger = logging.getLogger(__name__)

_EMBED_BATCH_SIZE = 128


def _get_voyage_client():
    """Lazy-init Voyage AI client."""
    import voyageai

    return voyageai.Client(api_key=settings.VOYAGEAI_API_KEY)


def _get_tpuf_namespace():
    """Lazy-init TurboPuffer namespace."""
    import turbopuffer as tpuf

    tpuf.api_key = settings.TURBOPUFFER_API_KEY
    return tpuf.Namespace(settings.TURBOPUFFER_NAMESPACE)


def embed_texts(
    texts: list[str],
    input_type: str = "document",
) -> list[list[float]]:
    """Batch embed texts using Voyage AI.

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


def upsert_vectors(
    ids: list[str],
    vectors: list[list[float]],
    attributes: dict[str, list] | None = None,
) -> None:
    """Upsert vectors to TurboPuffer namespace with metadata."""
    ns = _get_tpuf_namespace()
    ns.upsert(
        ids=ids,
        vectors=vectors,
        attributes=attributes or {},
    )
    logger.info("Upserted %d vectors to TurboPuffer", len(ids))


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
    vectors = embed_texts(texts, input_type="document")

    # Build attributes
    attributes: dict[str, list] = {
        "description": texts,
        "ticker": tickers,
    }

    # Upsert to TurboPuffer
    upsert_vectors(tickers, vectors, attributes)

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

    # Embed the query
    query_vec = embed_texts([text_to_embed], input_type="query")[0]

    # Query TurboPuffer
    ns = _get_tpuf_namespace()
    results = ns.query(
        vector=query_vec,
        top_k=top_k + 1,  # +1 to exclude self if querying by ticker
        include_attributes=["description", "ticker"],
    )

    output: list[dict] = []
    for row in results:
        ticker = row.attributes.get("ticker", row.id) if row.attributes else row.id
        # Skip self
        if query_ticker and ticker == query_ticker:
            continue

        output.append(
            {
                "ticker": ticker,
                "score": round(float(row.dist), 4),
                "description": (
                    row.attributes.get("description", "") if row.attributes else ""
                ),
            }
        )

        if len(output) >= top_k:
            break

    return output
