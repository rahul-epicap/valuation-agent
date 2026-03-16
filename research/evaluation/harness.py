"""Core evaluation harness for regression experiments.

Runs a train.py experiment across all temporal splits and computes
composite evaluation metrics.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import numpy as np

from research.config.settings import settings
from research.evaluation.metrics import adjusted_r2, composite_score, oos_r2, stability_score
from research.prepare import PreparedDataset


@dataclass
class SplitResult:
    """Result from a single temporal split evaluation."""

    split_idx: int
    train_date_indices: list[int]
    test_date_idx: int
    train_r2: float
    test_r2: float  # OOS R²
    n_train: int
    n_test: int
    n_features: int
    train_adj_r2: float


@dataclass
class ExperimentResult:
    """Aggregated result from evaluating an experiment across all splits."""

    metric_type: str
    model_description: str
    n_features: int

    # Aggregated metrics
    mean_oos_r2: float
    mean_adj_r2: float
    stability: float
    interpretability: float
    composite: float

    # Per-split detail
    split_results: list[SplitResult] = field(default_factory=list)

    # Timing
    elapsed_seconds: float = 0.0

    # Error info (if experiment failed)
    error: str | None = None


def _load_train_module(train_py_path: Path) -> ModuleType:
    """Dynamically load train.py as a module."""
    spec = importlib.util.spec_from_file_location("train_experiment", str(train_py_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {train_py_path}")
    module = importlib.util.module_from_spec(spec)
    # Don't pollute sys.modules permanently
    old = sys.modules.get("train_experiment")
    try:
        sys.modules["train_experiment"] = module
        spec.loader.exec_module(module)
    finally:
        if old is not None:
            sys.modules["train_experiment"] = old
        else:
            sys.modules.pop("train_experiment", None)
    return module


def evaluate_experiment(
    dataset: PreparedDataset,
    metric_type: str,
    train_py_path: Path | None = None,
    interpretability_score: float = 0.5,
    max_splits: int | None = None,
) -> ExperimentResult:
    """Evaluate a train.py experiment across temporal splits.

    The train.py module must export:
        - build_features(dataset, date_idx, metric_type) -> (X, y, feature_names)
        - fit_model(X_train, y_train) -> model
        - predict(model, X_test) -> y_pred
        - get_model_description() -> str

    Args:
        dataset: PreparedDataset to evaluate on.
        metric_type: One of 'evRev', 'evGP', 'pEPS'.
        train_py_path: Path to train.py. Defaults to settings.train_py_path.
        interpretability_score: Pre-computed interpretability score (0-1).
        max_splits: Limit number of splits to evaluate (for debugging).

    Returns:
        ExperimentResult with all metrics computed.
    """
    train_py_path = train_py_path or settings.train_py_path
    start_time = time.time()

    try:
        module = _load_train_module(train_py_path)
    except Exception as e:
        return ExperimentResult(
            metric_type=metric_type,
            model_description="LOAD_ERROR",
            n_features=0,
            mean_oos_r2=0.0,
            mean_adj_r2=0.0,
            stability=0.0,
            interpretability=0.0,
            composite=0.0,
            error=f"Failed to load train.py: {e}",
            elapsed_seconds=time.time() - start_time,
        )

    # Validate required functions
    for fn_name in ["build_features", "fit_model", "predict", "get_model_description"]:
        if not hasattr(module, fn_name):
            return ExperimentResult(
                metric_type=metric_type,
                model_description="MISSING_FUNCTION",
                n_features=0,
                mean_oos_r2=0.0,
                mean_adj_r2=0.0,
                stability=0.0,
                interpretability=0.0,
                composite=0.0,
                error=f"train.py missing required function: {fn_name}",
                elapsed_seconds=time.time() - start_time,
            )

    model_desc = module.get_model_description()
    splits = dataset.splits
    if max_splits is not None:
        splits = splits[:max_splits]

    split_results: list[SplitResult] = []
    oos_r2_values: list[float] = []

    for i, split in enumerate(splits):
        try:
            result = _evaluate_single_split(module, dataset, metric_type, split, i)
            split_results.append(result)
            oos_r2_values.append(result.test_r2)
        except Exception:
            # Log but continue — partial results are still useful
            split_results.append(
                SplitResult(
                    split_idx=i,
                    train_date_indices=split.train_date_indices.tolist(),
                    test_date_idx=split.test_date_idx,
                    train_r2=0.0,
                    test_r2=0.0,
                    n_train=0,
                    n_test=0,
                    n_features=0,
                    train_adj_r2=0.0,
                )
            )
            oos_r2_values.append(0.0)

    elapsed = time.time() - start_time

    if not oos_r2_values:
        return ExperimentResult(
            metric_type=metric_type,
            model_description=model_desc,
            n_features=0,
            mean_oos_r2=0.0,
            mean_adj_r2=0.0,
            stability=0.0,
            interpretability=0.0,
            composite=0.0,
            error="No valid splits",
            elapsed_seconds=elapsed,
        )

    mean_oos = float(np.mean(oos_r2_values))
    stab = stability_score(oos_r2_values)

    adj_r2_values = [sr.train_adj_r2 for sr in split_results if sr.n_train > 0]
    mean_adj = float(np.mean(adj_r2_values)) if adj_r2_values else 0.0

    n_features = max((sr.n_features for sr in split_results if sr.n_features > 0), default=0)

    comp = composite_score(
        oos_r2_val=mean_oos,
        stability_val=stab,
        adj_r2_val=mean_adj,
        interpretability_val=interpretability_score,
        weights={
            "oos_r2": settings.WEIGHT_OOS_R2,
            "stability": settings.WEIGHT_STABILITY,
            "adjusted_r2": settings.WEIGHT_ADJUSTED_R2,
            "interpretability": settings.WEIGHT_INTERPRETABILITY,
        },
    )

    return ExperimentResult(
        metric_type=metric_type,
        model_description=model_desc,
        n_features=n_features,
        mean_oos_r2=mean_oos,
        mean_adj_r2=mean_adj,
        stability=stab,
        interpretability=interpretability_score,
        composite=comp,
        split_results=split_results,
        elapsed_seconds=elapsed,
    )


def _evaluate_single_split(
    module: ModuleType,
    dataset: PreparedDataset,
    metric_type: str,
    split: object,
    split_idx: int,
) -> SplitResult:
    """Evaluate experiment on a single temporal split."""
    # Build training data: aggregate across all training dates
    X_train_parts = []
    y_train_parts = []
    feature_names = None

    for di in split.train_date_indices:
        X, y, fnames = module.build_features(dataset, int(di), metric_type)
        if len(X) > 0:
            X_train_parts.append(X)
            y_train_parts.append(y)
            if feature_names is None:
                feature_names = fnames

    if not X_train_parts:
        return SplitResult(
            split_idx=split_idx,
            train_date_indices=split.train_date_indices.tolist(),
            test_date_idx=split.test_date_idx,
            train_r2=0.0,
            test_r2=0.0,
            n_train=0,
            n_test=0,
            n_features=0,
            train_adj_r2=0.0,
        )

    X_train = np.vstack(X_train_parts)
    y_train = np.concatenate(y_train_parts)
    n_features = X_train.shape[1] if X_train.ndim == 2 else 1

    # Fit model
    model = module.fit_model(X_train, y_train)

    # Training R²
    y_train_pred = module.predict(model, X_train)
    train_r2_val = oos_r2(y_train, y_train_pred)
    train_adj = adjusted_r2(train_r2_val, len(y_train), n_features)

    # Test data
    X_test, y_test, _ = module.build_features(dataset, split.test_date_idx, metric_type)
    if len(X_test) == 0:
        return SplitResult(
            split_idx=split_idx,
            train_date_indices=split.train_date_indices.tolist(),
            test_date_idx=split.test_date_idx,
            train_r2=train_r2_val,
            test_r2=0.0,
            n_train=len(y_train),
            n_test=0,
            n_features=n_features,
            train_adj_r2=train_adj,
        )

    # OOS prediction
    y_test_pred = module.predict(model, X_test)
    test_r2_val = oos_r2(y_test, y_test_pred)

    return SplitResult(
        split_idx=split_idx,
        train_date_indices=split.train_date_indices.tolist(),
        test_date_idx=split.test_date_idx,
        train_r2=train_r2_val,
        test_r2=test_r2_val,
        n_train=len(y_train),
        n_test=len(y_test),
        n_features=n_features,
        train_adj_r2=train_adj,
    )
