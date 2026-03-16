"""SQLite-backed experiment tracking registry.

Tracks all experiment attempts, their results, and the train.py code.
Mirrors results.tsv for compatibility with the autoresearch convention.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from research.config.settings import settings


@dataclass
class ExperimentRecord:
    """A single experiment record."""

    experiment_id: str
    timestamp: str
    metric_type: str
    model_description: str
    hypothesis: str
    train_py_code: str
    n_features: int
    mean_oos_r2: float
    stability: float
    adjusted_r2: float
    interpretability: float
    composite: float
    elapsed_seconds: float
    status: str  # "improved", "worse", "error"
    error_message: str | None = None
    git_commit: str | None = None


class ExperimentRegistry:
    """SQLite-backed experiment registry."""

    def __init__(self, db_path: Path | None = None, tsv_path: Path | None = None):
        self._db_path = db_path or settings.experiment_db_path
        self._tsv_path = tsv_path or settings.results_tsv_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    model_description TEXT,
                    hypothesis TEXT,
                    train_py_code TEXT,
                    n_features INTEGER,
                    mean_oos_r2 REAL,
                    stability REAL,
                    adjusted_r2 REAL,
                    interpretability REAL,
                    composite REAL,
                    elapsed_seconds REAL,
                    status TEXT,
                    error_message TEXT,
                    git_commit TEXT
                )
            """)

    def record(self, rec: ExperimentRecord) -> None:
        """Insert an experiment record."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO experiments
                (experiment_id, timestamp, metric_type, model_description,
                 hypothesis, train_py_code, n_features, mean_oos_r2,
                 stability, adjusted_r2, interpretability, composite,
                 elapsed_seconds, status, error_message, git_commit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec.experiment_id,
                    rec.timestamp,
                    rec.metric_type,
                    rec.model_description,
                    rec.hypothesis,
                    rec.train_py_code,
                    rec.n_features,
                    rec.mean_oos_r2,
                    rec.stability,
                    rec.adjusted_r2,
                    rec.interpretability,
                    rec.composite,
                    rec.elapsed_seconds,
                    rec.status,
                    rec.error_message,
                    rec.git_commit,
                ),
            )

        # Also append to results.tsv
        self._append_tsv(rec)

    def _append_tsv(self, rec: ExperimentRecord) -> None:
        """Append record to results.tsv (autoresearch convention)."""
        tsv_path = self._tsv_path
        line = "\t".join(
            [
                rec.experiment_id,
                rec.timestamp,
                rec.metric_type,
                rec.model_description or "",
                str(rec.n_features),
                f"{rec.mean_oos_r2:.6f}",
                f"{rec.stability:.6f}",
                f"{rec.adjusted_r2:.6f}",
                f"{rec.interpretability:.6f}",
                f"{rec.composite:.6f}",
                f"{rec.elapsed_seconds:.1f}",
                rec.status,
            ]
        )
        with open(tsv_path, "a") as f:
            f.write(line + "\n")

    def get_best(self, metric_type: str) -> ExperimentRecord | None:
        """Get the best experiment by composite score for a metric."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT * FROM experiments
                WHERE metric_type = ? AND status = 'improved'
                ORDER BY composite DESC LIMIT 1""",
                (metric_type,),
            ).fetchone()
            return self._row_to_record(row) if row else None

    def get_by_id(self, experiment_id: str) -> ExperimentRecord | None:
        """Get a specific experiment by ID."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM experiments WHERE experiment_id = ?",
                (experiment_id,),
            ).fetchone()
            return self._row_to_record(row) if row else None

    def get_recent(
        self,
        metric_type: str,
        limit: int = 10,
    ) -> list[ExperimentRecord]:
        """Get recent experiments for a metric."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM experiments
                WHERE metric_type = ?
                ORDER BY timestamp DESC LIMIT ?""",
                (metric_type, limit),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def get_leaderboard(
        self,
        metric_type: str,
        limit: int = 20,
    ) -> list[ExperimentRecord]:
        """Get top experiments by composite score."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM experiments
                WHERE metric_type = ? AND status = 'improved'
                ORDER BY composite DESC LIMIT ?""",
                (metric_type, limit),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    def count(self, metric_type: str | None = None) -> int:
        """Count experiments."""
        with sqlite3.connect(self._db_path) as conn:
            if metric_type:
                row = conn.execute(
                    "SELECT COUNT(*) FROM experiments WHERE metric_type = ?",
                    (metric_type,),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()
            return row[0] if row else 0

    def consecutive_failures(self, metric_type: str) -> int:
        """Count consecutive non-improved experiments from the latest."""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT status FROM experiments
                WHERE metric_type = ?
                ORDER BY rowid DESC LIMIT 10""",
                (metric_type,),
            ).fetchall()

            count = 0
            for (status,) in rows:
                if status != "improved":
                    count += 1
                else:
                    break
            return count

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ExperimentRecord:
        return ExperimentRecord(
            experiment_id=row["experiment_id"],
            timestamp=row["timestamp"],
            metric_type=row["metric_type"],
            model_description=row["model_description"],
            hypothesis=row["hypothesis"] or "",
            train_py_code=row["train_py_code"] or "",
            n_features=row["n_features"] or 0,
            mean_oos_r2=row["mean_oos_r2"] or 0.0,
            stability=row["stability"] or 0.0,
            adjusted_r2=row["adjusted_r2"] or 0.0,
            interpretability=row["interpretability"] or 0.0,
            composite=row["composite"] or 0.0,
            elapsed_seconds=row["elapsed_seconds"] or 0.0,
            status=row["status"] or "unknown",
            error_message=row["error_message"],
            git_commit=row["git_commit"],
        )

    @staticmethod
    def generate_id() -> str:
        """Generate a unique experiment ID."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        import hashlib
        import os

        rand = hashlib.sha256(os.urandom(8)).hexdigest()[:6]
        return f"exp_{ts}_{rand}"
