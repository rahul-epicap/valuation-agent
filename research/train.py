"""Ridge regression with simplified, robust features for valuation multiples.

Required function signatures (do not change):
    build_features(dataset, date_idx, metric_type) -> (X, y, feature_names)
    fit_model(X_train, y_train) -> model
    predict(model, X_test) -> y_pred
    get_model_description() -> str
"""

from __future__ import annotations

import numpy as np

from research.prepare import PreparedDataset, get_baseline_points


def _winsorize(arr, lower=2, upper=98):
    """Winsorize array at given percentiles."""
    if len(arr) == 0:
        return arr
    lo = np.percentile(arr, lower)
    hi = np.percentile(arr, upper)
    return np.clip(arr, lo, hi)


def build_features(
    dataset: PreparedDataset,
    date_idx: int,
    metric_type: str,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extract features (X) and target (y) for a single date."""

    if metric_type == "pEPS":
        feature_names = [
            "growth_pct_w",
            "positive_growth",
            "growth_abs_capped",
        ]
    elif metric_type == "evRev":
        feature_names = [
            "growth_pct_w",
            "gross_margin",
            "growth_x_margin",
        ]
    else:  # evGP
        feature_names = [
            "growth_pct_w",
            "positive_growth",
            "log_growth_abs",
        ]

    empty_X = np.array([]).reshape(0, len(feature_names))

    # Get baseline growth% and valuation multiple for the primary metric
    X_flat, y = get_baseline_points(dataset, metric_type, date_idx)

    if len(X_flat) == 0 or len(y) == 0:
        return empty_X, np.array([]), feature_names

    growth_pct = X_flat.copy()

    # For EV/Rev, try to compute gross margin
    has_gm = False
    gm_raw = None
    if metric_type == "evRev":
        try:
            _, y_gp = get_baseline_points(dataset, "evGP", date_idx)
            if len(y_gp) == len(y):
                gm_raw = np.where((y_gp > 0) & np.isfinite(y_gp), y / y_gp, np.nan)
                gm_valid = np.isfinite(gm_raw) & (gm_raw > 0) & (gm_raw < 1.5)
                if gm_valid.sum() > 0.5 * len(y):
                    has_gm = True
        except Exception:
            has_gm = False

    # Filter valid observations
    if metric_type == "pEPS":
        # PE ratios: positive, finite, and within reasonable range
        valid = (y > 0) & (y < 150) & np.isfinite(y) & np.isfinite(growth_pct)
    else:
        valid = (y > 0) & np.isfinite(y) & np.isfinite(growth_pct)

    if has_gm and metric_type == "evRev":
        valid = valid & np.isfinite(gm_raw) & (gm_raw > 0) & (gm_raw < 1.5)

    if valid.sum() < 10:
        return empty_X, np.array([]), feature_names

    y = y[valid]
    growth_pct = growth_pct[valid]
    if has_gm:
        gm = gm_raw[valid]

    # Winsorize target
    if metric_type == "pEPS":
        y_w = _winsorize(y, 3, 97)
    else:
        y_w = _winsorize(y, 2, 98)

    # Winsorize growth
    growth_w = _winsorize(growth_pct, 3, 97)

    if metric_type == "pEPS":
        # Feature 1: Winsorized growth percentage (linear growth premium)
        f1 = growth_w

        # Feature 2: Positive growth indicator (discrete premium for positive EPS growth)
        f2 = (growth_w > 0).astype(float)

        # Feature 3: Absolute growth capped — captures magnitude effect symmetrically
        # Economic rationale: market penalizes large negative growth and rewards large positive
        # but the effect saturates; using abs captures the "uncertainty" premium at extremes
        f3 = np.abs(growth_w)

        X = np.column_stack([f1, f2, f3])

    elif metric_type == "evRev":
        # Feature 1: Winsorized growth percentage
        f1 = growth_w

        # Feature 2: Gross margin (profitability premium)
        if has_gm:
            gm_w = _winsorize(gm, 3, 97)
            f2 = gm_w
        else:
            f2 = np.zeros_like(f1)

        # Feature 3: Growth × Margin interaction
        f3 = f1 * f2

        X = np.column_stack([f1, f2, f3])

    else:  # evGP
        f1 = growth_w
        f2 = (growth_w > 0).astype(float)
        f3 = np.sign(growth_w) * np.log1p(np.abs(growth_w))
        X = np.column_stack([f1, f2, f3])

    return X, y_w, feature_names


def fit_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
) -> dict:
    """Fit Ridge regression with feature standardization for stability."""
    n = len(y_train)
    p = X_train.shape[1] if X_train.ndim > 1 else 1

    if n < 10 or X_train.shape[0] < 10:
        return {
            "intercept": float(np.median(y_train)) if n > 0 else 0.0,
            "coefficients": np.zeros(p),
            "means": np.zeros(p),
            "stds": np.ones(p),
            "standardized": False,
        }

    # Standardize features for proper regularization
    means = np.mean(X_train, axis=0)
    stds = np.std(X_train, axis=0)
    stds[stds < 1e-10] = 1.0

    X_std = (X_train - means) / stds

    # Add intercept column
    ones = np.ones((n, 1))
    X_aug = np.hstack([ones, X_std])

    # Ridge regression — moderate lambda for stability
    lam = 10.0
    XtX = X_aug.T @ X_aug
    reg = lam * np.eye(XtX.shape[0])
    reg[0, 0] = 0  # don't regularize intercept

    try:
        beta = np.linalg.solve(XtX + reg, X_aug.T @ y_train)
    except np.linalg.LinAlgError:
        try:
            beta, _, _, _ = np.linalg.lstsq(X_aug, y_train, rcond=None)
        except np.linalg.LinAlgError:
            return {
                "intercept": float(np.median(y_train)),
                "coefficients": np.zeros(p),
                "means": np.zeros(p),
                "stds": np.ones(p),
                "standardized": False,
            }

    return {
        "intercept": float(beta[0]),
        "coefficients": beta[1:],
        "means": means,
        "stds": stds,
        "standardized": True,
    }


def predict(model: dict, X_test: np.ndarray) -> np.ndarray:
    """Generate predictions from fitted model."""
    intercept = model["intercept"]
    coefficients = model["coefficients"]

    if len(X_test) == 0:
        return np.array([])

    if model.get("standardized", False):
        means = model["means"]
        stds = model["stds"]
        X_std = (X_test - means) / stds
        return intercept + X_std @ coefficients
    else:
        return intercept + X_test @ coefficients


def get_model_description() -> str:
    """Human-readable description of the model specification."""
    return (
        "Ridge regression (lambda=10) with simplified, robust features and standardization. "
        "For P/EPS: 3 features: (1) winsorized EPS growth% — linear growth premium on earnings, "
        "(2) positive growth indicator — discrete PE premium for growing vs declining earnings "
        "(market pays substantial premium simply for positive earnings trajectory), "
        "(3) absolute growth magnitude — captures symmetric magnitude effect where both large "
        "positive and negative growth increase valuation uncertainty. "
        "For EV/Rev: 3 features using growth, gross margin, and growth×margin interaction. "
        "For EV/GP: 3 features using growth, positive indicator, and log growth. "
        "PE observations pre-filtered to (0, 150) range. "
        "Target winsorized at 3/97 pctile for PE (tighter to handle fat tails); growth at 3/97. "
        "Higher Ridge lambda (10) for maximum temporal stability across market regimes. "
        "Fewer features reduce multicollinearity from correlated nonlinear transforms. "
        "All features have clear economic rationale for cross-sectional valuation."
    )