"""Research module settings — Pydantic-based configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

_RESEARCH_DIR = Path(__file__).resolve().parent.parent
_CACHE_DIR = _RESEARCH_DIR / ".cache"


class ResearchSettings(BaseSettings):
    """Settings for the autoresearch system.

    Reads from environment variables and .env file in the research/ directory.
    """

    # --- Database (Railway production) ---
    # Only used for one-time fetch and upload; never during experiment runs.
    DATABASE_URL: str = ""

    # --- FMP API ---
    FMP_API_KEY: str = ""
    FMP_BASE_URL: str = "https://financialmodelingprep.com"
    FMP_RATE_LIMIT_PER_MINUTE: int = 3000
    FMP_CACHE_STALE_DAYS_PROFILE: int = 7
    FMP_CACHE_STALE_DAYS_METRICS: int = 30

    # --- LLM Provider ---
    LLM_PROVIDER: str = "anthropic"  # anthropic | openai | local
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "claude-opus-4-6"
    LLM_LOCAL_BASE_URL: str = "http://localhost:11434/v1"  # Ollama

    # --- Experiment ---
    EXPERIMENT_TIMEOUT_SECONDS: int = 60
    MAX_FEATURES: int = 20
    MIN_OBSERVATIONS: int = 10

    # --- Evaluation Weights ---
    WEIGHT_OOS_R2: float = 0.40
    WEIGHT_STABILITY: float = 0.25
    WEIGHT_ADJUSTED_R2: float = 0.20
    WEIGHT_INTERPRETABILITY: float = 0.15

    # --- Temporal Split ---
    TRAIN_WINDOW_MONTHS: int = 12
    TEST_WINDOW_MONTHS: int = 1
    STRIDE_MONTHS: int = 1

    # --- Paths ---
    CACHE_DIR: Path = _CACHE_DIR
    RESEARCH_DIR: Path = _RESEARCH_DIR

    @property
    def snapshot_path(self) -> Path:
        return self.CACHE_DIR / "snapshot.json"

    @property
    def fmp_cache_dir(self) -> Path:
        return self.CACHE_DIR / "fmp"

    @property
    def prepared_dataset_path(self) -> Path:
        return self.CACHE_DIR / "prepared_dataset.pkl"

    @property
    def results_tsv_path(self) -> Path:
        return self.RESEARCH_DIR / "results.tsv"

    @property
    def train_py_path(self) -> Path:
        return self.RESEARCH_DIR / "train.py"

    @property
    def program_md_path(self) -> Path:
        return self.RESEARCH_DIR / "program.md"

    @property
    def experiment_db_path(self) -> Path:
        return self.CACHE_DIR / "experiments.db"

    @property
    def sync_database_url(self) -> str:
        """Convert async DB URL to sync for one-time operations."""
        url = self.DATABASE_URL
        if "asyncpg" in url:
            return url.replace("asyncpg", "psycopg2")
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    model_config = {
        "env_file": str(_RESEARCH_DIR / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = ResearchSettings()
