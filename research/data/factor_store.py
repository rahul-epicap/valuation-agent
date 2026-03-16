"""Parquet-based cache for FMP factor data.

Stores fetched factor values in Parquet files under .cache/fmp/.
Handles staleness checks and incremental updates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from research.config.settings import settings


class FactorStore:
    """Manages Parquet cache for FMP factor data."""

    def __init__(self, cache_dir: Path | None = None):
        self._dir = cache_dir or settings.fmp_cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def factors_path(self) -> Path:
        return self._dir / "factors.parquet"

    @property
    def metadata_path(self) -> Path:
        return self._dir / "fetch_metadata.parquet"

    def load(self) -> pd.DataFrame | None:
        """Load cached factor data. Returns None if no cache exists."""
        if not self.factors_path.exists():
            return None
        return pd.read_parquet(self.factors_path)

    def save(self, df: pd.DataFrame) -> None:
        """Save factor data to Parquet cache."""
        df.to_parquet(self.factors_path, index=False)

    def save_metadata(self, tickers: list[str]) -> None:
        """Record fetch timestamps for tickers."""
        now = datetime.now(timezone.utc).isoformat()
        records = [{"ticker": t, "fetched_at": now} for t in tickers]
        new_df = pd.DataFrame(records)

        if self.metadata_path.exists():
            existing = pd.read_parquet(self.metadata_path)
            # Update existing, add new
            combined = pd.concat([existing, new_df]).drop_duplicates(subset=["ticker"], keep="last")
        else:
            combined = new_df

        combined.to_parquet(self.metadata_path, index=False)

    def get_stale_tickers(
        self,
        all_tickers: list[str],
        stale_days: int = 7,
    ) -> list[str]:
        """Return tickers whose cached data is stale or missing."""
        if not self.metadata_path.exists():
            return list(all_tickers)

        meta = pd.read_parquet(self.metadata_path)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).isoformat()

        fresh = set(meta[meta["fetched_at"] > cutoff]["ticker"].tolist())
        return [t for t in all_tickers if t not in fresh]

    def upsert_factors(self, new_data: list[dict]) -> pd.DataFrame:
        """Merge new factor data into existing cache.

        Args:
            new_data: List of dicts with 'ticker' key and factor values.

        Returns:
            Updated full DataFrame.
        """
        new_df = pd.DataFrame(new_data)

        existing = self.load()
        if existing is not None and not existing.empty:
            # Remove old entries for tickers we're updating
            updated_tickers = set(new_df["ticker"].tolist())
            kept = existing[~existing["ticker"].isin(updated_tickers)]
            combined = pd.concat([kept, new_df], ignore_index=True)
        else:
            combined = new_df

        self.save(combined)
        return combined

    def get_factor_matrix(
        self,
        tickers: list[str],
        factor_names: list[str] | None = None,
    ) -> pd.DataFrame:
        """Get factor values for specific tickers.

        Returns DataFrame indexed by ticker with factor columns.
        Missing tickers get NaN values.
        """
        df = self.load()
        if df is None:
            result = pd.DataFrame(index=tickers)
            result.index.name = "ticker"
            return result

        df = df.set_index("ticker")

        if factor_names:
            available = [f for f in factor_names if f in df.columns]
            df = df[available]

        # Reindex to include all requested tickers (NaN for missing)
        return df.reindex(tickers)
