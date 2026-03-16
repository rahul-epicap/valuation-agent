"""Tests for prepare.py — dataset building and baseline regression."""

from __future__ import annotations

import numpy as np

from research.prepare import (
    PreparedDataset,
    _build_arrays,
    _build_index_dummies,
    _build_temporal_splits,
    _build_valid_masks,
    _ok_eps,
    build_dataset,
    get_baseline_points,
    get_baseline_r2,
)


def _make_test_data(n_dates: int = 24, n_tickers: int = 10) -> dict:
    """Create synthetic dashboard data for testing."""
    dates = [f"2024-{m:02d}-01" for m in range(1, n_dates + 1)]
    tickers = [f"TK{i}" for i in range(n_tickers)]
    industries = {t: f"Industry_{i % 3}" for i, t in enumerate(tickers)}

    rng = np.random.RandomState(42)

    fm = {}
    for t in tickers:
        growth = rng.uniform(0.05, 0.40, n_dates).tolist()
        # Multiple correlates with growth + noise (realistic)
        er = [g * 100 + rng.normal(10, 3) for g in growth]
        eg = [e / rng.uniform(0.3, 0.7) for e in er]
        pe = [rng.uniform(15, 50) for _ in range(n_dates)]
        xg = [rng.uniform(0.05, 0.30) for _ in range(n_dates)]
        fe = [rng.uniform(2.0, 10.0) for _ in range(n_dates)]

        fm[t] = {
            "er": er,
            "eg": eg,
            "pe": pe,
            "rg": growth,
            "xg": xg,
            "fe": fe,
        }

    return {
        "dates": dates,
        "tickers": tickers,
        "industries": industries,
        "indices": {
            "TK0": ["SP500", "NASDAQ"],
            "TK1": ["SP500"],
            "TK2": ["NASDAQ"],
            "TK3": ["SP500", "NASDAQ"],
            "TK4": ["SP500"],
        },
        "fm": fm,
    }


class TestBuildArrays:
    def test_shapes(self):
        data = _make_test_data(24, 10)
        multiples, growth, gm = _build_arrays(data, data["tickers"], len(data["dates"]))

        assert multiples["evRev"].shape == (24, 10)
        assert growth["evRev"].shape == (24, 10)
        assert gm.shape == (24, 10)

    def test_no_nans_in_clean_data(self):
        data = _make_test_data()
        multiples, growth, gm = _build_arrays(data, data["tickers"], len(data["dates"]))

        # Synthetic data has no nulls, so no NaN
        assert not np.any(np.isnan(multiples["evRev"]))
        assert not np.any(np.isnan(growth["evRev"]))

    def test_gross_margin_computed(self):
        data = _make_test_data()
        multiples, _, gm = _build_arrays(data, data["tickers"], len(data["dates"]))

        # gm = er / eg for each point
        expected = multiples["evRev"] / multiples["evGP"]
        np.testing.assert_allclose(gm, expected, rtol=1e-10)


class TestValidMasks:
    def test_outlier_caps(self):
        data = _make_test_data(12, 5)
        # Set one point to exceed outlier cap
        data["fm"]["TK0"]["er"][0] = 100.0  # > 80x cap

        multiples, growth, _ = _build_arrays(data, data["tickers"], len(data["dates"]))
        masks = _build_valid_masks(multiples, growth, data, data["tickers"], len(data["dates"]))

        # TK0 at date 0 should be masked out for evRev
        assert not masks["evRev"][0, 0]

    def test_valid_points_pass(self):
        data = _make_test_data()
        multiples, growth, _ = _build_arrays(data, data["tickers"], len(data["dates"]))
        masks = _build_valid_masks(multiples, growth, data, data["tickers"], len(data["dates"]))

        # Most points in clean synthetic data should be valid
        assert masks["evRev"].sum() > 0.8 * masks["evRev"].size


class TestIndexDummies:
    def test_dummies_created(self):
        data = _make_test_data()
        dummies = _build_index_dummies(data["indices"], data["tickers"])

        # SP500 has TK0, TK1, TK3, TK4 = 4 members (≥3, should be included)
        assert "SP500" in dummies
        assert dummies["SP500"].sum() == 4

    def test_min_members_filter(self):
        # Index with only 2 members should be excluded
        indices = {"TK0": ["SMALL_INDEX"], "TK1": ["SMALL_INDEX"]}
        dummies = _build_index_dummies(indices, ["TK0", "TK1", "TK2"])
        assert "SMALL_INDEX" not in dummies


class TestTemporalSplits:
    def test_split_count(self):
        splits = _build_temporal_splits(n_dates=24, train_window=12, stride=1)
        # With 24 dates, train on [0:12] test on 12, ..., train on [11:23] test on 23
        assert len(splits) == 12

    def test_split_structure(self):
        splits = _build_temporal_splits(n_dates=24, train_window=12)
        first = splits[0]
        assert len(first.train_date_indices) == 12
        assert first.test_date_idx == 12
        np.testing.assert_array_equal(first.train_date_indices, np.arange(12))


class TestBuildDataset:
    def test_full_build(self):
        data = _make_test_data()
        dataset = build_dataset(data)

        assert isinstance(dataset, PreparedDataset)
        assert dataset.n_dates == 24
        assert dataset.n_tickers == 10
        assert dataset.n_splits > 0
        assert "evRev" in dataset.multiples
        assert "evRev" in dataset.valid_masks


class TestBaselineRegression:
    def test_baseline_points(self):
        data = _make_test_data()
        dataset = build_dataset(data)
        X, y = get_baseline_points(dataset, "evRev", 0)

        assert len(X) == len(y)
        assert len(X) > 0
        # X should be in percentage space
        assert X.mean() > 1.0  # Growth rates * 100

    def test_baseline_r2(self):
        data = _make_test_data()
        dataset = build_dataset(data)
        result = get_baseline_r2(dataset, "evRev", 0)

        assert result is not None
        assert "r2" in result
        assert "slope" in result
        assert "intercept" in result
        assert "n" in result
        assert 0 <= result["r2"] <= 1.0
        assert result["n"] >= 3


class TestOkEps:
    def test_valid_eps(self):
        d = {"fe": [5.0], "xg": [0.15]}
        assert _ok_eps(d, 0, "pEPS")

    def test_low_fe_rejected(self):
        d = {"fe": [0.3], "xg": [0.15]}
        assert not _ok_eps(d, 0, "pEPS")

    def test_extreme_growth_rejected(self):
        d = {"fe": [5.0], "xg": [3.0]}  # > 200%
        assert not _ok_eps(d, 0, "pEPS")

    def test_negative_growth_rejected(self):
        d = {"fe": [5.0], "xg": [-0.8]}  # < -75%
        assert not _ok_eps(d, 0, "pEPS")
