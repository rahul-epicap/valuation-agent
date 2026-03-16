"""Tests for experiment sandbox validation."""

from __future__ import annotations

from research.experiments.sandbox import validate_train_py


class TestValidation:
    def test_valid_baseline(self):
        code = """
import numpy as np
from research.prepare import PreparedDataset, get_baseline_points

def build_features(dataset, date_idx, metric_type):
    X, y = get_baseline_points(dataset, metric_type, date_idx)
    return X.reshape(-1, 1), y, ["growth_pct"]

def fit_model(X_train, y_train):
    return {"intercept": 0.0, "coefficients": np.zeros(1)}

def predict(model, X_test):
    return model["intercept"] + X_test @ model["coefficients"]

def get_model_description():
    return "test"
"""
        errors = validate_train_py(code)
        assert errors == []

    def test_missing_function(self):
        code = """
import numpy as np
def build_features(dataset, date_idx, metric_type):
    pass
def fit_model(X, y):
    pass
def predict(model, X):
    pass
# Missing get_model_description
"""
        errors = validate_train_py(code)
        assert any("Missing required functions" in e for e in errors)

    def test_blocked_import(self):
        code = """
import os
import numpy as np
def build_features(dataset, date_idx, metric_type):
    pass
def fit_model(X, y):
    pass
def predict(model, X):
    pass
def get_model_description():
    return "test"
"""
        errors = validate_train_py(code)
        assert any("Disallowed import" in e for e in errors)

    def test_blocked_open(self):
        code = """
import numpy as np
def build_features(dataset, date_idx, metric_type):
    f = open("data.txt")
    pass
def fit_model(X, y):
    pass
def predict(model, X):
    pass
def get_model_description():
    return "test"
"""
        errors = validate_train_py(code)
        assert any("Blocked pattern" in e for e in errors)

    def test_sklearn_allowed(self):
        code = """
import numpy as np
from sklearn.linear_model import Ridge
from research.prepare import get_baseline_points

def build_features(dataset, date_idx, metric_type):
    X, y = get_baseline_points(dataset, metric_type, date_idx)
    return X.reshape(-1, 1), y, ["growth_pct"]

def fit_model(X_train, y_train):
    model = Ridge(alpha=1.0)
    model.fit(X_train, y_train)
    return model

def predict(model, X_test):
    return model.predict(X_test)

def get_model_description():
    return "Ridge regression"
"""
        errors = validate_train_py(code)
        assert errors == []

    def test_syntax_error(self):
        code = "def foo(:\n    pass"
        errors = validate_train_py(code)
        assert any("Syntax error" in e for e in errors)
