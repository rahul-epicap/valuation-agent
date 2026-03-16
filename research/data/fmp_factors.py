"""Maps FMP API responses → comprehensive factor values for regression research.

Pulls from profile, key-metrics, ratios, financial-growth, analyst-estimates,
rating, earnings-surprises, and historical prices to build a rich cross-sectional
factor set.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np

from research.data.fmp_client import FMPClient


async def extract_all_factors(
    client: FMPClient,
    symbol: str,
    reference_date: str | None = None,
) -> dict[str, float | None]:
    """Extract all FMP-sourced factors for a single symbol.

    Pulls data from 6 endpoints and derives ~30 factor values covering:
    - Size (market cap, enterprise value)
    - Volatility (beta, historical vol)
    - Momentum (6m, 12m price returns)
    - Quality (ROE, ROIC, margins, FCF yield, earnings quality)
    - Leverage (D/E, interest coverage, net debt/EBITDA)
    - Growth (revenue, EPS, FCF historical growth rates)
    - Valuation context (P/E, P/B, EV/EBITDA from FMP's perspective)
    - Analyst sentiment (estimate dispersion, earnings surprise)
    - Rating (composite score)
    """
    factors: dict[str, float | None] = {}

    # --- 1. Profile: size, beta, sector ---
    profile = await client.get_profile(symbol)
    if profile:
        mkt_cap = profile.get("mktCap")
        factors["log_market_cap"] = math.log(mkt_cap) if mkt_cap and mkt_cap > 0 else None
        factors["beta"] = _safe_float(profile.get("beta"))
        factors["vol_avg"] = _safe_float(profile.get("volAvg"))
    else:
        factors["log_market_cap"] = None
        factors["beta"] = None
        factors["vol_avg"] = None

    # --- 2. Key Metrics: quality, leverage, valuation ---
    metrics = await client.get_key_metrics(symbol)
    if metrics:
        latest = metrics[0]
        factors["roe"] = _safe_float(latest.get("roe"))
        factors["roic"] = _safe_float(latest.get("roic"))
        factors["debt_to_equity"] = _safe_float(latest.get("debtToEquity"))
        factors["debt_to_assets"] = _safe_float(latest.get("debtToAssets"))
        factors["net_debt_to_ebitda"] = _safe_float(latest.get("netDebtToEBITDA"))
        factors["interest_coverage"] = _safe_float(latest.get("interestCoverage"))
        factors["current_ratio"] = _safe_float(latest.get("currentRatio"))
        factors["fcf_yield"] = _safe_float(latest.get("freeCashFlowYield"))
        factors["earnings_yield"] = _safe_float(latest.get("earningsYield"))
        factors["income_quality"] = _safe_float(latest.get("incomeQuality"))
        factors["ev_to_sales"] = _safe_float(latest.get("evToSales"))
        factors["ev_to_ebitda"] = _safe_float(latest.get("enterpriseValueOverEBITDA"))
        factors["pe_ratio"] = _safe_float(latest.get("peRatio"))
        factors["pb_ratio"] = _safe_float(latest.get("pbRatio"))
        factors["price_to_sales"] = _safe_float(latest.get("priceToSalesRatio"))
        factors["sbc_to_revenue"] = _safe_float(latest.get("stockBasedCompensationToRevenue"))
        factors["rd_to_revenue"] = _safe_float(latest.get("researchAndDdevelopementToRevenue"))
        factors["capex_to_revenue"] = _safe_float(latest.get("capexToRevenue"))
    else:
        for k in [
            "roe",
            "roic",
            "debt_to_equity",
            "debt_to_assets",
            "net_debt_to_ebitda",
            "interest_coverage",
            "current_ratio",
            "fcf_yield",
            "earnings_yield",
            "income_quality",
            "ev_to_sales",
            "ev_to_ebitda",
            "pe_ratio",
            "pb_ratio",
            "price_to_sales",
            "sbc_to_revenue",
            "rd_to_revenue",
            "capex_to_revenue",
        ]:
            factors[k] = None

    # --- 3. Ratios: margins ---
    ratios = await client.get_ratios(symbol)
    if ratios:
        latest = ratios[0]
        factors["gross_profit_margin"] = _safe_float(latest.get("grossProfitMargin"))
        factors["operating_profit_margin"] = _safe_float(latest.get("operatingProfitMargin"))
        factors["net_profit_margin"] = _safe_float(latest.get("netProfitMargin"))
        factors["fcf_to_operating_cf"] = _safe_float(
            latest.get("freeCashFlowOperatingCashFlowRatio")
        )
        factors["return_on_assets"] = _safe_float(latest.get("returnOnAssets"))
        factors["return_on_capital"] = _safe_float(latest.get("returnOnCapitalEmployed"))
        factors["asset_turnover"] = _safe_float(latest.get("assetTurnover"))
    else:
        for k in [
            "gross_profit_margin",
            "operating_profit_margin",
            "net_profit_margin",
            "fcf_to_operating_cf",
            "return_on_assets",
            "return_on_capital",
            "asset_turnover",
        ]:
            factors[k] = None

    # --- 4. Financial Growth: historical growth rates ---
    growth = await client.get_financial_growth(symbol)
    if growth:
        latest = growth[0]
        factors["revenue_growth_hist"] = _safe_float(latest.get("revenueGrowth"))
        factors["gross_profit_growth"] = _safe_float(latest.get("grossProfitGrowth"))
        factors["eps_growth_hist"] = _safe_float(latest.get("epsgrowth"))
        factors["fcf_growth"] = _safe_float(latest.get("freeCashFlowGrowth"))
        factors["operating_income_growth"] = _safe_float(latest.get("operatingIncomeGrowth"))
        factors["three_yr_rev_growth"] = _safe_float(latest.get("threeYRevenueGrowthPerShare"))
        factors["five_yr_rev_growth"] = _safe_float(latest.get("fiveYRevenueGrowthPerShare"))
        factors["rd_expense_growth"] = _safe_float(latest.get("rdexpenseGrowth"))
    else:
        for k in [
            "revenue_growth_hist",
            "gross_profit_growth",
            "eps_growth_hist",
            "fcf_growth",
            "operating_income_growth",
            "three_yr_rev_growth",
            "five_yr_rev_growth",
            "rd_expense_growth",
        ]:
            factors[k] = None

    # --- 5. Analyst Estimates: consensus dispersion ---
    estimates = await client.get_analyst_estimates(symbol)
    if estimates:
        latest = estimates[0]
        est_eps_avg = _safe_float(latest.get("estimatedEpsAvg"))
        est_eps_high = _safe_float(latest.get("estimatedEpsHigh"))
        est_eps_low = _safe_float(latest.get("estimatedEpsLow"))
        if est_eps_avg and est_eps_high and est_eps_low and abs(est_eps_avg) > 0.01:
            factors["eps_estimate_dispersion"] = (est_eps_high - est_eps_low) / abs(est_eps_avg)
        else:
            factors["eps_estimate_dispersion"] = None
        factors["n_analysts_eps"] = _safe_float(latest.get("numberAnalystsEstimatedEps"))
        factors["n_analysts_rev"] = _safe_float(latest.get("numberAnalystEstimatedRevenue"))
    else:
        factors["eps_estimate_dispersion"] = None
        factors["n_analysts_eps"] = None
        factors["n_analysts_rev"] = None

    # --- 6. Rating: composite score ---
    rating = await client.get_rating(symbol)
    if rating:
        factors["rating_score"] = _safe_float(rating.get("ratingScore"))
    else:
        factors["rating_score"] = None

    # --- 7. Earnings Surprise: recent beat/miss ---
    surprises = await client.get_earnings_surprises(symbol)
    if surprises and len(surprises) >= 1:
        latest_s = surprises[0]
        actual = _safe_float(latest_s.get("actualEarningResult"))
        estimated = _safe_float(latest_s.get("estimatedEarning"))
        if actual is not None and estimated is not None and abs(estimated) > 0.01:
            factors["earnings_surprise_pct"] = (actual - estimated) / abs(estimated)
        else:
            factors["earnings_surprise_pct"] = None
        # Average surprise over last 4 quarters
        if len(surprises) >= 4:
            surprise_pcts = []
            for s in surprises[:4]:
                a = _safe_float(s.get("actualEarningResult"))
                e = _safe_float(s.get("estimatedEarning"))
                if a is not None and e is not None and abs(e) > 0.01:
                    surprise_pcts.append((a - e) / abs(e))
            factors["avg_earnings_surprise_4q"] = (
                sum(surprise_pcts) / len(surprise_pcts) if surprise_pcts else None
            )
        else:
            factors["avg_earnings_surprise_4q"] = None
    else:
        factors["earnings_surprise_pct"] = None
        factors["avg_earnings_surprise_4q"] = None

    # --- 8. Historical Prices: momentum & volatility ---
    mom_vol = await _extract_momentum_volatility(client, symbol, reference_date)
    factors.update(mom_vol)

    return factors


async def _extract_momentum_volatility(
    client: FMPClient,
    symbol: str,
    reference_date: str | None = None,
) -> dict[str, float | None]:
    """Extract momentum and volatility factors from historical prices."""
    if reference_date:
        ref = datetime.strptime(reference_date, "%Y-%m-%d")
    else:
        ref = datetime.now()

    from_date = (ref - timedelta(days=400)).strftime("%Y-%m-%d")
    to_date = ref.strftime("%Y-%m-%d")

    prices = await client.get_historical_prices(symbol, from_date, to_date)
    if not prices or len(prices) < 30:
        return {
            "momentum_1m": None,
            "momentum_3m": None,
            "momentum_6m": None,
            "momentum_12m": None,
            "historical_vol_30d": None,
            "historical_vol_90d": None,
        }

    prices_sorted = sorted(prices, key=lambda p: p["date"])
    closes = [p["close"] for p in prices_sorted if p.get("close")]

    if len(closes) < 30:
        return {
            "momentum_1m": None,
            "momentum_3m": None,
            "momentum_6m": None,
            "momentum_12m": None,
            "historical_vol_30d": None,
            "historical_vol_90d": None,
        }

    result: dict[str, float | None] = {}

    # Momentum at various horizons
    result["momentum_1m"] = closes[-1] / closes[-21] - 1.0 if len(closes) >= 21 else None
    result["momentum_3m"] = closes[-1] / closes[-63] - 1.0 if len(closes) >= 63 else None
    result["momentum_6m"] = closes[-1] / closes[-126] - 1.0 if len(closes) >= 126 else None
    result["momentum_12m"] = closes[-1] / closes[-252] - 1.0 if len(closes) >= 252 else None

    # Historical volatility (annualized)
    log_returns = np.diff(np.log(closes))
    if len(log_returns) >= 30:
        result["historical_vol_30d"] = float(np.std(log_returns[-30:]) * np.sqrt(252))
    else:
        result["historical_vol_30d"] = None
    if len(log_returns) >= 90:
        result["historical_vol_90d"] = float(np.std(log_returns[-90:]) * np.sqrt(252))
    else:
        result["historical_vol_90d"] = None

    return result


def _safe_float(val) -> float | None:
    """Safely convert API value to float, handling None and non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None
