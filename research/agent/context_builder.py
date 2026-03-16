"""Builds LLM context from experiment history, leaderboard, and dataset stats."""

from __future__ import annotations

import numpy as np

from research.prepare import PreparedDataset


def build_results_summary(results_tsv_path: str, max_detailed: int = 8) -> str:
    """Build a summary of experiment results for the LLM context."""
    try:
        with open(results_tsv_path) as f:
            lines = f.read().strip().split("\n")
    except FileNotFoundError:
        return "No experiments run yet."

    if len(lines) <= 1:
        return "No experiments run yet."

    header = lines[0]
    rows = lines[1:]

    if not rows:
        return "No experiments run yet."

    # Show most recent experiments in detail
    recent = rows[-max_detailed:]
    summary_parts = [header]
    if len(rows) > max_detailed:
        summary_parts.append(f"... ({len(rows) - max_detailed} earlier experiments omitted)")
    summary_parts.extend(recent)

    return "\n".join(summary_parts)


def build_dataset_stats(dataset: PreparedDataset, metric_type: str) -> str:
    """Build dataset statistics summary for LLM context."""
    lines = [
        f"Metric: {metric_type}",
        f"Tickers: {dataset.n_tickers}",
        f"Dates: {dataset.n_dates} ({dataset.dates[0]} to {dataset.dates[-1]})",
        f"Temporal splits: {dataset.n_splits}",
        f"Index dummies available: {list(dataset.index_dummies.keys())}",
    ]

    # Multiple distribution stats
    m = dataset.multiples.get(metric_type)
    g = dataset.growth.get(metric_type)
    mask = dataset.valid_masks.get(metric_type)

    if m is not None and mask is not None:
        valid_m = m[mask]
        lines.append("\nMultiple distribution (valid points):")
        lines.append(f"  Count: {len(valid_m)}")
        lines.append(f"  Mean: {np.nanmean(valid_m):.2f}")
        lines.append(f"  Median: {np.nanmedian(valid_m):.2f}")
        lines.append(f"  Std: {np.nanstd(valid_m):.2f}")
        pcts = np.nanpercentile(valid_m, [5, 25, 75, 95])
        pct_str = " / ".join(f"{p:.2f}" for p in pcts)
        lines.append(f"  P5/P25/P75/P95: {pct_str}")

    if g is not None and mask is not None:
        valid_g = g[mask] * 100  # Convert to pct
        lines.append("\nGrowth distribution (valid points, %):")
        lines.append(f"  Mean: {np.nanmean(valid_g):.1f}%")
        lines.append(f"  Median: {np.nanmedian(valid_g):.1f}%")
        lines.append(f"  Std: {np.nanstd(valid_g):.1f}%")
        gpcts = np.nanpercentile(valid_g, [5, 25, 75, 95])
        gpct_str = " / ".join(f"{p:.1f}%" for p in gpcts)
        lines.append(f"  P5/P25/P75/P95: {gpct_str}")

    # Gross margin stats
    gm = dataset.gross_margin
    if gm is not None:
        valid_gm = gm[np.isfinite(gm)]
        if len(valid_gm) > 0:
            lines.append("\nGross margin (GP/Rev) distribution:")
            lines.append(f"  Mean: {np.nanmean(valid_gm):.3f}")
            lines.append(f"  Median: {np.nanmedian(valid_gm):.3f}")

    # Valid points per date (average)
    if mask is not None:
        per_date = mask.sum(axis=1)
        lines.append(
            f"\nValid points per date: mean={per_date.mean():.0f}, "
            f"min={per_date.min()}, max={per_date.max()}"
        )

    # FMP factors available
    if dataset.fmp_factor_names:
        lines.append(f"\nFMP factors available ({len(dataset.fmp_factor_names)} factors):")
        lines.append("  Access via: dataset.fmp_factors['factor_name'] -> (n_tickers,) array")
        lines.append("  All z-score standardized. NaN = missing. Mean-impute NaN before use.")
        lines.append("")

        # Group by category for readability
        categories = {
            "Size": ["log_market_cap"],
            "Risk/Vol": ["beta", "historical_vol_30d", "historical_vol_90d"],
            "Momentum": ["momentum_1m", "momentum_3m", "momentum_6m", "momentum_12m"],
            "Quality": [
                "roe",
                "roic",
                "return_on_assets",
                "return_on_capital",
                "gross_profit_margin",
                "operating_profit_margin",
                "net_profit_margin",
                "income_quality",
                "fcf_yield",
                "earnings_yield",
                "fcf_to_operating_cf",
                "asset_turnover",
            ],
            "Leverage": [
                "debt_to_equity",
                "debt_to_assets",
                "net_debt_to_ebitda",
                "interest_coverage",
                "current_ratio",
            ],
            "Hist Growth": [
                "revenue_growth_hist",
                "eps_growth_hist",
                "fcf_growth",
                "three_yr_rev_growth",
                "five_yr_rev_growth",
            ],
            "R&D/SBC": ["rd_to_revenue", "sbc_to_revenue", "capex_to_revenue"],
            "Analyst": [
                "n_analysts_eps",
                "eps_estimate_dispersion",
                "earnings_surprise_pct",
                "avg_earnings_surprise_4q",
            ],
            "Rating": ["rating_score"],
        }

        available = set(dataset.fmp_factor_names)
        for cat, factors in categories.items():
            present = [f for f in factors if f in available]
            if present:
                coverage = []
                for f in present:
                    arr = dataset.fmp_factors[f]
                    n_valid = int(np.isfinite(arr).sum())
                    coverage.append(f"{f}({n_valid})")
                lines.append(f"  {cat}: {', '.join(coverage)}")

    return "\n".join(lines)
