"""Tests for code generation from experiments."""

from __future__ import annotations

from research.codegen.pr_formatter import format_pr_description
from research.codegen.python_generator import generate_production_python
from research.codegen.typescript_generator import generate_production_typescript
from research.experiments.registry import ExperimentRecord


def _make_experiment(
    code: str = "",
    model_desc: str = "OLS baseline",
) -> ExperimentRecord:
    if not code:
        code = """
import numpy as np
from research.prepare import get_baseline_points

def build_features(dataset, date_idx, metric_type):
    X, y = get_baseline_points(dataset, metric_type, date_idx)
    return X.reshape(-1, 1), y, ["growth_pct"]

def fit_model(X_train, y_train):
    beta, _, _, _ = np.linalg.lstsq(
        np.column_stack([np.ones(len(y_train)), X_train]), y_train, rcond=None
    )
    return {"intercept": beta[0], "coefficients": beta[1:]}

def predict(model, X_test):
    return model["intercept"] + X_test @ model["coefficients"]

def get_model_description():
    return "OLS baseline"
"""
    return ExperimentRecord(
        experiment_id="test_exp",
        timestamp="2026-03-16T00:00:00Z",
        metric_type="evRev",
        model_description=model_desc,
        hypothesis="Test hypothesis",
        train_py_code=code,
        n_features=1,
        mean_oos_r2=0.45,
        stability=0.8,
        adjusted_r2=0.43,
        interpretability=0.7,
        composite=0.55,
        elapsed_seconds=2.0,
        status="improved",
    )


class TestPythonGenerator:
    def test_generates_valid_python(self):
        exp = _make_experiment()
        result = generate_production_python(exp)
        assert "Auto-generated regression model" in result
        assert "import numpy" in result
        # Should not contain research.prepare imports
        assert "from research.prepare" not in result

    def test_includes_metadata(self):
        exp = _make_experiment()
        result = generate_production_python(exp)
        assert "test_exp" in result
        assert "0.55" in result  # composite


class TestTypescriptGenerator:
    def test_linear_model_generates_ts(self):
        exp = _make_experiment()
        result = generate_production_typescript(exp)
        assert result is not None
        assert "RESEARCH_MODEL_FEATURES" in result
        assert "buildResearchFeatures" in result

    def test_nonlinear_model_returns_none(self):
        code = """
from sklearn.ensemble import RandomForestRegressor
import numpy as np

def build_features(dataset, date_idx, metric_type):
    return np.array([]), np.array([]), ["growth_pct"]

def fit_model(X_train, y_train):
    return RandomForestRegressor().fit(X_train, y_train)

def predict(model, X_test):
    return model.predict(X_test)

def get_model_description():
    return "Random Forest"
"""
        exp = _make_experiment(code=code, model_desc="Random Forest")
        result = generate_production_typescript(exp)
        assert result is None


class TestPRFormatter:
    def test_format_pr(self):
        exp = _make_experiment()
        pr = format_pr_description(exp, baseline_r2=0.30)
        assert "## Summary" in pr
        assert "Autoresearch" in pr
        assert "0.45" in pr  # OOS R²
        assert "0.30" in pr  # baseline
        assert "## Test Plan" in pr
