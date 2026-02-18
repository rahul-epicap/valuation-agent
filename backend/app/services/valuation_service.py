"""Pure-computation valuation service — no DB, no FastAPI dependencies.

Ports regression, filtering, DCF, and peer-stats logic from the frontend
TypeScript into Python for consumption by the /api/valuation/estimate endpoint.
"""

from __future__ import annotations

import math

MULTIPLE_KEYS: dict[str, str] = {"evRev": "er", "evGP": "eg", "pEPS": "pe"}
GROWTH_KEYS: dict[str, str] = {"evRev": "rg", "evGP": "rg", "pEPS": "xg"}
METRIC_LABELS: dict[str, str] = {
    "evRev": "EV / Revenue",
    "evGP": "EV / Gross Profit",
    "pEPS": "Price / EPS",
}


# ---------------------------------------------------------------------------
# 1. Linear regression (OLS)
# ---------------------------------------------------------------------------
def linear_regression(
    pts: list[tuple[float, float]],
) -> dict[str, float] | None:
    """OLS regression. Port of regression.ts. Requires >= 3 points."""
    n = len(pts)
    if n < 3:
        return None

    sx = sy = sxy = sx2 = sy2 = 0.0
    for x, y in pts:
        sx += x
        sy += y
        sxy += x * y
        sx2 += x * x
        sy2 += y * y

    d = n * sx2 - sx * sx
    if abs(d) < 1e-12:
        return None

    slope = (n * sxy - sx * sy) / d
    intercept = (sy - slope * sx) / n
    sst = sy2 - sy * sy / n

    sse = 0.0
    for x, y in pts:
        p = slope * x + intercept
        sse += (y - p) ** 2

    r2 = (1 - sse / sst) if sst > 0 else 0.0
    return {"slope": slope, "intercept": intercept, "r2": r2, "n": n}


# ---------------------------------------------------------------------------
# 2. EPS quality check
# ---------------------------------------------------------------------------
def ok_eps(data: dict, ticker: str, di: int) -> bool:
    """Port of filters.ts okEps. Checks forward EPS > 0.5 and EPS growth bounds."""
    d = data["fm"][ticker]
    fe = d["fe"][di]
    xg = d["xg"][di]
    if fe is None or fe <= 0.5:
        return False
    if xg is None or xg <= -0.75 or xg > 2.0:
        return False
    return True


# ---------------------------------------------------------------------------
# 3. Filter scatter points (growth vs multiple)
# ---------------------------------------------------------------------------
def filter_points(
    data: dict,
    metric_type: str,
    di: int,
    tickers: list[str],
) -> list[dict]:
    """Port of filters.ts filterPoints (without growth-range filters).

    Returns [{x: growth%, y: multiple, t: ticker}, ...].
    """
    mk = MULTIPLE_KEYS[metric_type]
    gk = GROWTH_KEYS[metric_type]
    pts: list[dict] = []

    for t in tickers:
        d = data["fm"].get(t)
        if d is None:
            continue
        m = d[mk][di]
        g = d[gk][di]
        if m is None or g is None:
            continue

        if metric_type == "pEPS":
            if not ok_eps(data, t, di):
                continue
            if m > 200:
                continue
        if metric_type == "evRev" and m > 80:
            continue
        if metric_type == "evGP" and m > 120:
            continue

        g_pct = g * 100
        pts.append({"x": g_pct, "y": m, "t": t})

    return pts


# ---------------------------------------------------------------------------
# 4. Filter multiples (for distribution stats)
# ---------------------------------------------------------------------------
def filter_multiples(
    data: dict,
    metric_type: str,
    di: int,
    tickers: list[str],
) -> list[float]:
    """Port of filters.ts filterMultiples. Returns sorted valid multiples."""
    mk = MULTIPLE_KEYS[metric_type]
    vals: list[float] = []

    for t in tickers:
        d = data["fm"].get(t)
        if d is None:
            continue
        m = d[mk][di]
        if m is None:
            continue

        if metric_type == "pEPS":
            if not ok_eps(data, t, di):
                continue
            if m > 200:
                continue
        if metric_type == "evRev" and (m > 80 or m < 0):
            continue
        if metric_type == "evGP" and (m > 120 or m < 0):
            continue

        vals.append(float(m))

    vals.sort()
    return vals


# ---------------------------------------------------------------------------
# 5. Percentile (linear interpolation)
# ---------------------------------------------------------------------------
def percentile(sorted_vals: list[float], p: float) -> float:
    """Port of filters.ts percentile. Linear interpolation on sorted list."""
    if len(sorted_vals) == 0:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    i = (len(sorted_vals) - 1) * p
    lo = math.floor(i)
    hi = math.ceil(i)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


# ---------------------------------------------------------------------------
# 6. Historical baseline (average regression across all dates)
# ---------------------------------------------------------------------------
def compute_historical_baseline(
    data: dict,
    metric_type: str,
    tickers: list[str],
) -> dict | None:
    """Port of valueScore.ts computeHistoricalBaseline (no growth-range filters)."""
    total_slope = 0.0
    total_intercept = 0.0
    total_r2 = 0.0
    total_n = 0.0
    period_count = 0

    for di in range(len(data["dates"])):
        pts = filter_points(data, metric_type, di, tickers)
        reg = linear_regression([(p["x"], p["y"]) for p in pts])
        if reg is None:
            continue

        total_slope += reg["slope"]
        total_intercept += reg["intercept"]
        total_r2 += reg["r2"]
        total_n += reg["n"]
        period_count += 1

    if period_count < 1:
        return None

    return {
        "avg_slope": total_slope / period_count,
        "avg_intercept": total_intercept / period_count,
        "period_count": period_count,
        "avg_r2": total_r2 / period_count,
        "avg_n": total_n / period_count,
    }


# ---------------------------------------------------------------------------
# 7. Spot regression (single date)
# ---------------------------------------------------------------------------
def compute_spot_regression(
    data: dict,
    metric_type: str,
    di: int,
    tickers: list[str],
) -> dict | None:
    """Run filter_points + linear_regression at a single date index."""
    pts = filter_points(data, metric_type, di, tickers)
    return linear_regression([(p["x"], p["y"]) for p in pts])


# ---------------------------------------------------------------------------
# 8. Fade growth rate (for DCF projection)
# ---------------------------------------------------------------------------
def fade_growth_rate(
    year: int,
    initial: float,
    terminal: float,
    fade_period: int,
) -> float:
    """Port of dcf.ts fadeGrowthRate. Linear interpolation from initial to terminal."""
    if fade_period <= 0:
        return terminal
    if year <= 0:
        return initial
    if year >= fade_period:
        return terminal
    t = year / fade_period
    return initial * (1 - t) + terminal * t


# ---------------------------------------------------------------------------
# 9. Core DCF computation
# ---------------------------------------------------------------------------
def compute_dcf(
    forward_eps: float,
    eps_growth_estimates: list[float],
    discount_rate: float = 0.10,
    terminal_growth: float = 0.0,
    fade_period: int = 5,
    current_pe: float | None = None,
) -> dict | None:
    """DCF valuation with explicit year-by-year EPS growth estimates.

    Projection phases:
      1. Explicit years — one per entry in eps_growth_estimates.
      2. Fade years — linear decel from last estimate to terminal_growth
         over fade_period additional years.
    Terminal value via Gordon Growth at the end of the fade period.
    """
    if forward_eps <= 0:
        return None
    if discount_rate <= terminal_growth:
        return None
    if not eps_growth_estimates:
        return None

    n_explicit = len(eps_growth_estimates)
    total_years = n_explicit + fade_period
    last_explicit_growth = eps_growth_estimates[-1]

    projections: list[dict] = []
    eps = forward_eps
    sum_pv_eps = 0.0

    for y in range(1, total_years + 1):
        if y <= n_explicit:
            # Explicit estimate
            growth_rate = eps_growth_estimates[y - 1]
        else:
            # Fade from last explicit growth to terminal
            fade_year = y - n_explicit
            growth_rate = fade_growth_rate(
                fade_year, last_explicit_growth, terminal_growth, fade_period
            )

        eps = eps * (1 + growth_rate)
        discount_factor = 1 / ((1 + discount_rate) ** y)
        present_value = eps * discount_factor
        sum_pv_eps += present_value

        projections.append(
            {
                "year": y,
                "growth_rate": growth_rate,
                "eps": eps,
                "discount_factor": discount_factor,
                "present_value": present_value,
            }
        )

    # Gordon Growth Model terminal value
    terminal_eps = eps * (1 + terminal_growth)
    terminal_value = terminal_eps / (discount_rate - terminal_growth)
    pv_terminal_value = terminal_value / ((1 + discount_rate) ** total_years)

    total_pv_per_share = sum_pv_eps + pv_terminal_value
    implied_pe = total_pv_per_share / forward_eps
    terminal_value_pct = (pv_terminal_value / total_pv_per_share) * 100

    result: dict = {
        "projections": projections,
        "sum_pv_eps": sum_pv_eps,
        "terminal_eps": terminal_eps,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "total_pv_per_share": total_pv_per_share,
        "implied_pe": implied_pe,
        "terminal_value_pct": terminal_value_pct,
    }

    if current_pe is not None and current_pe > 0:
        result["current_pe"] = current_pe
        result["deviation_pct"] = ((implied_pe - current_pe) / current_pe) * 100

    return result


# ---------------------------------------------------------------------------
# 10. Sensitivity table (5×5 grid)
# ---------------------------------------------------------------------------
def compute_sensitivity_table(
    forward_eps: float,
    eps_growth_estimates: list[float],
    discount_rate: float,
    terminal_growth: float,
    fade_period: int,
) -> dict:
    """5×5 grid of implied P/E varying dr ±0.01/±0.02 and tg ±0.01/±0.02."""
    dr_offsets = [-0.02, -0.01, 0.0, 0.01, 0.02]
    tg_offsets = [-0.02, -0.01, 0.0, 0.01, 0.02]

    discount_rates = [discount_rate + o for o in dr_offsets]
    terminal_growths = [terminal_growth + o for o in tg_offsets]

    grid: list[list[float | None]] = []
    for dr in discount_rates:
        row: list[float | None] = []
        for tg in terminal_growths:
            res = compute_dcf(forward_eps, eps_growth_estimates, dr, tg, fade_period)
            row.append(res["implied_pe"] if res else None)
        grid.append(row)

    return {
        "discount_rates": discount_rates,
        "terminal_growths": terminal_growths,
        "implied_pe_grid": grid,
    }


# ---------------------------------------------------------------------------
# 11. Peer / industry distribution stats
# ---------------------------------------------------------------------------
def compute_peer_stats(
    data: dict,
    metric_type: str,
    di: int,
    tickers: list[str],
    ticker_value: float | None = None,
) -> dict:
    """Distribution stats for filtered multiples of the given ticker set."""
    vals = filter_multiples(data, metric_type, di, tickers)
    if not vals:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p25": None,
            "p75": None,
            "min": None,
            "max": None,
            "ticker_percentile": None,
        }

    mean = sum(vals) / len(vals)
    result: dict = {
        "count": len(vals),
        "mean": mean,
        "median": percentile(vals, 0.5),
        "p25": percentile(vals, 0.25),
        "p75": percentile(vals, 0.75),
        "min": vals[0],
        "max": vals[-1],
        "ticker_percentile": None,
    }

    if ticker_value is not None:
        below_or_equal = sum(1 for v in vals if v <= ticker_value)
        result["ticker_percentile"] = (below_or_equal / len(vals)) * 100

    return result


# ---------------------------------------------------------------------------
# 12. Orchestrator — assembles full valuation estimate
# ---------------------------------------------------------------------------
def compute_valuation_estimate(
    data: dict,
    revenue_growth: float,
    eps_growth: float,
    ticker: str | None = None,
    forward_eps: float | None = None,
    current_pe: float | None = None,
    current_ev_revenue: float | None = None,
    current_ev_gp: float | None = None,
    eps_growth_estimates: list[float] | None = None,
    dcf_discount_rate: float = 0.10,
    dcf_terminal_growth: float = 0.0,
    dcf_fade_period: int = 5,
) -> dict:
    """Compute regression-implied multiples, DCF, and peer context.

    Returns a dict ready for serialisation into ValuationEstimateResponse.
    """
    all_tickers: list[str] = data["tickers"]
    latest_di = len(data["dates"]) - 1

    # Pull ticker actuals from snapshot when available
    ticker_actuals: dict[str, float | None] = {
        "er": current_ev_revenue,
        "eg": current_ev_gp,
        "pe": current_pe,
    }
    industry: str | None = None

    if ticker and ticker in data["fm"]:
        fm = data["fm"][ticker]
        industry = data.get("industries", {}).get(ticker)
        # Fill in from snapshot where caller didn't override
        if forward_eps is None:
            fe_val = fm["fe"][latest_di]
            if fe_val is not None:
                forward_eps = float(fe_val)
        if current_pe is None:
            pe_val = fm["pe"][latest_di]
            if pe_val is not None:
                current_pe = float(pe_val)
                ticker_actuals["pe"] = current_pe
        if current_ev_revenue is None:
            er_val = fm["er"][latest_di]
            if er_val is not None:
                ticker_actuals["er"] = float(er_val)
        if current_ev_gp is None:
            eg_val = fm["eg"][latest_di]
            if eg_val is not None:
                ticker_actuals["eg"] = float(eg_val)

    # ---- Regression predictions for each metric type ----
    metric_types = ["evRev", "evGP", "pEPS"]
    regression_results: list[dict] = []

    for mt in metric_types:
        mk = MULTIPLE_KEYS[mt]
        gk = GROWTH_KEYS[mt]
        growth_rate = revenue_growth if gk == "rg" else eps_growth
        growth_pct = growth_rate * 100

        # Historical baseline
        hist = compute_historical_baseline(data, mt, all_tickers)
        hist_predicted: float | None = None
        hist_stats: dict | None = None
        hist_period_count: int | None = None
        if hist:
            hist_predicted = hist["avg_slope"] * growth_pct + hist["avg_intercept"]
            hist_stats = {
                "slope": hist["avg_slope"],
                "intercept": hist["avg_intercept"],
                "r2": hist["avg_r2"],
                "n": hist["avg_n"],
            }
            hist_period_count = hist["period_count"]

        # Spot regression
        spot = compute_spot_regression(data, mt, latest_di, all_tickers)
        spot_predicted: float | None = None
        spot_stats: dict | None = None
        if spot:
            spot_predicted = spot["slope"] * growth_pct + spot["intercept"]
            spot_stats = {
                "slope": spot["slope"],
                "intercept": spot["intercept"],
                "r2": spot["r2"],
                "n": spot["n"],
            }

        # Actual multiple for ticker
        actual = ticker_actuals.get(mk)

        # Deviation %
        hist_dev: float | None = None
        spot_dev: float | None = None
        if actual is not None and hist_predicted and hist_predicted > 0:
            hist_dev = ((actual - hist_predicted) / hist_predicted) * 100
        if actual is not None and spot_predicted and spot_predicted > 0:
            spot_dev = ((actual - spot_predicted) / spot_predicted) * 100

        regression_results.append(
            {
                "metric_type": mt,
                "metric_label": METRIC_LABELS[mt],
                "growth_input_pct": growth_pct,
                "historical_predicted": hist_predicted,
                "historical_stats": hist_stats,
                "historical_period_count": hist_period_count,
                "spot_predicted": spot_predicted,
                "spot_stats": spot_stats,
                "current_actual": actual,
                "historical_deviation_pct": hist_dev,
                "spot_deviation_pct": spot_dev,
            }
        )

    # ---- DCF valuation ----
    # Fall back to single eps_growth wrapped in a list if no explicit estimates
    dcf_estimates = eps_growth_estimates if eps_growth_estimates else [eps_growth]

    dcf_result: dict | None = None
    if forward_eps is not None and forward_eps > 0:
        dcf_result = compute_dcf(
            forward_eps=forward_eps,
            eps_growth_estimates=dcf_estimates,
            discount_rate=dcf_discount_rate,
            terminal_growth=dcf_terminal_growth,
            fade_period=dcf_fade_period,
            current_pe=current_pe,
        )
        if dcf_result is not None:
            sensitivity = compute_sensitivity_table(
                forward_eps=forward_eps,
                eps_growth_estimates=dcf_estimates,
                discount_rate=dcf_discount_rate,
                terminal_growth=dcf_terminal_growth,
                fade_period=dcf_fade_period,
            )
            dcf_result["inputs"] = {
                "forward_eps": forward_eps,
                "eps_growth_estimates": dcf_estimates,
                "discount_rate": dcf_discount_rate,
                "terminal_growth": dcf_terminal_growth,
                "fade_period": dcf_fade_period,
            }
            dcf_result["sensitivity"] = sensitivity["implied_pe_grid"]
            dcf_result["sensitivity_discount_rates"] = sensitivity["discount_rates"]
            dcf_result["sensitivity_terminal_growths"] = sensitivity["terminal_growths"]

    # ---- Peer context (full universe) ----
    peer_context: list[dict] = []
    for mt in metric_types:
        mk = MULTIPLE_KEYS[mt]
        tv = ticker_actuals.get(mk)
        stats = compute_peer_stats(data, mt, latest_di, all_tickers, tv)
        stats["metric_type"] = mt
        stats["metric_label"] = METRIC_LABELS[mt]
        peer_context.append(stats)

    # ---- Industry context (if ticker provided) ----
    industry_context: list[dict] | None = None
    if ticker and industry:
        ind_tickers = [
            t for t in all_tickers if data.get("industries", {}).get(t) == industry
        ]
        industry_context = []
        for mt in metric_types:
            mk = MULTIPLE_KEYS[mt]
            tv = ticker_actuals.get(mk)
            stats = compute_peer_stats(data, mt, latest_di, ind_tickers, tv)
            stats["metric_type"] = mt
            stats["metric_label"] = METRIC_LABELS[mt]
            stats["industry"] = industry
            industry_context.append(stats)

    return {
        "ticker": ticker,
        "industry": industry,
        "date_count": len(data["dates"]),
        "regression": regression_results,
        "dcf": dcf_result,
        "peer_context": peer_context,
        "industry_context": industry_context,
    }
