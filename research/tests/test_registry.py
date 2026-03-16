"""Tests for experiment registry."""

from __future__ import annotations

from research.experiments.registry import ExperimentRecord, ExperimentRegistry


def _make_record(
    exp_id: str = "test_001",
    metric: str = "evRev",
    composite: float = 0.5,
    status: str = "improved",
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=exp_id,
        timestamp="2026-03-16T00:00:00Z",
        metric_type=metric,
        model_description="Test model",
        hypothesis="Test hypothesis",
        train_py_code="# test code",
        n_features=1,
        mean_oos_r2=0.4,
        stability=0.7,
        adjusted_r2=0.38,
        interpretability=0.6,
        composite=composite,
        elapsed_seconds=1.5,
        status=status,
    )


class TestRegistry:
    def test_record_and_retrieve(self, tmp_path):
        db = tmp_path / "test.db"
        reg = ExperimentRegistry(db_path=db, tsv_path=tmp_path / "results.tsv")

        rec = _make_record()
        reg.record(rec)

        retrieved = reg.get_by_id("test_001")
        assert retrieved is not None
        assert retrieved.experiment_id == "test_001"
        assert retrieved.composite == 0.5

    def test_get_best(self, tmp_path):
        db = tmp_path / "test.db"
        reg = ExperimentRegistry(db_path=db, tsv_path=tmp_path / "results.tsv")

        reg.record(_make_record("exp1", composite=0.3))
        reg.record(_make_record("exp2", composite=0.6))
        reg.record(_make_record("exp3", composite=0.4))

        best = reg.get_best("evRev")
        assert best is not None
        assert best.experiment_id == "exp2"

    def test_leaderboard(self, tmp_path):
        db = tmp_path / "test.db"
        reg = ExperimentRegistry(db_path=db, tsv_path=tmp_path / "results.tsv")

        for i in range(5):
            reg.record(_make_record(f"exp{i}", composite=i * 0.1))

        board = reg.get_leaderboard("evRev", limit=3)
        assert len(board) == 3
        assert board[0].composite > board[1].composite

    def test_consecutive_failures(self, tmp_path):
        db = tmp_path / "test.db"
        reg = ExperimentRegistry(db_path=db, tsv_path=tmp_path / "results.tsv")

        reg.record(_make_record("e1", status="improved"))
        reg.record(_make_record("e2", status="worse"))
        reg.record(_make_record("e3", status="worse"))
        reg.record(_make_record("e4", status="error"))

        assert reg.consecutive_failures("evRev") == 3

    def test_count(self, tmp_path):
        db = tmp_path / "test.db"
        reg = ExperimentRegistry(db_path=db, tsv_path=tmp_path / "results.tsv")

        reg.record(_make_record("e1", metric="evRev"))
        reg.record(_make_record("e2", metric="evGP"))
        reg.record(_make_record("e3", metric="evRev"))

        assert reg.count() == 3
        assert reg.count("evRev") == 2
        assert reg.count("evGP") == 1

    def test_generate_id(self):
        id1 = ExperimentRegistry.generate_id()
        id2 = ExperimentRegistry.generate_id()
        assert id1.startswith("exp_")
        assert id1 != id2
