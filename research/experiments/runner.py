"""Sandboxed experiment execution with timeout and error capture."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from research.config.settings import settings


@dataclass
class RunResult:
    """Result from running an experiment."""

    success: bool
    stdout: str
    stderr: str
    elapsed_seconds: float
    return_code: int


def run_experiment(
    train_py_path: Path | None = None,
    metric_type: str = "evRev",
    max_splits: int | None = None,
    timeout: int | None = None,
) -> RunResult:
    """Run a train.py experiment in a subprocess with timeout.

    This provides isolation: if the experiment crashes, hangs, or has
    import errors, it doesn't affect the main process.
    """
    train_path = train_py_path or settings.train_py_path
    timeout_s = timeout or settings.EXPERIMENT_TIMEOUT_SECONDS

    # Build the evaluation script to run in subprocess
    script = _build_eval_script(train_path, metric_type, max_splits)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, dir=settings.CACHE_DIR
    ) as f:
        f.write(script)
        script_path = f.name

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(settings.RESEARCH_DIR.parent),
        )
        elapsed = time.time() - start
        return RunResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_seconds=elapsed,
            return_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        return RunResult(
            success=False,
            stdout="",
            stderr=f"Experiment timed out after {timeout_s}s",
            elapsed_seconds=elapsed,
            return_code=-1,
        )
    finally:
        Path(script_path).unlink(missing_ok=True)


def _build_eval_script(
    train_path: Path,
    metric_type: str,
    max_splits: int | None,
) -> str:
    """Build a Python script that evaluates train.py and prints results as JSON."""
    max_splits_arg = f", max_splits={max_splits}" if max_splits else ""
    return f"""\
import json
import sys
sys.path.insert(0, ".")

from research.evaluation.harness import evaluate_experiment
from research.prepare import build_dataset
from pathlib import Path

dataset = build_dataset()
result = evaluate_experiment(
    dataset,
    metric_type="{metric_type}",
    train_py_path=Path("{train_path}"){max_splits_arg},
)

output = {{
    "metric_type": result.metric_type,
    "model_description": result.model_description,
    "n_features": result.n_features,
    "mean_oos_r2": result.mean_oos_r2,
    "mean_adj_r2": result.mean_adj_r2,
    "stability": result.stability,
    "interpretability": result.interpretability,
    "composite": result.composite,
    "elapsed_seconds": result.elapsed_seconds,
    "error": result.error,
    "n_splits": len(result.split_results),
}}
print(json.dumps(output))
"""
