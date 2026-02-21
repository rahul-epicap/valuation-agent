"""Peer-based valuation endpoint — combines similarity search with index regressions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot
from app.services import index_service, similarity_service, valuation_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["peer-valuation"])


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class PeerValuationRequest(BaseModel):
    ticker: str
    revenue_growth: float = Field(description="Decimal, e.g. 0.15 for 15%")
    eps_growth: float = Field(description="Decimal, e.g. 0.20 for 20%")
    forward_eps: float | None = None
    current_pe: float | None = None
    top_k_peers: int = Field(default=20, ge=5, le=50)
    snapshot_id: int | None = None
    eps_growth_estimates: list[float] | None = None
    dcf_discount_rate: float = 0.10
    dcf_terminal_growth: float = 0.0
    dcf_fade_period: int = 5
    business_description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional business description for similarity search when ticker lacks a stored description",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class PeerSearchResultModel(BaseModel):
    ticker: str
    score: float
    description: str


class HistoricalBaseline(BaseModel):
    avg_slope: float
    avg_intercept: float
    avg_r2: float
    avg_n: float
    period_count: int


class PeerRegressionMetric(BaseModel):
    metric_type: str
    metric_label: str
    regression: dict | None = None
    implied_multiple: float | None = None
    historical_implied_multiple: float | None = None
    historical: HistoricalBaseline | None = None


class PeerIndexRegression(BaseModel):
    index_name: str
    peer_count_in_index: int
    total_index_tickers: int
    avg_peer_similarity: float
    regressions: list[PeerRegressionMetric]


class PeerCompositeValuation(BaseModel):
    metric_type: str
    metric_label: str
    weighted_implied_multiple: float | None = None
    actual_multiple: float | None = None
    deviation_pct: float | None = None
    num_indices: int = 0


class PeerDistributionStats(BaseModel):
    metric_type: str
    metric_label: str
    count: int
    mean: float | None = None
    median: float | None = None
    p25: float | None = None
    p75: float | None = None
    min: float | None = None
    max: float | None = None
    ticker_percentile: float | None = None


class PeerValuationResponse(BaseModel):
    ticker: str
    industry: str | None = None
    peer_count: int
    similar_tickers: list[PeerSearchResultModel]
    index_regressions: list[PeerIndexRegression]
    composite_valuation: list[PeerCompositeValuation]
    historical_composite_valuation: list[PeerCompositeValuation]
    peer_stats: list[PeerDistributionStats]
    dcf: dict | None = None
    snapshot_id: int


@router.post("/valuation/peer-estimate", response_model=PeerValuationResponse)
async def peer_estimate(
    body: PeerValuationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compute peer-based valuation using similarity search + index regressions.

    Flow:
        1. Load snapshot data.
        2. Find similar tickers via TurboPuffer.
        3. Look up index memberships for each peer.
        4. Run index-based regressions and compute composite valuation.
    """
    # Load snapshot
    if body.snapshot_id:
        result = await db.execute(
            select(Snapshot).where(Snapshot.id == body.snapshot_id)
        )
    else:
        result = await db.execute(
            select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
        )

    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshot found")

    data = snapshot.dashboard_data
    if body.ticker not in data.get("tickers", []):
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{body.ticker}' not found in snapshot",
        )

    # Find similar tickers
    try:
        similar = await similarity_service.find_similar(
            query_ticker=body.ticker,
            query_text=body.business_description,
            db=db,
            top_k=body.top_k_peers,
        )
    except Exception:
        logger.exception("Similarity search failed for %s", body.ticker)
        similar = []

    # Build indices map
    indices_map = await index_service.build_indices_map(db)

    # Fill in actuals from snapshot
    fm = data["fm"].get(body.ticker, {})
    latest_di = len(data["dates"]) - 1

    forward_eps = body.forward_eps
    if forward_eps is None:
        fe_val = fm.get("fe", [None] * (latest_di + 1))[latest_di]
        if fe_val is not None:
            forward_eps = float(fe_val)

    current_pe = body.current_pe
    if current_pe is None:
        pe_val = fm.get("pe", [None] * (latest_di + 1))[latest_di]
        if pe_val is not None:
            current_pe = float(pe_val)

    # Compute peer-based valuation
    result = valuation_service.compute_peer_valuation(
        data=data,
        ticker=body.ticker,
        similar_tickers=similar,
        indices_map=indices_map,
        revenue_growth=body.revenue_growth,
        eps_growth=body.eps_growth,
        forward_eps=forward_eps,
        current_pe=current_pe,
        eps_growth_estimates=body.eps_growth_estimates,
        dcf_discount_rate=body.dcf_discount_rate,
        dcf_terminal_growth=body.dcf_terminal_growth,
        dcf_fade_period=body.dcf_fade_period,
    )

    result["snapshot_id"] = snapshot.id
    result["industry"] = data.get("industries", {}).get(body.ticker)

    return result
