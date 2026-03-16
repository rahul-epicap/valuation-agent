"""Generate production-ready TypeScript from winning experiment.

Outputs code compatible with frontend/src/lib/multiFactorRegression.ts patterns.
Only works for models expressible as linear combinations (OLS/Ridge/Lasso).
"""

from __future__ import annotations

import re
from pathlib import Path

from research.experiments.registry import ExperimentRecord


def generate_production_typescript(
    experiment: ExperimentRecord,
    output_path: Path | None = None,
) -> str | None:
    """Generate production TypeScript code from a winning experiment.

    Returns None if the model is not expressible as a linear combination
    (i.e., requires non-linear computation that should stay server-side).

    Returns the generated code as a string.
    """
    code = experiment.train_py_code

    # Check if model is linear (can be expressed as coefficients)
    if not _is_linear_model(code):
        return None

    # Extract feature engineering logic
    feature_names = _extract_feature_names(code)
    model_desc = experiment.model_description

    lines = [
        "/**",
        " * Auto-generated regression model from autoresearch.",
        f" * Experiment: {experiment.experiment_id}",
        f" * Model: {model_desc}",
        f" * Composite Score: {experiment.composite:.4f}",
        f" * OOS R²: {experiment.mean_oos_r2:.4f}",
        " *",
        " * NOTE: This is a generated file. Do not edit manually.",
        " * Regenerate with: python -m research.cli codegen",
        " */",
        "",
        f"export const RESEARCH_MODEL_FEATURES = {_to_ts_array(feature_names)};",
        "",
        f"export const RESEARCH_MODEL_DESCRIPTION = '{_escape_ts(model_desc)}';",
        "",
        "/**",
        " * Apply feature transforms matching the research experiment.",
        " * This function should be integrated into the existing",
        " * multiFactorRegression.ts build pipeline.",
        " */",
        "export function buildResearchFeatures(",
        "  growthPct: number,",
        "  factorValues: Record<string, number>,",
        "): number[] {",
        "  const features: number[] = [growthPct];",
    ]

    # Add feature extraction logic based on detected transforms
    transforms = _detect_transforms(code)
    for name, transform in transforms.items():
        if name == "growth_pct":
            continue
        if transform == "squared":
            lines.append(f"  features.push(growthPct * growthPct);  // {name}")
        elif transform == "log":
            expr = "Math.log(Math.max(1 + growthPct / 100, 0.01))"
            lines.append(f"  features.push({expr});  // {name}")
        elif transform == "dummy":
            lines.append(f"  features.push(factorValues['{name}'] ?? 0);  // {name}")
        elif transform == "continuous":
            lines.append(f"  features.push(factorValues['{name}'] ?? 0);  // {name}")
        else:
            lines.append(f"  features.push(factorValues['{name}'] ?? 0);  // {name}")

    lines.extend(
        [
            "  return features;",
            "}",
            "",
        ]
    )

    result = "\n".join(lines)

    if output_path:
        output_path.write_text(result)

    return result


def _is_linear_model(code: str) -> bool:
    """Check if the model is expressible as linear coefficients."""
    # Non-linear indicators
    non_linear = [
        "RandomForest",
        "GradientBoosting",
        "XGB",
        "xgboost",
        "neural",
        "MLPRegressor",
        "KernelRidge",
        "DecisionTree",
    ]
    for indicator in non_linear:
        if indicator in code:
            return False
    return True


def _extract_feature_names(code: str) -> list[str]:
    """Extract feature names from the build_features function."""
    # Look for the feature_names list in the return
    match = re.search(r'\[(["\'].*?["\'](?:\s*,\s*["\'].*?["\'])*)\]', code)
    if match:
        names_str = match.group(1)
        return re.findall(r'["\'](\w+)["\']', names_str)
    return ["growth_pct"]


def _detect_transforms(code: str) -> dict[str, str]:
    """Detect feature transforms used in the code."""
    transforms: dict[str, str] = {}
    if "** 2" in code or "**2" in code or "np.square" in code:
        transforms["growth_pct_sq"] = "squared"
    if "np.log" in code:
        transforms["log_growth"] = "log"
    return transforms


def _to_ts_array(items: list[str]) -> str:
    """Convert Python list to TypeScript array literal."""
    inner = ", ".join(f"'{item}'" for item in items)
    return f"[{inner}]"


def _escape_ts(s: str) -> str:
    """Escape a string for TypeScript string literal."""
    return s.replace("'", "\\'").replace("\n", "\\n")
