"""CLI for the autoresearch system.

Usage:
    python -m research.cli fetch          # Pull snapshot from Railway → local cache
    python -m research.cli enrich         # Fetch FMP factor data for all tickers
    python -m research.cli prepare        # Build PreparedDataset from cache
    python -m research.cli baseline       # Run baseline OLS and show R² per metric
    python -m research.cli evaluate       # Evaluate current train.py
    python -m research.cli run            # Run autoresearch experiment loop
    python -m research.cli leaderboard    # Show experiment leaderboard
    python -m research.cli upload --experiment-id <id>  # Upload to production
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """Autoresearch for valuation R² optimization."""
    pass


@cli.command()
def fetch():
    """Pull latest snapshot from Railway production DB → local cache."""
    from research.data.snapshot_loader import fetch_latest_snapshot

    try:
        fetch_latest_snapshot()
        console.print("[green]Snapshot fetched successfully.[/green]")
    except Exception as e:
        console.print(f"[red]Error fetching snapshot: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--limit", default=None, type=int, help="Limit to N tickers (dry run)")
@click.option("--force", is_flag=True, help="Re-fetch even if cache is fresh")
def enrich(limit: int | None, force: bool):
    """Fetch FMP factor data for all tickers in cached snapshot."""
    import asyncio

    from research.data.factor_store import FactorStore
    from research.data.fmp_client import FMPClient
    from research.data.fmp_factors import extract_all_factors
    from research.data.snapshot_loader import load_cached_snapshot

    try:
        data = load_cached_snapshot()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    tickers = data["tickers"]
    isin_map = data.get("isin_map", {})
    console.print(f"  {len(tickers)} tickers, {len(isin_map)} with ISIN mappings")
    store = FactorStore()

    if force:
        to_fetch = tickers
    else:
        to_fetch = store.get_stale_tickers(tickers)

    if limit:
        to_fetch = to_fetch[:limit]

    if not to_fetch:
        console.print("[green]All tickers have fresh factor data.[/green]")
        return

    console.print(f"Fetching FMP factors for {len(to_fetch)} tickers...")
    console.print("  Endpoints: profile, key-metrics, ratios, financial-growth,")
    console.print("             analyst-estimates, rating, earnings-surprises, prices")
    console.print("  ISIN → FMP ticker resolution via /api/v4/search/isin")

    async def _process_ticker(sem, client, ticker, isin_map, counters):
        """Process a single ticker with concurrency control."""
        async with sem:
            fmp_symbol = ticker
            isin = isin_map.get(ticker)
            if isin:
                resolved = await client.search_by_isin(isin)
                if resolved:
                    fmp_symbol = resolved
                    counters["isin_resolved"] += 1

            try:
                factors = await extract_all_factors(client, fmp_symbol)
                factors["ticker"] = ticker
                factors["fmp_symbol"] = fmp_symbol
                counters["ok"] += 1
                return factors
            except Exception as e:
                counters["errors"] += 1
                if counters["errors"] <= 10:
                    console.print(f"  [yellow]{ticker} → {fmp_symbol}: {e}[/yellow]")
                return None

    async def _run():
        client = FMPClient()
        concurrency = 20
        sem = asyncio.Semaphore(concurrency)
        counters = {"ok": 0, "errors": 0, "isin_resolved": 0}

        try:
            # Process in batches for progress reporting
            batch_size = 200
            all_results = []
            for batch_start in range(0, len(to_fetch), batch_size):
                batch = to_fetch[batch_start : batch_start + batch_size]
                tasks = [_process_ticker(sem, client, t, isin_map, counters) for t in batch]
                batch_results = await asyncio.gather(*tasks)
                all_results.extend([r for r in batch_results if r is not None])

                done = batch_start + len(batch)
                pct = done / len(to_fetch) * 100
                console.print(
                    f"  Progress: {done}/{len(to_fetch)} ({pct:.0f}%)"
                    f" — {counters['ok']} ok, {counters['errors']} err"
                    f", {counters['isin_resolved']} ISIN-resolved"
                )

                # Save incrementally every batch
                if all_results:
                    store.upsert_factors(all_results)
                    store.save_metadata([r["ticker"] for r in all_results])
        finally:
            await client.close()

        return all_results

    results = asyncio.run(_run())

    if results:
        store.upsert_factors(results)
        store.save_metadata([r["ticker"] for r in results])
        console.print(f"[green]Cached {len(results)} ticker factors.[/green]")
    else:
        console.print("[yellow]No factor data fetched.[/yellow]")


@cli.command()
def prepare():
    """Build PreparedDataset from cached snapshot."""
    from research.prepare import build_and_cache_dataset

    try:
        dataset = build_and_cache_dataset()
        console.print(
            f"[green]Dataset prepared: {dataset.n_dates} dates, "
            f"{dataset.n_tickers} tickers, {dataset.n_splits} splits[/green]"
        )
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        console.print("Run 'python -m research.cli fetch' first.")
        sys.exit(1)


@cli.command()
@click.option("--metric", default="evRev", type=click.Choice(["evRev", "evGP", "pEPS"]))
@click.option("--date-idx", default=None, type=int, help="Specific date index (default: latest)")
def baseline(metric: str, date_idx: int | None):
    """Run baseline OLS and show R² for each date."""
    from research.prepare import build_dataset, get_baseline_r2

    try:
        dataset = build_dataset()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    if date_idx is not None:
        result = get_baseline_r2(dataset, metric, date_idx)
        if result:
            console.print(f"Date: {dataset.dates[date_idx]}")
            console.print(
                f"  R²={result['r2']:.4f}  slope={result['slope']:.4f}  "
                f"intercept={result['intercept']:.2f}  n={result['n']}"
            )
        else:
            console.print("[yellow]Not enough valid points for regression.[/yellow]")
        return

    # Show summary across all dates
    table = Table(title=f"Baseline OLS R² — {metric}")
    table.add_column("Date", style="dim")
    table.add_column("R²", justify="right")
    table.add_column("Slope", justify="right")
    table.add_column("Intercept", justify="right")
    table.add_column("N", justify="right")

    r2_values = []
    for di in range(dataset.n_dates):
        result = get_baseline_r2(dataset, metric, di)
        if result:
            r2_values.append(result["r2"])
            # Show every 12th date (monthly → annual) to keep output manageable
            if di % 12 == 0 or di == dataset.n_dates - 1:
                table.add_row(
                    dataset.dates[di],
                    f"{result['r2']:.4f}",
                    f"{result['slope']:.4f}",
                    f"{result['intercept']:.2f}",
                    str(result["n"]),
                )

    console.print(table)

    if r2_values:
        import numpy as np

        arr = np.array(r2_values)
        console.print(f"\n[bold]Summary ({len(r2_values)} dates with valid regressions):[/bold]")
        console.print(f"  Mean R²:   {arr.mean():.4f}")
        console.print(f"  Median R²: {np.median(arr):.4f}")
        console.print(f"  Min R²:    {arr.min():.4f}")
        console.print(f"  Max R²:    {arr.max():.4f}")
        console.print(f"  Std R²:    {arr.std():.4f}")


@cli.command()
@click.option("--metric", default="evRev", type=click.Choice(["evRev", "evGP", "pEPS"]))
@click.option("--max-splits", default=None, type=int, help="Limit splits for quick test")
@click.option("--train-py", default=None, type=str, help="Path to train.py")
def evaluate(metric: str, max_splits: int | None, train_py: str | None):
    """Evaluate current train.py across temporal splits."""
    from research.evaluation.harness import evaluate_experiment
    from research.prepare import build_dataset

    try:
        dataset = build_dataset()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    train_path = Path(train_py) if train_py else None

    console.print(f"Evaluating train.py for metric={metric}...")
    start = time.time()
    result = evaluate_experiment(dataset, metric, train_path, max_splits=max_splits)
    elapsed = time.time() - start

    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Results — {result.model_description}[/bold]")
    console.print(f"  Metric:           {result.metric_type}")
    console.print(f"  Features:         {result.n_features}")
    console.print(f"  Mean OOS R²:      {result.mean_oos_r2:.4f}")
    console.print(f"  Stability:        {result.stability:.4f}")
    console.print(f"  Mean Adj R²:      {result.mean_adj_r2:.4f}")
    console.print(f"  Interpretability: {result.interpretability:.4f}")
    console.print(f"  [bold green]Composite Score:  {result.composite:.4f}[/bold green]")
    console.print(f"  Elapsed:          {elapsed:.1f}s")
    console.print(f"  Splits evaluated: {len(result.split_results)}")


@cli.command(name="run")
@click.option("--metric", default="evRev", type=click.Choice(["evRev", "evGP", "pEPS"]))
@click.option("--iterations", default=10, type=int, help="Number of iterations")
@click.option("--max-splits", default=None, type=int, help="Limit splits (faster)")
def run_research(metric: str, iterations: int, max_splits: int | None):
    """Run the autoresearch experiment loop."""
    from research.agent.orchestrator import Orchestrator

    try:
        orchestrator = Orchestrator(
            metric_type=metric,
            max_splits=max_splits,
        )
        orchestrator.run(iterations=iterations)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        console.print("Run 'python -m research.cli fetch' first.")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Research error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--metric", default="evRev", type=click.Choice(["evRev", "evGP", "pEPS"]))
@click.option("--limit", default=20, type=int, help="Number of entries to show")
def leaderboard(metric: str, limit: int):
    """Show experiment leaderboard."""
    from research.evaluation.leaderboard import show_leaderboard

    show_leaderboard(metric_type=metric, limit=limit)


@cli.command()
@click.option("--metric", default="evRev", type=click.Choice(["evRev", "evGP", "pEPS"]))
@click.option("--experiment-id", default=None, help="Experiment ID (default: best)")
@click.option("--output-dir", default=None, type=str, help="Output directory")
def codegen(metric: str, experiment_id: str | None, output_dir: str | None):
    """Generate production code from a winning experiment."""
    from research.codegen.pr_formatter import format_pr_description
    from research.codegen.python_generator import generate_production_python
    from research.codegen.typescript_generator import generate_production_typescript
    from research.experiments.registry import ExperimentRegistry

    registry = ExperimentRegistry()

    if experiment_id:
        exp = registry.get_by_id(experiment_id)
        if not exp:
            console.print(f"[red]Experiment {experiment_id} not found.[/red]")
            sys.exit(1)
    else:
        exp = registry.get_best(metric)
        if not exp:
            console.print("[red]No improved experiments found.[/red]")
            sys.exit(1)

    console.print(f"[bold]Generating code from: {exp.experiment_id}[/bold]")
    console.print(f"  Model: {exp.model_description}")
    console.print(f"  Composite: {exp.composite:.4f}")

    out = Path(output_dir) if output_dir else Path(".")
    out.mkdir(parents=True, exist_ok=True)

    # Python
    generate_production_python(exp, out / "valuation_model.py")
    console.print(f"  [green]Python: {out / 'valuation_model.py'}[/green]")

    # TypeScript
    ts_code = generate_production_typescript(exp, out / "researchModel.ts")
    if ts_code:
        console.print(f"  [green]TypeScript: {out / 'researchModel.ts'}[/green]")
    else:
        console.print("  [yellow]TypeScript: skipped (non-linear model)[/yellow]")

    # PR description
    pr_desc = format_pr_description(exp)
    pr_path = out / "PR_DESCRIPTION.md"
    pr_path.write_text(pr_desc)
    console.print(f"  [green]PR description: {pr_path}[/green]")


@cli.command()
@click.argument("experiment_id")
@click.option("--name", default=None, help="Snapshot name")
def upload(experiment_id: str, name: str | None):
    """Upload winning experiment results back to production."""
    from research.experiments.registry import ExperimentRegistry

    registry = ExperimentRegistry()
    exp = registry.get_by_id(experiment_id)
    if not exp:
        console.print(f"[red]Experiment {experiment_id} not found.[/red]")
        sys.exit(1)

    console.print(f"[bold]Uploading: {exp.experiment_id}[/bold]")
    console.print(f"  Model: {exp.model_description}")
    console.print(f"  Composite: {exp.composite:.4f}")
    msg = "Upload to production not yet implemented."
    console.print(f"[yellow]{msg}[/yellow]")


@cli.command()
def status():
    """Show current research status."""
    from research.config.settings import settings

    console.print("[bold]Research Status[/bold]")
    console.print(f"  Cache dir:    {settings.CACHE_DIR}")
    console.print(f"  Snapshot:     {'exists' if settings.snapshot_path.exists() else 'missing'}")
    ds_status = "exists" if settings.prepared_dataset_path.exists() else "missing"
    tsv_status = "exists" if settings.results_tsv_path.exists() else "missing"
    console.print(f"  Dataset:      {ds_status}")
    console.print(f"  Results TSV:  {tsv_status}")
    console.print(f"  LLM provider: {settings.LLM_PROVIDER}")
    console.print(f"  LLM model:    {settings.LLM_MODEL}")

    # Show registry info
    try:
        from research.experiments.registry import ExperimentRegistry

        reg = ExperimentRegistry()
        total = reg.count()
        console.print(f"  Experiments:  {total}")

        for mt in ["evRev", "evGP", "pEPS"]:
            best = reg.get_best(mt)
            if best:
                console.print(f"  Best {mt}: {best.composite:.4f} (R²={best.mean_oos_r2:.4f})")
    except Exception:
        pass

    # Show FMP factor cache status
    fmp_dir = settings.fmp_cache_dir
    if fmp_dir.exists():
        factor_file = fmp_dir / "factors.parquet"
        if factor_file.exists():
            import pandas as pd

            df = pd.read_parquet(factor_file)
            console.print(f"  FMP factors:  {len(df)} tickers cached")


def main():
    cli()


if __name__ == "__main__":
    main()
