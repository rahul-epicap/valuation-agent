"""Main autoresearch loop: propose → run → evaluate → keep/discard.

Follows the autoresearch-mlx pattern adapted for valuation regression.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from rich.console import Console

from research.agent.context_builder import build_dataset_stats, build_results_summary
from research.agent.llm_client import LLMClient
from research.agent.prompts import (
    INTERPRETABILITY_PROMPT,
    PIVOT_PROMPT,
    PROPOSAL_TEMPLATE,
    SYSTEM_PROMPT,
)
from research.config.settings import settings
from research.evaluation.harness import ExperimentResult, evaluate_experiment
from research.experiments.registry import ExperimentRecord, ExperimentRegistry
from research.experiments.sandbox import validate_train_py
from research.prepare import PreparedDataset, build_dataset

console = Console()


class Orchestrator:
    """Main autoresearch orchestrator."""

    def __init__(
        self,
        metric_type: str = "evRev",
        max_splits: int | None = None,
        llm_client: LLMClient | None = None,
    ):
        self.metric_type = metric_type
        self.max_splits = max_splits
        self.llm = llm_client or LLMClient()
        self.registry = ExperimentRegistry()
        self.dataset: PreparedDataset | None = None
        self.best_composite: float = 0.0

    def run(self, iterations: int = 10) -> None:
        """Run the autoresearch loop for N iterations."""
        console.print(f"\n[bold]Starting autoresearch: {iterations} iterations[/bold]")
        console.print(f"  Metric: {self.metric_type}")
        console.print(f"  Max splits: {self.max_splits or 'all'}\n")

        # Load dataset
        self.dataset = build_dataset()

        # Get current best
        best = self.registry.get_best(self.metric_type)
        if best:
            self.best_composite = best.composite
            console.print(
                f"[dim]Current best: {best.composite:.4f} (OOS R²={best.mean_oos_r2:.4f})[/dim]\n"
            )
        else:
            # Evaluate baseline first
            console.print("[dim]Evaluating baseline...[/dim]")
            baseline_result = evaluate_experiment(
                self.dataset,
                self.metric_type,
                settings.train_py_path,
                max_splits=self.max_splits,
            )
            self.best_composite = baseline_result.composite
            self._record_experiment(
                experiment_id="baseline",
                hypothesis="Baseline OLS: growth_pct -> multiple",
                code=settings.train_py_path.read_text(),
                result=baseline_result,
                status="improved",
            )
            console.print(
                f"[dim]Baseline: composite={baseline_result.composite:.4f} "
                f"OOS R²={baseline_result.mean_oos_r2:.4f}[/dim]\n"
            )

        for i in range(iterations):
            console.print(f"[bold]--- Iteration {i + 1}/{iterations} ---[/bold]")
            self._run_iteration(i)

        # Summary
        final_best = self.registry.get_best(self.metric_type)
        if final_best:
            console.print("\n[bold green]Best result:[/bold green]")
            console.print(f"  {final_best.model_description}")
            console.print(f"  Composite: {final_best.composite:.4f}")
            console.print(f"  OOS R²: {final_best.mean_oos_r2:.4f}")
            console.print(f"  Experiment: {final_best.experiment_id}")

    def _run_iteration(self, iteration: int) -> None:
        """Run a single propose → evaluate → keep/discard cycle."""
        # 1. Build context for LLM
        program_md = settings.program_md_path.read_text()
        current_train = settings.train_py_path.read_text()
        results_summary = build_results_summary(str(settings.results_tsv_path), max_detailed=8)
        dataset_stats = build_dataset_stats(self.dataset, self.metric_type)

        # Check for pivot
        n_failures = self.registry.consecutive_failures(self.metric_type)
        pivot_text = ""
        if n_failures >= 3:
            best = self.registry.get_best(self.metric_type)
            pivot_text = "\n\n" + PIVOT_PROMPT.format(
                n_failures=n_failures,
                best_score=best.composite if best else 0.0,
                best_r2=best.mean_oos_r2 if best else 0.0,
            )

        # 2. Get LLM proposal
        user_prompt = (
            PROPOSAL_TEMPLATE.format(
                program_md=program_md,
                n_results=8,
                results_summary=results_summary,
                current_train_py=current_train,
                dataset_stats=dataset_stats,
            )
            + pivot_text
        )

        console.print("[dim]Requesting LLM proposal...[/dim]")
        try:
            response = self.llm.complete(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=8192,
                temperature=0.7,
            )
        except Exception as e:
            console.print(f"[red]LLM error: {e}[/red]")
            return

        # 3. Parse proposal
        code = self._extract_code(response.content)
        hypothesis = self._extract_hypothesis(response.content)

        if not code:
            console.print("[yellow]No valid code block in LLM response.[/yellow]")
            return

        console.print(f"[dim]Hypothesis: {hypothesis}[/dim]")

        # 4. Validate code
        errors = validate_train_py(code)
        if errors:
            console.print(f"[red]Validation errors: {errors}[/red]")
            exp_id = ExperimentRegistry.generate_id()
            self._record_experiment(
                experiment_id=exp_id,
                hypothesis=hypothesis,
                code=code,
                result=None,
                status="error",
                error=f"Validation: {errors}",
            )
            return

        # 5. Write modified train.py and evaluate
        backup = current_train
        settings.train_py_path.write_text(code)

        try:
            console.print("[dim]Evaluating...[/dim]")
            result = evaluate_experiment(
                self.dataset,
                self.metric_type,
                settings.train_py_path,
                interpretability_score=self._score_interpretability(code, result=None),
                max_splits=self.max_splits,
            )
        except Exception as e:
            console.print(f"[red]Evaluation error: {e}[/red]")
            settings.train_py_path.write_text(backup)
            return

        exp_id = ExperimentRegistry.generate_id()

        if result.error:
            console.print(f"[red]Experiment error: {result.error}[/red]")
            settings.train_py_path.write_text(backup)
            self._record_experiment(
                experiment_id=exp_id,
                hypothesis=hypothesis,
                code=code,
                result=result,
                status="error",
                error=result.error,
            )
            return

        # 6. Keep or discard
        if result.composite > self.best_composite:
            self.best_composite = result.composite
            console.print(
                f"[bold green]IMPROVED: {result.composite:.4f} "
                f"(OOS R²={result.mean_oos_r2:.4f}, "
                f"stability={result.stability:.4f})[/bold green]"
            )
            self._record_experiment(
                experiment_id=exp_id,
                hypothesis=hypothesis,
                code=code,
                result=result,
                status="improved",
            )
        else:
            console.print(
                f"[yellow]No improvement: {result.composite:.4f} "
                f"vs best {self.best_composite:.4f}[/yellow]"
            )
            # Revert train.py
            settings.train_py_path.write_text(backup)
            self._record_experiment(
                experiment_id=exp_id,
                hypothesis=hypothesis,
                code=code,
                result=result,
                status="worse",
            )

    def _score_interpretability(self, code: str, result: ExperimentResult | None) -> float:
        """Use LLM to score model interpretability. Falls back to 0.5."""
        try:
            # Extract feature names and description from code
            import ast

            tree = ast.parse(code)
            desc = "Unknown model"
            features = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.name == "get_model_description":
                        # Try to extract the return string
                        for child in ast.walk(node):
                            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                                desc = child.value
                                break

            prompt = INTERPRETABILITY_PROMPT.format(
                model_description=desc,
                feature_names=", ".join(features) if features else "unknown",
                metric_type=self.metric_type,
            )

            response = self.llm.complete(
                system="You are a quantitative finance expert.",
                user=prompt,
                max_tokens=50,
                temperature=0.0,
            )

            # Parse the score
            text = response.content.strip()
            score = float(re.search(r"[\d.]+", text).group())
            return max(0.0, min(1.0, score))
        except Exception:
            return 0.5

    def _extract_code(self, response: str) -> str | None:
        """Extract Python code block from LLM response."""
        pattern = r"```python\s*\n(.*?)```"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _extract_hypothesis(self, response: str) -> str:
        """Extract hypothesis from LLM response."""
        pattern = r"###\s*Hypothesis\s*\n(.*?)(?=\n###|\Z)"
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "No hypothesis provided"

    def _record_experiment(
        self,
        experiment_id: str,
        hypothesis: str,
        code: str,
        result: ExperimentResult | None,
        status: str,
        error: str | None = None,
    ) -> None:
        """Record an experiment to the registry."""
        record = ExperimentRecord(
            experiment_id=experiment_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metric_type=self.metric_type,
            model_description=result.model_description if result else "N/A",
            hypothesis=hypothesis,
            train_py_code=code,
            n_features=result.n_features if result else 0,
            mean_oos_r2=result.mean_oos_r2 if result else 0.0,
            stability=result.stability if result else 0.0,
            adjusted_r2=result.mean_adj_r2 if result else 0.0,
            interpretability=result.interpretability if result else 0.0,
            composite=result.composite if result else 0.0,
            elapsed_seconds=result.elapsed_seconds if result else 0.0,
            status=status,
            error_message=error,
        )
        self.registry.record(record)
