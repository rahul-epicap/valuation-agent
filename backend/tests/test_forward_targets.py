"""Tests for forward price target computation."""

from __future__ import annotations

import pytest

from app.services.valuation_service import (
    compute_dcf_at_horizon,
    compute_forward_targets,
)


# -- Minimal dashboard data fixture --
@pytest.fixture
def sample_data() -> dict:
    """Minimal dashboard data with enough tickers for regression (>= 3)."""
    tickers = ["A", "B", "C", "D", "E"]
    dates = ["2025-01-01", "2025-02-01"]
    fm: dict = {}
    # Create tickers with known multiples and growth so regression is well-defined
    for i, t in enumerate(tickers):
        growth = 0.10 + i * 0.05  # 10%, 15%, 20%, 25%, 30%
        pe = 20 + i * 5  # 20x, 25x, 30x, 35x, 40x
        fm[t] = {
            "er": [5.0 + i, 5.0 + i],
            "eg": [8.0 + i, 8.0 + i],
            "pe": [pe, pe],
            "rg": [growth, growth],
            "xg": [growth, growth],
            "fe": [5.0, 5.0],
        }
    return {
        "tickers": tickers,
        "dates": dates,
        "industries": {t: "Tech" for t in tickers},
        "fm": fm,
    }


class TestComputeDcfAtHorizon:
    def test_basic(self) -> None:
        result = compute_dcf_at_horizon(
            forward_eps_at_horizon=10.0,
            eps_growth_at_horizon=0.15,
            discount_rate=0.10,
            terminal_growth=0.02,
            fade_period=5,
        )
        assert result is not None
        assert result > 0

    def test_returns_none_for_zero_eps(self) -> None:
        result = compute_dcf_at_horizon(
            forward_eps_at_horizon=0.0,
            eps_growth_at_horizon=0.15,
        )
        assert result is None

    def test_returns_none_when_dr_lte_tg(self) -> None:
        result = compute_dcf_at_horizon(
            forward_eps_at_horizon=10.0,
            eps_growth_at_horizon=0.15,
            discount_rate=0.05,
            terminal_growth=0.05,
        )
        assert result is None


class TestComputeForwardTargets:
    def test_empty_targets(self, sample_data: dict) -> None:
        result = compute_forward_targets(data=sample_data, targets=[])
        assert result == []

    def test_single_target(self, sample_data: dict) -> None:
        targets = [
            {
                "horizon_years": 2,
                "eps_growth_at_horizon": 0.15,
                "forward_eps_at_horizon": 12.50,
            }
        ]
        result = compute_forward_targets(
            data=sample_data,
            targets=targets,
            current_price=400.0,
        )
        assert len(result) == 1
        r = result[0]
        assert r["horizon_years"] == 2
        assert r["eps_growth_at_horizon_pct"] == 15.0
        assert r["forward_eps_at_horizon"] == 12.50
        # Spot regression should produce a P/E
        assert r["spot_implied_pe"] is not None
        assert r["spot_target_price"] is not None
        # Historical regression should produce a P/E
        assert r["historical_implied_pe"] is not None
        assert r["historical_target_price"] is not None
        # DCF should produce a P/E
        assert r["dcf_implied_pe"] is not None
        assert r["dcf_target_price"] is not None
        # Upside should be computed
        assert r["spot_upside_pct"] is not None
        assert r["current_price"] == 400.0

    def test_no_current_price(self, sample_data: dict) -> None:
        targets = [
            {
                "horizon_years": 5,
                "eps_growth_at_horizon": 0.10,
                "forward_eps_at_horizon": 18.20,
            }
        ]
        result = compute_forward_targets(
            data=sample_data,
            targets=targets,
            current_price=None,
        )
        assert len(result) == 1
        r = result[0]
        # Target prices should still be computed
        assert r["spot_target_price"] is not None
        # But upside should be None
        assert r["spot_upside_pct"] is None
        assert r["historical_upside_pct"] is None
        assert r["dcf_upside_pct"] is None
        assert r["current_price"] is None

    def test_multiple_targets_share_regression(self, sample_data: dict) -> None:
        targets = [
            {
                "horizon_years": 2,
                "eps_growth_at_horizon": 0.15,
                "forward_eps_at_horizon": 12.50,
            },
            {
                "horizon_years": 5,
                "eps_growth_at_horizon": 0.10,
                "forward_eps_at_horizon": 18.20,
            },
        ]
        result = compute_forward_targets(
            data=sample_data,
            targets=targets,
            current_price=400.0,
        )
        assert len(result) == 2
        # Both should share the same regression stats
        assert result[0]["spot_regression_stats"] == result[1]["spot_regression_stats"]
        assert (
            result[0]["historical_regression_stats"]
            == result[1]["historical_regression_stats"]
        )
        # But different target prices (different EPS inputs)
        assert result[0]["spot_target_price"] != result[1]["spot_target_price"]
