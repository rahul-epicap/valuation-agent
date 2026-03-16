"""Format PR-ready output from a winning experiment."""

from __future__ import annotations

from research.codegen.typescript_generator import generate_production_typescript
from research.experiments.registry import ExperimentRecord


def format_pr_description(
    experiment: ExperimentRecord,
    baseline_r2: float = 0.0,
) -> str:
    """Generate a PR description for the winning experiment."""
    ts_possible = generate_production_typescript(experiment) is not None

    lines = [
        "## Summary",
        "",
        f"Autoresearch found an improved regression model for `{experiment.metric_type}`.",
        "",
        f"- **Model**: {experiment.model_description}",
        f"- **Composite Score**: {experiment.composite:.4f}",
        f"- **OOS R²**: {experiment.mean_oos_r2:.4f} (baseline: {baseline_r2:.4f})",
        f"- **Stability**: {experiment.stability:.4f}",
        f"- **Adjusted R²**: {experiment.adjusted_r2:.4f}",
        f"- **Features**: {experiment.n_features}",
        "",
        "### Hypothesis",
        experiment.hypothesis,
        "",
        "## AI Contribution",
        "",
        "- Regression specification discovered by LLM-driven autoresearch",
        "- Production code auto-generated from winning experiment",
        f"- Experiment ID: `{experiment.experiment_id}`",
        "",
        "## Changes",
        "",
        "- Updated `backend/app/services/valuation_service.py` with new regression logic",
    ]

    if ts_possible:
        lines.append("- Updated `frontend/src/lib/` with TypeScript equivalent")
    else:
        lines.extend(
            [
                "- **Note**: Model requires server-side computation (non-linear)",
                "- Frontend falls back to API call for regression results",
            ]
        )

    lines.extend(
        [
            "",
            "## Test Plan",
            "",
            "- [ ] Verify baseline R² matches production for same date/metric",
            "- [ ] Verify new model R² improvement on production data",
            "- [ ] Frontend renders regression chart correctly",
            "- [ ] No regression in other metric types",
            "",
            "---",
            "Generated with autoresearch",
        ]
    )

    return "\n".join(lines)
