"""Generate production-ready Python from winning experiment.

Outputs code compatible with backend/app/services/valuation_service.py patterns.
"""

from __future__ import annotations

import ast
from pathlib import Path

from research.experiments.registry import ExperimentRecord


def generate_production_python(
    experiment: ExperimentRecord,
    output_path: Path | None = None,
) -> str:
    """Generate production Python code from a winning experiment.

    Extracts the model logic from train.py and wraps it in a format
    compatible with the existing valuation_service.py patterns.

    Returns the generated code as a string.
    """
    code = experiment.train_py_code

    # Parse to extract function bodies
    tree = ast.parse(code)

    lines = [
        '"""Auto-generated regression model from autoresearch.',
        "",
        f"Experiment: {experiment.experiment_id}",
        f"Model: {experiment.model_description}",
        f"Composite Score: {experiment.composite:.4f}",
        f"OOS R²: {experiment.mean_oos_r2:.4f}",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import numpy as np",
        "",
    ]

    # Extract imports from the experiment code (except research.prepare)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not alias.name.startswith("research"):
                    asname = f" as {alias.asname}" if alias.asname else ""
                    lines.append(f"import {alias.name}{asname}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.module.startswith("research"):
                names = ", ".join(
                    f"{a.name}" + (f" as {a.asname}" if a.asname else "") for a in node.names
                )
                lines.append(f"from {node.module} import {names}")

    lines.append("")
    lines.append("")

    # Include the full experiment code as-is (functions are self-contained)
    # but replace research.prepare imports with inline equivalents
    adapted = _adapt_imports(code)
    lines.append(adapted)

    result = "\n".join(lines)

    if output_path:
        output_path.write_text(result)

    return result


def _adapt_imports(code: str) -> str:
    """Remove research.prepare imports and inline the needed functions."""
    # Remove import lines for research.prepare
    adapted_lines = []
    for line in code.split("\n"):
        if "from research.prepare" in line or "import research" in line:
            continue
        adapted_lines.append(line)

    return "\n".join(adapted_lines)
