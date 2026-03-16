"""Individual evaluation metric implementations for regression experiments."""

from __future__ import annotations

import numpy as np


def oos_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Out-of-sample R² (coefficient of determination).

    Uses the standard definition: 1 - SS_res / SS_tot
    where SS_tot uses the test set mean (not training mean).

    Returns negative values if the model is worse than predicting the mean.
    """
    if len(y_true) < 2:
        return 0.0

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

    if ss_tot < 1e-12:
        return 0.0

    return float(1.0 - ss_res / ss_tot)


def adjusted_r2(r2: float, n: int, p: int) -> float:
    """Adjusted R² penalizing model complexity.

    Args:
        r2: Standard R² value.
        n: Number of observations.
        p: Number of predictors (excluding intercept).

    Returns:
        Adjusted R² value. Can be negative for overfit models.
    """
    if n <= p + 1:
        return 0.0
    return float(1.0 - (1.0 - r2) * (n - 1) / (n - p - 1))


def stability_score(r2_values: list[float] | np.ndarray) -> float:
    """Stability score: 1 - CV(R²) across temporal splits.

    A score of 1.0 means perfectly consistent R² across splits.
    Clipped to [0, 1] — negative means extremely unstable.
    """
    arr = np.array(r2_values)
    # Filter out NaN and negative R² (failed splits)
    arr = arr[np.isfinite(arr) & (arr > 0)]

    if len(arr) < 3:
        return 0.0

    mean_r2 = np.mean(arr)
    if mean_r2 < 1e-6:
        return 0.0

    cv = float(np.std(arr) / mean_r2)
    return float(np.clip(1.0 - cv, 0.0, 1.0))


def composite_score(
    oos_r2_val: float,
    stability_val: float,
    adj_r2_val: float,
    interpretability_val: float = 0.5,
    weights: dict[str, float] | None = None,
) -> float:
    """Compute weighted composite evaluation score.

    Default weights from settings:
        OOS R² (40%) + Stability (25%) + Adjusted R² (20%) + Interpretability (15%)
    """
    if weights is None:
        weights = {
            "oos_r2": 0.40,
            "stability": 0.25,
            "adjusted_r2": 0.20,
            "interpretability": 0.15,
        }

    score = (
        weights["oos_r2"] * max(oos_r2_val, 0.0)
        + weights["stability"] * max(stability_val, 0.0)
        + weights["adjusted_r2"] * max(adj_r2_val, 0.0)
        + weights["interpretability"] * max(interpretability_val, 0.0)
    )

    return float(score)
