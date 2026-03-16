"""Experiment leaderboard — ranks experiments by composite score."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from research.experiments.registry import ExperimentRegistry

console = Console()


def show_leaderboard(
    metric_type: str = "evRev",
    limit: int = 20,
    registry: ExperimentRegistry | None = None,
) -> None:
    """Display experiment leaderboard as a rich table."""
    reg = registry or ExperimentRegistry()
    experiments = reg.get_leaderboard(metric_type, limit)

    if not experiments:
        console.print("[yellow]No improved experiments yet.[/yellow]")
        return

    table = Table(title=f"Leaderboard — {metric_type} (top {limit})")
    table.add_column("Rank", style="dim", width=4)
    table.add_column("ID", style="dim", width=24)
    table.add_column("Composite", justify="right")
    table.add_column("OOS R²", justify="right")
    table.add_column("Stability", justify="right")
    table.add_column("Adj R²", justify="right")
    table.add_column("Interp", justify="right")
    table.add_column("Features", justify="right", width=4)
    table.add_column("Description", max_width=40)

    for i, exp in enumerate(experiments):
        style = "bold green" if i == 0 else ""
        table.add_row(
            str(i + 1),
            exp.experiment_id,
            f"{exp.composite:.4f}",
            f"{exp.mean_oos_r2:.4f}",
            f"{exp.stability:.4f}",
            f"{exp.adjusted_r2:.4f}",
            f"{exp.interpretability:.2f}",
            str(exp.n_features),
            exp.model_description or "",
            style=style,
        )

    console.print(table)
    console.print(f"\nTotal experiments: {reg.count(metric_type)}")
