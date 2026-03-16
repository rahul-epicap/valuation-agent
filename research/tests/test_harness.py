"""Tests for the evaluation harness."""

from __future__ import annotations

import numpy as np
import pytest

from research.evaluation.metrics import adjusted_r2, composite_score, oos_r2, stability_score


class TestOosR2:
    def test_perfect_prediction(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert oos_r2(y_true, y_pred) == pytest.approx(1.0)

    def test_mean_prediction(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y_pred = np.full(5, 3.0)  # Predicting the mean
        assert oos_r2(y_true, y_pred) == pytest.approx(0.0)

    def test_worse_than_mean(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([10.0, 10.0, 10.0])  # Way off
        assert oos_r2(y_true, y_pred) < 0.0

    def test_partial_fit(self):
        y_true = np.array([1.0, 2.0, 3.0, 4.0])
        y_pred = np.array([1.5, 2.5, 2.5, 3.5])
        r2 = oos_r2(y_true, y_pred)
        assert 0.0 < r2 < 1.0


class TestAdjustedR2:
    def test_penalizes_features(self):
        # Same R², more features → lower adjusted R²
        adj1 = adjusted_r2(0.5, 100, 1)
        adj5 = adjusted_r2(0.5, 100, 5)
        adj10 = adjusted_r2(0.5, 100, 10)
        assert adj1 > adj5 > adj10

    def test_perfect_r2(self):
        assert adjusted_r2(1.0, 100, 5) == pytest.approx(1.0)

    def test_too_few_observations(self):
        assert adjusted_r2(0.5, 3, 3) == 0.0


class TestStabilityScore:
    def test_perfect_stability(self):
        r2s = [0.5, 0.5, 0.5, 0.5, 0.5]
        assert stability_score(r2s) == pytest.approx(1.0)

    def test_unstable(self):
        r2s = [0.1, 0.9, 0.2, 0.8, 0.3]
        score = stability_score(r2s)
        assert 0.0 < score < 1.0

    def test_too_few_values(self):
        assert stability_score([0.5, 0.5]) == 0.0

    def test_ignores_negative(self):
        r2s = [-0.5, 0.3, 0.3, 0.3, 0.3]
        score = stability_score(r2s)
        # Should ignore the negative value
        assert score > 0.5


class TestCompositeScore:
    def test_baseline(self):
        score = composite_score(
            oos_r2_val=0.5,
            stability_val=0.8,
            adj_r2_val=0.45,
            interpretability_val=0.7,
        )
        expected = 0.4 * 0.5 + 0.25 * 0.8 + 0.20 * 0.45 + 0.15 * 0.7
        assert score == pytest.approx(expected)

    def test_negative_r2_clamped(self):
        score = composite_score(
            oos_r2_val=-0.5,
            stability_val=0.8,
            adj_r2_val=-0.3,
            interpretability_val=0.5,
        )
        # Negative values clamped to 0
        assert score >= 0.0

    def test_custom_weights(self):
        score = composite_score(
            oos_r2_val=1.0,
            stability_val=0.0,
            adj_r2_val=0.0,
            interpretability_val=0.0,
            weights={"oos_r2": 1.0, "stability": 0.0, "adjusted_r2": 0.0, "interpretability": 0.0},
        )
        assert score == pytest.approx(1.0)
