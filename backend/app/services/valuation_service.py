"""Pure-computation valuation service — no DB, no FastAPI dependencies.

Ports regression, filtering, DCF, and peer-stats logic from the frontend
TypeScript into Python for consumption by the /api/valuation/estimate endpoint.
"""

from __future__ import annotations

import math

import numpy as np

MULTIPLE_KEYS: dict[str, str] = {
    "evRev": "er",
    "evGP": "eg",
    "pEPS": "pe",
    "pEPS_GAAP": "pe_gaap",
}
GROWTH_KEYS: dict[str, str] = {
    "evRev": "rg",
    "evGP": "rg",
    "pEPS": "xg",
    "pEPS_GAAP": "xg_gaap",
}
METRIC_LABELS: dict[str, str] = {
    "evRev": "EV / Revenue",
    "evGP": "EV / Gross Profit",
    "pEPS": "Price / EPS",
    "pEPS_GAAP": "P / GAAP EPS",
}


def _resolve_eps_keys(metric_type: str, d: dict) -> tuple[str, str]:
    """Resolve per-ticker multiple/growth keys based on epsMarketType.

    For pEPS, if the ticker's epsMarketType is 'GAAP', use pe_gaap/xg_gaap
    so regressions plot each ticker on its native EPS basis.
    For pEPS_GAAP, always use GAAP keys regardless of epsMarketType.
    """
    if metric_type == "pEPS" and d.get("epsMarketType") == "GAAP":
        return "pe_gaap", "xg_gaap"
    return MULTIPLE_KEYS[metric_type], GROWTH_KEYS[metric_type]


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
def ok_eps(data: dict, ticker: str, di: int, metric_type: str = "pEPS") -> bool:
    """Port of filters.ts okEps. Checks forward EPS > 0.5 and EPS growth bounds."""
    d = data["fm"][ticker]
    use_gaap = metric_type == "pEPS_GAAP" or (
        metric_type == "pEPS" and d.get("epsMarketType") == "GAAP"
    )
    if use_gaap:
        fe_arr = d.get("fe_gaap", [])
        xg_arr = d.get("xg_gaap", [])
        fe = fe_arr[di] if di < len(fe_arr) else None
        xg = xg_arr[di] if di < len(xg_arr) else None
    else:
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
    is_eps = metric_type in ("pEPS", "pEPS_GAAP")
    pts: list[dict] = []

    for t in tickers:
        d = data["fm"].get(t)
        if d is None:
            continue
        # Per-ticker key resolution based on epsMarketType
        mk, gk = (
            _resolve_eps_keys(metric_type, d)
            if is_eps
            else (MULTIPLE_KEYS[metric_type], GROWTH_KEYS[metric_type])
        )
        m_arr = d.get(mk, [])
        g_arr = d.get(gk, [])
        m = m_arr[di] if di < len(m_arr) else None
        g = g_arr[di] if di < len(g_arr) else None
        if m is None or g is None:
            continue

        if is_eps:
            if not ok_eps(data, t, di, metric_type):
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
# 3b. Multi-factor filter: enrich scatter points with factor dummy values
# ---------------------------------------------------------------------------
def filter_points_multi_factor(
    data: dict,
    metric_type: str,
    di: int,
    tickers: list[str],
    active_factors: list[str],
    indices_map: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Reuses filter_points, then attaches factorValues for each point.

    indices_map: {ticker: [index_short_names]} — if None, uses data['indices'].
    """
    base_pts = filter_points(data, metric_type, di, tickers)
    if not active_factors:
        return base_pts

    idx_map = indices_map or data.get("indices", {})

    for pt in base_pts:
        ticker_indices = set(idx_map.get(pt["t"], []))
        pt["factorValues"] = {
            f: (1 if f in ticker_indices else 0) for f in active_factors
        }

    return base_pts


# ---------------------------------------------------------------------------
# 3c. Multi-factor OLS regression via NumPy
# ---------------------------------------------------------------------------
def multi_factor_ols(
    y: list[float],
    X: list[list[float]],
    factor_names: list[str],
) -> dict | None:
    """Multi-factor OLS using NumPy lstsq.

    X columns: [0]=intercept, [1]=growth%, [2+]=factor dummies.
    Drops factors with < 3 members or zero variance before solving.

    Returns dict with intercept, growth_coefficient, factors, r2, adjusted_r2, n, p.
    """
    n = len(y)
    if n < 3:
        return None

    X_arr = np.array(X, dtype=np.float64)
    y_arr = np.array(y, dtype=np.float64)

    # Filter factors: keep only columns with >= 3 non-zero and non-zero variance
    kept_indices: list[int] = []
    kept_names: list[str] = []
    for i, name in enumerate(factor_names):
        col_idx = i + 2
        col = X_arr[:, col_idx]
        if np.count_nonzero(col) < 3:
            continue
        if np.var(col) < 1e-12:
            continue
        kept_indices.append(i)
        kept_names.append(name)

    # Build filtered X: intercept + growth + kept factors
    cols = [X_arr[:, 0], X_arr[:, 1]]
    for i in kept_indices:
        cols.append(X_arr[:, i + 2])
    Xf = np.column_stack(cols)

    p = Xf.shape[1]
    if n <= p:
        return None

    # Solve via lstsq
    beta, residuals, rank, sv = np.linalg.lstsq(Xf, y_arr, rcond=None)
    if rank < p:
        return None

    # Compute R² and adjusted R²
    y_mean = np.mean(y_arr)
    sst = np.sum((y_arr - y_mean) ** 2)
    y_pred = Xf @ beta
    sse = np.sum((y_arr - y_pred) ** 2)

    r2 = float(1 - sse / sst) if sst > 0 else 0.0
    adjusted_r2 = float(1 - ((1 - r2) * (n - 1)) / (n - p)) if sst > 0 else 0.0

    factors = [
        {"name": name, "type": "binary", "coefficient": float(beta[i + 2])}
        for i, name in enumerate(kept_names)
    ]

    return {
        "intercept": float(beta[0]),
        "growth_coefficient": float(beta[1]),
        "factors": factors,
        "r2": r2,
        "adjusted_r2": adjusted_r2,
        "n": n,
        "p": p,
    }


# ---------------------------------------------------------------------------
# 3d. Spot regression with multi-factor support
# ---------------------------------------------------------------------------
def compute_spot_regression_multi_factor(
    data: dict,
    metric_type: str,
    di: int,
    tickers: list[str],
    active_factors: list[str],
    indices_map: dict[str, list[str]] | None = None,
) -> dict | None:
    """Run multi-factor OLS at a single date."""
    pts = filter_points_multi_factor(
        data, metric_type, di, tickers, active_factors, indices_map
    )
    if len(pts) < 3:
        return None

    y = [p["y"] for p in pts]
    X = []
    for p in pts:
        row = [1.0, p["x"]]
        fv = p.get("factorValues", {})
        for f in active_factors:
            row.append(float(fv.get(f, 0)))
        X.append(row)

    return multi_factor_ols(y, X, active_factors)


# ---------------------------------------------------------------------------
# 3e. Historical baseline with multi-factor support
# ---------------------------------------------------------------------------
def compute_historical_baseline_multi_factor(
    data: dict,
    metric_type: str,
    tickers: list[str],
    active_factors: list[str],
    indices_map: dict[str, list[str]] | None = None,
) -> dict | None:
    """Average multi-factor regression across all dates."""
    total_growth_coeff = 0.0
    total_intercept = 0.0
    total_r2 = 0.0
    total_adj_r2 = 0.0
    total_n = 0.0
    period_count = 0

    for di in range(len(data["dates"])):
        reg = compute_spot_regression_multi_factor(
            data, metric_type, di, tickers, active_factors, indices_map
        )
        if reg is None:
            continue

        total_growth_coeff += reg["growth_coefficient"]
        total_intercept += reg["intercept"]
        total_r2 += reg["r2"]
        total_adj_r2 += reg["adjusted_r2"]
        total_n += reg["n"]
        period_count += 1

    if period_count < 1:
        return None

    return {
        "avg_growth_coefficient": total_growth_coeff / period_count,
        "avg_intercept": total_intercept / period_count,
        "avg_r2": total_r2 / period_count,
        "avg_adjusted_r2": total_adj_r2 / period_count,
        "avg_n": total_n / period_count,
        "period_count": period_count,
    }


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
    is_eps = metric_type in ("pEPS", "pEPS_GAAP")
    vals: list[float] = []

    for t in tickers:
        d = data["fm"].get(t)
        if d is None:
            continue
        # Per-ticker key resolution based on epsMarketType
        mk = (
            _resolve_eps_keys(metric_type, d)[0]
            if is_eps
            else MULTIPLE_KEYS[metric_type]
        )
        m_arr = d.get(mk, [])
        m = m_arr[di] if di < len(m_arr) else None
        if m is None:
            continue

        if is_eps:
            if not ok_eps(data, t, di, metric_type):
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
    eps_growth_gaap: float | None = None,
    forward_targets: list[dict] | None = None,
    current_price: float | None = None,
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
        "pe_gaap": None,
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
        # GAAP P/E
        pe_gaap_arr = fm.get("pe_gaap", [])
        if latest_di < len(pe_gaap_arr) and pe_gaap_arr[latest_di] is not None:
            ticker_actuals["pe_gaap"] = float(pe_gaap_arr[latest_di])

    # Determine GAAP EPS growth to use for regression input
    _eps_growth_gaap = eps_growth_gaap if eps_growth_gaap is not None else eps_growth

    # ---- Regression predictions for each metric type ----
    metric_types = ["evRev", "evGP", "pEPS", "pEPS_GAAP"]
    regression_results: list[dict] = []

    for mt in metric_types:
        # Resolve per-ticker keys for pEPS based on epsMarketType
        if mt in ("pEPS", "pEPS_GAAP") and ticker and ticker in data["fm"]:
            mk, gk = _resolve_eps_keys(mt, data["fm"][ticker])
        else:
            mk = MULTIPLE_KEYS[mt]
            gk = GROWTH_KEYS[mt]

        if gk == "rg":
            growth_rate = revenue_growth
        elif gk == "xg_gaap":
            growth_rate = _eps_growth_gaap
        else:
            growth_rate = eps_growth
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

        # Actual multiple for ticker (use resolved key)
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
        # Use resolved key for ticker_actuals lookup
        if mt in ("pEPS", "pEPS_GAAP") and ticker and ticker in data["fm"]:
            resolved_mk = _resolve_eps_keys(mt, data["fm"][ticker])[0]
        else:
            resolved_mk = MULTIPLE_KEYS[mt]
        tv = ticker_actuals.get(resolved_mk)
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
            if mt in ("pEPS", "pEPS_GAAP") and ticker in data["fm"]:
                resolved_mk = _resolve_eps_keys(mt, data["fm"][ticker])[0]
            else:
                resolved_mk = MULTIPLE_KEYS[mt]
            tv = ticker_actuals.get(resolved_mk)
            stats = compute_peer_stats(data, mt, latest_di, ind_tickers, tv)
            stats["metric_type"] = mt
            stats["metric_label"] = METRIC_LABELS[mt]
            stats["industry"] = industry
            industry_context.append(stats)

    # ---- Forward price targets ----
    forward_target_results: list[dict] | None = None
    if forward_targets:
        forward_target_results = compute_forward_targets(
            data=data,
            targets=forward_targets,
            current_price=current_price,
            dcf_discount_rate=dcf_discount_rate,
            dcf_terminal_growth=dcf_terminal_growth,
            dcf_fade_period=dcf_fade_period,
        )

    return {
        "ticker": ticker,
        "industry": industry,
        "date_count": len(data["dates"]),
        "regression": regression_results,
        "dcf": dcf_result,
        "peer_context": peer_context,
        "industry_context": industry_context,
        "forward_targets": forward_target_results,
    }


# ---------------------------------------------------------------------------
# 13. DCF at horizon (reuses compute_dcf for a future starting point)
# ---------------------------------------------------------------------------
def compute_dcf_at_horizon(
    forward_eps_at_horizon: float,
    eps_growth_at_horizon: float,
    discount_rate: float = 0.10,
    terminal_growth: float = 0.0,
    fade_period: int = 5,
) -> float | None:
    """Compute DCF-implied P/E starting from a future horizon's EPS and growth.

    Uses compute_dcf() with a single-year growth estimate (the horizon-year
    growth rate), then fades to terminal.  Returns implied P/E or None.
    """
    result = compute_dcf(
        forward_eps=forward_eps_at_horizon,
        eps_growth_estimates=[eps_growth_at_horizon],
        discount_rate=discount_rate,
        terminal_growth=terminal_growth,
        fade_period=fade_period,
    )
    if result is None:
        return None
    return result["implied_pe"]


# ---------------------------------------------------------------------------
# 14. Forward price targets
# ---------------------------------------------------------------------------
def compute_forward_targets(
    data: dict,
    targets: list[dict],
    current_price: float | None = None,
    dcf_discount_rate: float = 0.10,
    dcf_terminal_growth: float = 0.0,
    dcf_fade_period: int = 5,
) -> list[dict]:
    """Compute regression-implied and DCF target prices at future horizons.

    For each target horizon:
      1. Spot P/EPS regression (full universe, latest date)
      2. Historical baseline P/EPS regression (avg across all dates)
      3. DCF cross-check via compute_dcf_at_horizon()
      4. target_price = implied_pe * forward_eps_at_horizon
      5. upside_pct = (target_price / current_price - 1) * 100

    Regressions are cached across targets (same universe-wide regression).
    """
    if not targets:
        return []

    all_tickers: list[str] = data["tickers"]
    latest_di = len(data["dates"]) - 1

    # Cache spot + historical P/EPS regressions (same for all horizons)
    spot = compute_spot_regression(data, "pEPS", latest_di, all_tickers)
    hist = compute_historical_baseline(data, "pEPS", all_tickers)

    spot_stats: dict | None = None
    if spot:
        spot_stats = {
            "slope": spot["slope"],
            "intercept": spot["intercept"],
            "r2": spot["r2"],
            "n": spot["n"],
        }

    hist_stats: dict | None = None
    if hist:
        hist_stats = {
            "slope": hist["avg_slope"],
            "intercept": hist["avg_intercept"],
            "r2": hist["avg_r2"],
            "n": hist["avg_n"],
        }

    results: list[dict] = []
    for t in targets:
        horizon_years = t["horizon_years"]
        eps_growth = t["eps_growth_at_horizon"]
        fwd_eps = t["forward_eps_at_horizon"]
        growth_pct = eps_growth * 100

        # Spot regression-implied P/E
        spot_pe: float | None = None
        spot_target: float | None = None
        if spot:
            spot_pe = spot["slope"] * growth_pct + spot["intercept"]
            if spot_pe is not None and spot_pe > 0:
                spot_target = spot_pe * fwd_eps

        # Historical regression-implied P/E
        hist_pe: float | None = None
        hist_target: float | None = None
        if hist:
            hist_pe = hist["avg_slope"] * growth_pct + hist["avg_intercept"]
            if hist_pe is not None and hist_pe > 0:
                hist_target = hist_pe * fwd_eps

        # DCF cross-check
        dcf_pe = compute_dcf_at_horizon(
            forward_eps_at_horizon=fwd_eps,
            eps_growth_at_horizon=eps_growth,
            discount_rate=dcf_discount_rate,
            terminal_growth=dcf_terminal_growth,
            fade_period=dcf_fade_period,
        )
        dcf_target: float | None = None
        if dcf_pe is not None and dcf_pe > 0:
            dcf_target = dcf_pe * fwd_eps

        # Upside calculations
        spot_upside: float | None = None
        hist_upside: float | None = None
        dcf_upside: float | None = None
        if current_price is not None and current_price > 0:
            if spot_target is not None:
                spot_upside = (spot_target / current_price - 1) * 100
            if hist_target is not None:
                hist_upside = (hist_target / current_price - 1) * 100
            if dcf_target is not None:
                dcf_upside = (dcf_target / current_price - 1) * 100

        results.append(
            {
                "horizon_years": horizon_years,
                "eps_growth_at_horizon_pct": growth_pct,
                "forward_eps_at_horizon": fwd_eps,
                "spot_implied_pe": spot_pe,
                "spot_target_price": spot_target,
                "spot_regression_stats": spot_stats,
                "historical_implied_pe": hist_pe,
                "historical_target_price": hist_target,
                "historical_regression_stats": hist_stats,
                "dcf_implied_pe": dcf_pe,
                "dcf_target_price": dcf_target,
                "current_price": current_price,
                "spot_upside_pct": spot_upside,
                "historical_upside_pct": hist_upside,
                "dcf_upside_pct": dcf_upside,
            }
        )

    return results


# ---------------------------------------------------------------------------
# 15. Index-based regression
# ---------------------------------------------------------------------------
def compute_index_regression(
    data: dict,
    metric_type: str,
    index_tickers: list[str],
    di: int | None = None,
) -> dict | None:
    """Run spot + historical baseline regression using only tickers from a specific index.

    Args:
        data: Dashboard data dict.
        metric_type: One of 'evRev', 'evGP', 'pEPS'.
        index_tickers: Tickers belonging to this index.
        di: Date index for spot regression. Defaults to latest.

    Returns a dict with spot and historical stats, or None if insufficient data.
    """
    if di is None:
        di = len(data["dates"]) - 1

    # Only keep tickers that exist in the snapshot
    valid_tickers = [t for t in index_tickers if t in data["fm"]]
    if len(valid_tickers) < 3:
        return None

    spot = compute_spot_regression(data, metric_type, di, valid_tickers)
    hist = compute_historical_baseline(data, metric_type, valid_tickers)

    return {
        "spot": spot,
        "historical": hist,
        "ticker_count": len(valid_tickers),
    }


# ---------------------------------------------------------------------------
# 14. Peer-based composite valuation
# ---------------------------------------------------------------------------
def compute_peer_valuation(
    data: dict,
    ticker: str,
    similar_tickers: list[dict],
    indices_map: dict[str, list[str]],
    revenue_growth: float,
    eps_growth: float,
    forward_eps: float | None = None,
    current_pe: float | None = None,
    eps_growth_estimates: list[float] | None = None,
    dcf_discount_rate: float = 0.10,
    dcf_terminal_growth: float = 0.0,
    dcf_fade_period: int = 5,
    forward_targets: list[dict] | None = None,
    current_price: float | None = None,
) -> dict:
    """Orchestrate peer-based valuation with index regressions.

    Steps:
        1. Group similar stocks by their index memberships.
        2. For each index with enough peers, run full index regression.
        3. Predict implied multiple from each index regression.
        4. Weight predictions by (peer similarity in that index) * (R² of regression).
        5. Also run DCF and peer stats on the similar-stock subset.

    Args:
        data: Dashboard data dict.
        ticker: Target ticker.
        similar_tickers: [{ticker, score, description}, ...] from similarity search.
        indices_map: {ticker: [index_short_names]} mapping.
        revenue_growth: Target's revenue growth (decimal).
        eps_growth: Target's EPS growth (decimal).
        forward_eps: Target's forward EPS (for DCF).
        current_pe: Target's current P/E.
        eps_growth_estimates: Year-by-year EPS growth for DCF.
        dcf_*: DCF parameters.

    Returns comprehensive result dict.
    """
    latest_di = len(data["dates"]) - 1
    metric_types = ["evRev", "evGP", "pEPS", "pEPS_GAAP"]

    # Build peer ticker list
    peer_tickers = [p["ticker"] for p in similar_tickers if p["ticker"] in data["fm"]]
    peer_scores = {p["ticker"]: p["score"] for p in similar_tickers}

    # Group peers by index
    index_peer_groups: dict[str, list[str]] = {}
    for pt in peer_tickers:
        pt_indices = indices_map.get(pt, [])
        for idx_name in pt_indices:
            index_peer_groups.setdefault(idx_name, []).append(pt)

    # Collect all tickers per index (full membership, not just peers)
    index_all_tickers: dict[str, list[str]] = {}
    for t, idx_list in indices_map.items():
        for idx_name in idx_list:
            index_all_tickers.setdefault(idx_name, []).append(t)

    # Per-metric index regressions
    index_regression_results: list[dict] = []
    composite_predictions: dict[str, list[tuple[float, float]]] = {
        mt: [] for mt in metric_types
    }
    historical_composite_predictions: dict[str, list[tuple[float, float]]] = {
        mt: [] for mt in metric_types
    }

    for idx_name, idx_peers in index_peer_groups.items():
        idx_tickers = index_all_tickers.get(idx_name, [])
        if len(idx_tickers) < 10:
            continue

        # Average similarity score of peers in this index
        avg_peer_score = sum(peer_scores.get(p, 0) for p in idx_peers) / len(idx_peers)

        idx_regressions: list[dict] = []
        for mt in metric_types:
            gk = GROWTH_KEYS[mt]
            growth_rate = revenue_growth if gk == "rg" else eps_growth
            growth_pct = growth_rate * 100

            reg_result = compute_index_regression(data, mt, idx_tickers, latest_di)
            if reg_result is None or reg_result["spot"] is None:
                idx_regressions.append(
                    {
                        "metric_type": mt,
                        "metric_label": METRIC_LABELS[mt],
                        "regression": None,
                        "implied_multiple": None,
                        "historical_implied_multiple": None,
                    }
                )
                continue

            spot = reg_result["spot"]
            implied = spot["slope"] * growth_pct + spot["intercept"]
            r2 = spot["r2"]

            # Historical implied multiple
            hist = reg_result.get("historical")
            historical_implied: float | None = None
            if hist:
                historical_implied = (
                    hist["avg_slope"] * growth_pct + hist["avg_intercept"]
                )
                # Accumulate for historical composite
                hist_r2 = hist.get("avg_r2", 0)
                hist_weight = avg_peer_score * hist_r2
                if hist_weight > 0 and historical_implied > 0:
                    historical_composite_predictions[mt].append(
                        (historical_implied, hist_weight)
                    )

            # Weight = similarity * R²
            weight = avg_peer_score * r2
            if weight > 0 and implied > 0:
                composite_predictions[mt].append((implied, weight))

            idx_regressions.append(
                {
                    "metric_type": mt,
                    "metric_label": METRIC_LABELS[mt],
                    "regression": spot,
                    "implied_multiple": implied,
                    "historical_implied_multiple": historical_implied,
                    "historical": reg_result.get("historical"),
                }
            )

        index_regression_results.append(
            {
                "index_name": idx_name,
                "peer_count_in_index": len(idx_peers),
                "total_index_tickers": len(idx_tickers),
                "avg_peer_similarity": avg_peer_score,
                "regressions": idx_regressions,
            }
        )

    # Compute weighted composite implied multiples (spot + historical)
    composite: list[dict] = []
    historical_composite: list[dict] = []
    for mt in metric_types:
        # Get actual multiple for deviation (per-ticker EPS key resolution)
        actual: float | None = None
        if ticker in data["fm"]:
            td = data["fm"][ticker]
            is_eps = mt in ("pEPS", "pEPS_GAAP")
            mk = _resolve_eps_keys(mt, td)[0] if is_eps else MULTIPLE_KEYS[mt]
            vals = td.get(mk, [])
            if latest_di < len(vals) and vals[latest_di] is not None:
                actual = float(vals[latest_di])

        # Spot composite
        predictions = composite_predictions[mt]
        if not predictions:
            composite.append(
                {
                    "metric_type": mt,
                    "metric_label": METRIC_LABELS[mt],
                    "weighted_implied_multiple": None,
                    "num_indices": 0,
                }
            )
        else:
            total_weight = sum(w for _, w in predictions)
            weighted_sum = sum(v * w for v, w in predictions)
            weighted_avg = weighted_sum / total_weight if total_weight > 0 else None

            deviation: float | None = None
            if actual is not None and weighted_avg is not None and weighted_avg > 0:
                deviation = ((actual - weighted_avg) / weighted_avg) * 100

            composite.append(
                {
                    "metric_type": mt,
                    "metric_label": METRIC_LABELS[mt],
                    "weighted_implied_multiple": weighted_avg,
                    "actual_multiple": actual,
                    "deviation_pct": deviation,
                    "num_indices": len(predictions),
                }
            )

        # Historical composite
        hist_preds = historical_composite_predictions[mt]
        if not hist_preds:
            historical_composite.append(
                {
                    "metric_type": mt,
                    "metric_label": METRIC_LABELS[mt],
                    "weighted_implied_multiple": None,
                    "num_indices": 0,
                }
            )
        else:
            hist_total_w = sum(w for _, w in hist_preds)
            hist_weighted_sum = sum(v * w for v, w in hist_preds)
            hist_weighted_avg = (
                hist_weighted_sum / hist_total_w if hist_total_w > 0 else None
            )

            hist_deviation: float | None = None
            if (
                actual is not None
                and hist_weighted_avg is not None
                and hist_weighted_avg > 0
            ):
                hist_deviation = (
                    (actual - hist_weighted_avg) / hist_weighted_avg
                ) * 100

            historical_composite.append(
                {
                    "metric_type": mt,
                    "metric_label": METRIC_LABELS[mt],
                    "weighted_implied_multiple": hist_weighted_avg,
                    "actual_multiple": actual,
                    "deviation_pct": hist_deviation,
                    "num_indices": len(hist_preds),
                }
            )

    # Peer stats on just the similar-stock subset
    peer_stats: list[dict] = []
    for mt in metric_types:
        is_eps = mt in ("pEPS", "pEPS_GAAP")
        tv: float | None = None
        if ticker in data["fm"]:
            td = data["fm"][ticker]
            mk = _resolve_eps_keys(mt, td)[0] if is_eps else MULTIPLE_KEYS[mt]
            vals_arr = td.get(mk, [])
            val = vals_arr[latest_di] if latest_di < len(vals_arr) else None
            if val is not None:
                tv = float(val)
        stats = compute_peer_stats(data, mt, latest_di, peer_tickers, tv)
        stats["metric_type"] = mt
        stats["metric_label"] = METRIC_LABELS[mt]
        peer_stats.append(stats)

    # DCF on target
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

    # Forward price targets
    forward_target_results: list[dict] | None = None
    if forward_targets:
        forward_target_results = compute_forward_targets(
            data=data,
            targets=forward_targets,
            current_price=current_price,
            dcf_discount_rate=dcf_discount_rate,
            dcf_terminal_growth=dcf_terminal_growth,
            dcf_fade_period=dcf_fade_period,
        )

    return {
        "ticker": ticker,
        "peer_count": len(peer_tickers),
        "similar_tickers": similar_tickers,
        "index_regressions": index_regression_results,
        "composite_valuation": composite,
        "historical_composite_valuation": historical_composite,
        "peer_stats": peer_stats,
        "dcf": dcf_result,
        "forward_targets": forward_target_results,
    }
