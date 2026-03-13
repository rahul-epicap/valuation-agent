"""CLI tool to generate a formatted valuation report from the API.

Usage:
    python scripts/valuation_report.py \
        --ticker AAPL \
        --revenue-growth 0.08 \
        --eps-growth 0.15 \
        --forward-targets '[{"horizon_years":2,"eps_growth_at_horizon":0.15,"forward_eps_at_horizon":12.50},{"horizon_years":5,"eps_growth_at_horizon":0.10,"forward_eps_at_horizon":18.20}]' \
        --current-price 400.00
"""

from __future__ import annotations

import argparse
import json
import sys

import httpx

DEFAULT_API_URL = "http://localhost:8000"


def format_forward_targets(resp: dict) -> str:
    """Format the forward_targets section of a valuation response as markdown."""
    targets = resp.get("forward_targets")
    if not targets:
        return ""

    lines: list[str] = []
    lines.append("## Forward Price Targets\n")

    # Main table
    lines.append(
        "| Horizon | Fwd EPS Growth | Fwd EPS | Spot P/E | Hist P/E "
        "| DCF P/E | Spot Target | Hist Target | DCF Target |"
    )
    lines.append(
        "|---------|---------------|---------|----------|----------"
        "|---------|-------------|-------------|------------|"
    )
    for t in targets:
        horizon = f"{t['horizon_years']}Y"
        growth = f"{t['eps_growth_at_horizon_pct']:.1f}%"
        fwd_eps = f"${t['forward_eps_at_horizon']:.2f}"
        spot_pe = _fmt_pe(t.get("spot_implied_pe"))
        hist_pe = _fmt_pe(t.get("historical_implied_pe"))
        dcf_pe = _fmt_pe(t.get("dcf_implied_pe"))
        spot_tgt = _fmt_price(t.get("spot_target_price"))
        hist_tgt = _fmt_price(t.get("historical_target_price"))
        dcf_tgt = _fmt_price(t.get("dcf_target_price"))
        lines.append(
            f"| {horizon:<7} | {growth:<13} | {fwd_eps:<7} | {spot_pe:<8} "
            f"| {hist_pe:<8} | {dcf_pe:<7} | {spot_tgt:<11} | {hist_tgt:<11} "
            f"| {dcf_tgt:<10} |"
        )

    # Upside table (only if current_price is available)
    current_price = targets[0].get("current_price") if targets else None
    if current_price is not None:
        lines.append(f"\nCurrent Price: ${current_price:.2f}\n")
        lines.append("| Horizon | Spot Upside | Hist Upside | DCF Upside |")
        lines.append("|---------|------------|-------------|------------|")
        for t in targets:
            horizon = f"{t['horizon_years']}Y"
            spot_up = _fmt_upside(t.get("spot_upside_pct"))
            hist_up = _fmt_upside(t.get("historical_upside_pct"))
            dcf_up = _fmt_upside(t.get("dcf_upside_pct"))
            lines.append(
                f"| {horizon:<7} | {spot_up:<10} | {hist_up:<11} | {dcf_up:<10} |"
            )

    lines.append("")
    return "\n".join(lines)


def format_multi_factor(resp: dict) -> str:
    """Format the multi_factor_results section as markdown."""
    mf_results = resp.get("multi_factor_results")
    if not mf_results:
        return ""

    lines: list[str] = []
    lines.append("## Multi-Factor Regression\n")

    # Build R² comparison vs single-factor
    single_r2: dict[str, float] = {}
    for reg in resp.get("regression", []):
        spot = reg.get("spot_stats")
        if spot:
            single_r2[reg["metric_type"]] = spot["r2"]

    # Summary table
    lines.append(
        "| Metric | Single R² | Multi R² | Improvement "
        "| Growth Coeff | Factors | N |"
    )
    lines.append(
        "|--------|----------|---------|-------------"
        "|-------------|---------|---|"
    )
    for mf in mf_results:
        mt = mf["metric_type"]
        sf_r2 = single_r2.get(mt)
        mf_r2 = mf["r2"]
        delta = (mf_r2 - sf_r2) if sf_r2 is not None else None
        sf_str = f"{sf_r2:.4f}" if sf_r2 is not None else "N/A"
        delta_str = f"+{delta:.4f}" if delta is not None and delta > 0 else (
            f"{delta:.4f}" if delta is not None else "N/A"
        )
        lines.append(
            f"| {mt:<6} | {sf_str:<8} | {mf_r2:.4f}  | {delta_str:<11} "
            f"| {mf['growth_coefficient']:.4f}       | {len(mf['factors']):<7} | {mf['n']} |"
        )

    # Factor coefficients per metric
    for mf in mf_results:
        factors = mf.get("factors", [])
        if not factors:
            continue
        lines.append(f"\n### {mf['metric_type']} — Factor Coefficients\n")
        lines.append("| Factor | Coefficient | Effect |")
        lines.append("|--------|------------|--------|")
        for f in sorted(factors, key=lambda x: abs(x["coefficient"]), reverse=True):
            coeff = f["coefficient"]
            sign = "+" if coeff >= 0 else "\u2212"
            effect = f"{sign}{abs(coeff):.1f}x {'premium' if coeff >= 0 else 'discount'}"
            lines.append(f"| {f['name']:<6} | {coeff:+.3f}     | {effect} |")

    lines.append("")
    return "\n".join(lines)


def format_synthesis(resp: dict) -> str:
    """Format a brief synthesis section summarizing key signals."""
    lines: list[str] = []
    lines.append("## Synthesis\n")

    # Regression signals
    for reg in resp.get("regression", []):
        mt = reg["metric_label"]
        spot = reg.get("spot_predicted")
        hist = reg.get("historical_predicted")
        actual = reg.get("current_actual")
        if spot is not None:
            lines.append(f"- **{mt}** spot implied: {spot:.1f}x")
        if hist is not None:
            lines.append(f"  - Historical baseline: {hist:.1f}x")
        if actual is not None:
            lines.append(f"  - Current actual: {actual:.1f}x")

    # Multi-factor signal (brief summary)
    mf_results = resp.get("multi_factor_results")
    if mf_results:
        lines.append("- **Multi-Factor Regression:**")
        for mf in mf_results:
            sf_r2 = None
            for reg in resp.get("regression", []):
                if reg["metric_type"] == mf["metric_type"] and reg.get("spot_stats"):
                    sf_r2 = reg["spot_stats"]["r2"]
                    break
            delta = (mf["r2"] - sf_r2) if sf_r2 is not None else None
            delta_str = f" (+{delta:.4f})" if delta is not None and delta > 0 else ""
            top_factors = sorted(mf.get("factors", []), key=lambda x: abs(x["coefficient"]), reverse=True)[:3]
            factor_str = ", ".join(
                f"{f['name']} {f['coefficient']:+.1f}x" for f in top_factors
            )
            lines.append(
                f"  - {mf['metric_type']}: R\u00B2={mf['r2']:.4f}{delta_str}"
                f"  [{factor_str}]"
            )

    # DCF signal
    dcf = resp.get("dcf")
    if dcf:
        lines.append(f"- **DCF** implied P/E: {dcf['implied_pe']:.1f}x")
        if dcf.get("deviation_pct") is not None:
            lines.append(f"  - vs current: {dcf['deviation_pct']:+.1f}%")

    # Forward target signals
    targets = resp.get("forward_targets")
    if targets:
        lines.append("- **Forward Targets:**")
        for t in targets:
            horizon = f"{t['horizon_years']}Y"
            parts: list[str] = []
            if t.get("spot_target_price") is not None:
                parts.append(f"Spot ${t['spot_target_price']:.2f}")
            if t.get("historical_target_price") is not None:
                parts.append(f"Hist ${t['historical_target_price']:.2f}")
            if t.get("dcf_target_price") is not None:
                parts.append(f"DCF ${t['dcf_target_price']:.2f}")
            if parts:
                lines.append(f"  - {horizon}: {' / '.join(parts)}")

    lines.append("")
    return "\n".join(lines)


def run_valuation_report(
    api_url: str,
    ticker: str | None,
    revenue_growth: float,
    eps_growth: float,
    forward_eps: float | None = None,
    eps_growth_estimates: list[float] | None = None,
    forward_targets: list[dict] | None = None,
    current_price: float | None = None,
    snapshot_id: int | None = None,
    regression_factors: list[str] | None = None,
) -> str:
    """Call the valuation API and return a formatted markdown report."""
    payload: dict = {
        "revenue_growth": revenue_growth,
        "eps_growth": eps_growth,
    }
    if ticker:
        payload["ticker"] = ticker
    if forward_eps is not None:
        payload["forward_eps"] = forward_eps
    if eps_growth_estimates:
        payload["eps_growth_estimates"] = eps_growth_estimates
    if forward_targets:
        payload["forward_targets"] = forward_targets
    if current_price is not None:
        payload["current_price"] = current_price
    if snapshot_id is not None:
        payload["snapshot_id"] = snapshot_id
    if regression_factors:
        payload["regression_factors"] = regression_factors

    resp = httpx.post(f"{api_url}/api/valuation/estimate", json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    sections: list[str] = []
    title = "# Valuation Report"
    if ticker:
        title += f": {ticker}"
    sections.append(title)
    sections.append("")

    sections.append(format_synthesis(data))
    sections.append(format_multi_factor(data))
    sections.append(format_forward_targets(data))

    return "\n".join(sections)


# -- Helpers --
def _fmt_pe(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.1f}x"


def _fmt_price(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def _fmt_upside(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:+.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate valuation report from API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--ticker", default=None)
    parser.add_argument("--revenue-growth", type=float, required=True)
    parser.add_argument("--eps-growth", type=float, required=True)
    parser.add_argument("--forward-eps", type=float, default=None)
    parser.add_argument(
        "--eps-growth-estimates",
        type=str,
        default=None,
        help="JSON array of year-by-year EPS growth rates",
    )
    parser.add_argument(
        "--forward-targets",
        type=str,
        default=None,
        help="JSON array of forward target objects",
    )
    parser.add_argument("--current-price", type=float, default=None)
    parser.add_argument("--snapshot-id", type=int, default=None)
    parser.add_argument(
        "--regression-factors",
        type=str,
        default=None,
        help="JSON array of index names to use as regression factors (e.g. '[\"MSXXTECH\",\"MSXXMAG7\"]')",
    )

    args = parser.parse_args()

    eps_estimates = None
    if args.eps_growth_estimates:
        eps_estimates = json.loads(args.eps_growth_estimates)

    fwd_targets = None
    if args.forward_targets:
        fwd_targets = json.loads(args.forward_targets)

    reg_factors = None
    if args.regression_factors:
        reg_factors = json.loads(args.regression_factors)

    report = run_valuation_report(
        api_url=args.api_url,
        ticker=args.ticker,
        revenue_growth=args.revenue_growth,
        eps_growth=args.eps_growth,
        forward_eps=args.forward_eps,
        eps_growth_estimates=eps_estimates,
        forward_targets=fwd_targets,
        current_price=args.current_price,
        snapshot_id=args.snapshot_id,
        regression_factors=reg_factors,
    )
    sys.stdout.write(report)


if __name__ == "__main__":
    main()
