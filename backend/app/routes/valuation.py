"""POST /api/valuation/estimate — AI-agent-friendly valuation endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Snapshot
from app.services.valuation_service import compute_valuation_estimate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["valuation"])


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------
class ValuationEstimateRequest(BaseModel):
    ticker: str | None = None
    revenue_growth: float  # decimal, 0.08 = 8%
    eps_growth: float  # decimal — used for regression; DCF fallback if no estimates
    eps_growth_estimates: list[float] | None = None  # year-by-year EPS growth for DCF
    forward_eps: float | None = None
    current_pe: float | None = None
    current_ev_revenue: float | None = None
    current_ev_gp: float | None = None
    dcf_discount_rate: float = Field(0.10, ge=0.01, le=0.30)
    dcf_terminal_growth: float = Field(0.0, ge=-0.02, le=0.10)
    dcf_fade_period: int = Field(5, ge=1, le=15)
    snapshot_id: int | None = None


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class RegressionStats(BaseModel):
    slope: float
    intercept: float
    r2: float
    n: float


class RegressionPrediction(BaseModel):
    metric_type: str
    metric_label: str
    growth_input_pct: float
    historical_predicted: float | None = None
    historical_stats: RegressionStats | None = None
    historical_period_count: int | None = None
    spot_predicted: float | None = None
    spot_stats: RegressionStats | None = None
    current_actual: float | None = None
    historical_deviation_pct: float | None = None
    spot_deviation_pct: float | None = None


class DcfProjection(BaseModel):
    year: int
    growth_rate: float
    eps: float
    discount_factor: float
    present_value: float


class DcfInputs(BaseModel):
    forward_eps: float
    eps_growth_estimates: list[float]
    discount_rate: float
    terminal_growth: float
    fade_period: int


class DcfValuation(BaseModel):
    inputs: DcfInputs
    projections: list[DcfProjection]
    sum_pv_eps: float
    terminal_eps: float
    terminal_value: float
    pv_terminal_value: float
    total_pv_per_share: float
    implied_pe: float
    terminal_value_pct: float
    current_pe: float | None = None
    deviation_pct: float | None = None
    sensitivity: list[list[float | None]]
    sensitivity_discount_rates: list[float]
    sensitivity_terminal_growths: list[float]


class PeerStats(BaseModel):
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


class IndustryStats(PeerStats):
    industry: str | None = None


class ValuationEstimateResponse(BaseModel):
    ticker: str | None = None
    industry: str | None = None
    snapshot_id: int
    snapshot_date: str | None = None
    date_count: int
    regression: list[RegressionPrediction]
    dcf: DcfValuation | None = None
    peer_context: list[PeerStats]
    industry_context: list[IndustryStats] | None = None


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------
@router.post("/valuation/estimate", response_model=ValuationEstimateResponse)
async def valuation_estimate(
    body: ValuationEstimateRequest,
    db: AsyncSession = Depends(get_db),
) -> ValuationEstimateResponse:
    """Compute regression-implied multiples, DCF, and peer context.

    Accepts an AI agent's growth estimates and returns comprehensive
    valuation analysis in a single call.
    """
    # 1. Load snapshot
    if body.snapshot_id is not None:
        result = await db.execute(
            select(Snapshot).where(Snapshot.id == body.snapshot_id)
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found")
    else:
        result = await db.execute(
            select(Snapshot).order_by(Snapshot.created_at.desc()).limit(1)
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            raise HTTPException(status_code=404, detail="No snapshots found")

    data: dict = snapshot.dashboard_data

    # 2. Validate ticker if provided
    if body.ticker is not None and body.ticker not in data.get("fm", {}):
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{body.ticker}' not found in snapshot",
        )

    # 3. Compute
    try:
        result_dict = compute_valuation_estimate(
            data=data,
            revenue_growth=body.revenue_growth,
            eps_growth=body.eps_growth,
            ticker=body.ticker,
            forward_eps=body.forward_eps,
            current_pe=body.current_pe,
            current_ev_revenue=body.current_ev_revenue,
            current_ev_gp=body.current_ev_gp,
            eps_growth_estimates=body.eps_growth_estimates,
            dcf_discount_rate=body.dcf_discount_rate,
            dcf_terminal_growth=body.dcf_terminal_growth,
            dcf_fade_period=body.dcf_fade_period,
        )
    except Exception as exc:
        logger.exception("Valuation computation failed")
        raise HTTPException(
            status_code=422,
            detail=f"Valuation computation failed: {exc}",
        ) from exc

    # 4. Attach snapshot metadata
    result_dict["snapshot_id"] = snapshot.id
    result_dict["snapshot_date"] = (
        snapshot.created_at.isoformat() if snapshot.created_at else None
    )

    return ValuationEstimateResponse(**result_dict)
