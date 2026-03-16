"""Tests for experiment runner — end-to-end evaluation of train.py."""

from __future__ import annotations

import numpy as np

from research.evaluation.harness import evaluate_experiment
from research.prepare import build_dataset


def _make_test_data(n_dates: int = 24, n_tickers: int = 20) -> dict:
    """Create synthetic dashboard data for testing."""
    dates = [f"2024-{(m % 12) + 1:02d}-01" for m in range(n_dates)]
    tickers = [f"TK{i}" for i in range(n_tickers)]

    rng = np.random.RandomState(42)
    fm = {}
    for t in tickers:
        growth = rng.uniform(0.05, 0.40, n_dates).tolist()
        er = [g * 80 + rng.normal(10, 3) for g in growth]
        eg = [e / rng.uniform(0.3, 0.7) for e in er]
        pe = [rng.uniform(15, 50) for _ in range(n_dates)]
        xg = [rng.uniform(0.05, 0.30) for _ in range(n_dates)]
        fe = [rng.uniform(2.0, 10.0) for _ in range(n_dates)]

        fm[t] = {"er": er, "eg": eg, "pe": pe, "rg": growth, "xg": xg, "fe": fe}

    return {
        "dates": dates,
        "tickers": tickers,
        "industries": {t: f"Ind_{i % 3}" for i, t in enumerate(tickers)},
        "indices": {},
        "fm": fm,
    }


class TestEndToEnd:
    def test_baseline_evaluation(self, tmp_path):
        """Test that the baseline train.py can be evaluated end-to-end."""
        from research.config.settings import settings

        data = _make_test_data()
        dataset = build_dataset(data)

        result = evaluate_experiment(
            dataset,
            metric_type="evRev",
            train_py_path=settings.train_py_path,
            max_splits=5,
        )

        assert result.error is None, f"Experiment failed: {result.error}"
        assert result.model_description  # non-empty description
        assert result.n_features >= 1
        assert len(result.split_results) == 5
        assert result.elapsed_seconds > 0

    def test_composite_score_reasonable(self):
        """Baseline composite score should be in a reasonable range on synthetic data."""
        data = _make_test_data()
        dataset = build_dataset(data)

        from research.config.settings import settings

        result = evaluate_experiment(
            dataset,
            metric_type="evRev",
            train_py_path=settings.train_py_path,
            max_splits=5,
        )

        assert result.error is None
        # Synthetic data has strong growth-multiple correlation
        assert result.composite > 0.0
