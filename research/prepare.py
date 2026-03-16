"""FIXED data preparation — never modified by the agent.

Loads cached snapshot + FMP factors, builds PreparedDataset with:
- Multiples arrays: {metric_type: (n_dates, n_tickers)}
- Growth arrays: same shape
- Factor matrix: (n_dates, n_tickers, n_factors) — z-score standardized
- Valid masks: outlier caps applied
- Temporal splits: rolling window for train/test
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field

import numpy as np

from research.config.settings import settings
from research.data.snapshot_loader import load_cached_snapshot

# Outlier caps matching production valuation_service.py
OUTLIER_CAPS: dict[str, float] = {
    "evRev": 80.0,
    "evGP": 120.0,
    "pEPS": 200.0,
    "pEPS_GAAP": 200.0,
}

# Metric key mappings (matching production exactly)
MULTIPLE_KEYS: dict[str, str] = {
    "evRev": "er",
    "evGP": "eg",
    "pEPS": "pe",
    "pEPS_GAAP": "pe_gaap",
}
GROWTH_KEYS: dict[str, str] = {
    "evRev": "rg",
    "evGP": "rg",
    "pEPS": "xg",
    "pEPS_GAAP": "xg_gaap",
}


@dataclass
class TemporalSplit:
    """A single train/test temporal split."""

    train_date_indices: np.ndarray  # Indices into dates array for training
    test_date_idx: int  # Single date index for testing


@dataclass
class PreparedDataset:
    """Fully prepared dataset for regression experiments.

    All arrays are aligned: axis 0 = dates, axis 1 = tickers.
    NaN indicates missing/invalid data.
    """

    # Metadata
    dates: list[str]
    tickers: list[str]
    industries: dict[str, str]  # ticker → industry
    indices: dict[str, list[str]]  # ticker → [index_names]

    # Core arrays: (n_dates, n_tickers) — NaN for missing
    multiples: dict[str, np.ndarray]  # metric_type → array
    growth: dict[str, np.ndarray]  # metric_type → growth array

    # Derived factors from dashboard data: (n_dates, n_tickers)
    gross_margin: np.ndarray  # er / eg per date/ticker

    # Valid masks after outlier filtering: (n_dates, n_tickers) bool
    valid_masks: dict[str, np.ndarray]  # metric_type → mask

    # Index membership dummies: {index_name: (n_tickers,) bool array}
    index_dummies: dict[str, np.ndarray]

    # FMP cross-sectional factors: {factor_name: (n_tickers,) float array}
    # NaN for tickers without FMP data. Z-score standardized.
    fmp_factors: dict[str, np.ndarray] = field(default_factory=dict)

    # Raw FMP factor names available
    fmp_factor_names: list[str] = field(default_factory=list)

    # Temporal splits for evaluation
    splits: list[TemporalSplit] = field(default_factory=list)

    @property
    def n_dates(self) -> int:
        return len(self.dates)

    @property
    def n_tickers(self) -> int:
        return len(self.tickers)

    @property
    def n_splits(self) -> int:
        return len(self.splits)


def _resolve_eps_keys(metric_type: str, d: dict) -> tuple[str, str]:
    """Per-ticker EPS key resolution matching production logic."""
    if metric_type == "pEPS" and d.get("epsMarketType") == "GAAP":
        return "pe_gaap", "xg_gaap"
    return MULTIPLE_KEYS[metric_type], GROWTH_KEYS[metric_type]


def _ok_eps(d: dict, di: int, metric_type: str) -> bool:
    """EPS quality check matching production filters.ts/valuation_service.py."""
    use_gaap = metric_type == "pEPS_GAAP" or (
        metric_type == "pEPS" and d.get("epsMarketType") == "GAAP"
    )
    if use_gaap:
        fe_arr = d.get("fe_gaap", [])
        xg_arr = d.get("xg_gaap", [])
    else:
        fe_arr = d.get("fe", [])
        xg_arr = d.get("xg", [])

    fe = fe_arr[di] if di < len(fe_arr) else None
    xg = xg_arr[di] if di < len(xg_arr) else None

    if fe is None or fe <= 0.5:
        return False
    if xg is None or xg <= -0.75 or xg > 2.0:
        return False
    return True


def _build_arrays(
    data: dict,
    tickers: list[str],
    n_dates: int,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    """Build multiples, growth, and gross_margin arrays from raw dashboard data."""
    n_tickers = len(tickers)
    fm = data["fm"]

    multiples: dict[str, np.ndarray] = {}
    growth: dict[str, np.ndarray] = {}

    for metric_type in ["evRev", "evGP", "pEPS"]:
        m_arr = np.full((n_dates, n_tickers), np.nan)
        g_arr = np.full((n_dates, n_tickers), np.nan)

        for ti, ticker in enumerate(tickers):
            d = fm.get(ticker)
            if d is None:
                continue

            is_eps = metric_type in ("pEPS", "pEPS_GAAP")
            mk, gk = (
                _resolve_eps_keys(metric_type, d)
                if is_eps
                else (
                    MULTIPLE_KEYS[metric_type],
                    GROWTH_KEYS[metric_type],
                )
            )

            m_vals = d.get(mk, [])
            g_vals = d.get(gk, [])

            for di in range(min(n_dates, len(m_vals), len(g_vals))):
                m = m_vals[di]
                g = g_vals[di]
                if m is not None and g is not None:
                    m_arr[di, ti] = m
                    g_arr[di, ti] = g

        multiples[metric_type] = m_arr
        growth[metric_type] = g_arr

    # Gross margin: er / eg = (EV/Rev) / (EV/GP) = GP/Rev
    with np.errstate(divide="ignore", invalid="ignore"):
        gm = multiples["evRev"] / multiples["evGP"]
        gm[~np.isfinite(gm)] = np.nan

    return multiples, growth, gm


def _build_valid_masks(
    multiples: dict[str, np.ndarray],
    growth: dict[str, np.ndarray],
    data: dict,
    tickers: list[str],
    n_dates: int,
) -> dict[str, np.ndarray]:
    """Build boolean masks for valid (non-outlier) points per metric type."""
    masks: dict[str, np.ndarray] = {}

    for metric_type in ["evRev", "evGP", "pEPS"]:
        m = multiples[metric_type]
        g = growth[metric_type]
        cap = OUTLIER_CAPS[metric_type]

        # Base validity: both multiple and growth are finite
        valid = np.isfinite(m) & np.isfinite(g)

        # Outlier cap on multiple
        valid &= m <= cap

        # EPS-specific filters
        if metric_type in ("pEPS", "pEPS_GAAP"):
            fm = data["fm"]
            for ti, ticker in enumerate(tickers):
                d = fm.get(ticker)
                if d is None:
                    valid[:, ti] = False
                    continue
                for di in range(n_dates):
                    if valid[di, ti] and not _ok_eps(d, di, metric_type):
                        valid[di, ti] = False

        masks[metric_type] = valid

    return masks


def _build_index_dummies(
    indices: dict[str, list[str]],
    tickers: list[str],
) -> dict[str, np.ndarray]:
    """Build binary index membership arrays.

    indices: {ticker: [index_names]} from dashboard data.
    Returns: {index_name: (n_tickers,) bool array}.
    """
    # Invert: ticker → indices → index → tickers
    all_index_names: set[str] = set()
    for idx_list in indices.values():
        all_index_names.update(idx_list)

    ticker_to_idx = {t: i for i, t in enumerate(tickers)}
    n_tickers = len(tickers)

    dummies: dict[str, np.ndarray] = {}
    for idx_name in sorted(all_index_names):
        arr = np.zeros(n_tickers, dtype=bool)
        for ticker, idx_list in indices.items():
            if idx_name in idx_list and ticker in ticker_to_idx:
                arr[ticker_to_idx[ticker]] = True
        # Only include if >= 3 members (matches production filter)
        if arr.sum() >= 3:
            dummies[idx_name] = arr

    return dummies


def _load_fmp_factors(
    tickers: list[str],
) -> tuple[dict[str, np.ndarray], list[str]]:
    """Load FMP factor data from Parquet cache and z-score standardize.

    Returns:
        fmp_factors: {factor_name: (n_tickers,) float array} — z-scored, NaN for missing
        fmp_factor_names: list of available factor names
    """
    from research.data.factor_store import FactorStore

    store = FactorStore()
    df = store.load()

    if df is None or df.empty:
        return {}, []

    # Align to ticker ordering
    df_indexed = df.set_index("ticker") if "ticker" in df.columns else df
    # Exclude non-numeric / metadata columns
    skip_cols = {"ticker", "fmp_symbol", "isin", "fetched_at"}
    factor_cols = [c for c in df_indexed.columns if c not in skip_cols]

    n_tickers = len(tickers)
    fmp_factors: dict[str, np.ndarray] = {}
    fmp_factor_names: list[str] = []

    for col in factor_cols:
        arr = np.full(n_tickers, np.nan)
        for i, t in enumerate(tickers):
            if t in df_indexed.index:
                val = df_indexed.loc[t, col]
                if val is not None:
                    try:
                        fval = float(val)
                        if np.isfinite(fval):
                            arr[i] = fval
                    except (ValueError, TypeError):
                        pass

        # Only include if we have enough non-NaN values
        n_valid = np.isfinite(arr).sum()
        if n_valid < 10:
            continue

        # Z-score standardize (cross-sectional)
        finite_mask = np.isfinite(arr)
        mean = np.nanmean(arr)
        std = np.nanstd(arr)
        if std > 1e-10:
            arr_z = np.full(n_tickers, np.nan)
            arr_z[finite_mask] = (arr[finite_mask] - mean) / std
            fmp_factors[col] = arr_z
            fmp_factor_names.append(col)

    return fmp_factors, fmp_factor_names


def _build_temporal_splits(
    n_dates: int,
    train_window: int = 12,
    test_window: int = 1,
    stride: int = 1,
) -> list[TemporalSplit]:
    """Build rolling temporal splits for out-of-sample evaluation.

    Each split: train on [i : i + train_window], test on [i + train_window].
    """
    splits: list[TemporalSplit] = []

    for start in range(0, n_dates - train_window, stride):
        test_idx = start + train_window
        if test_idx >= n_dates:
            break
        train_indices = np.arange(start, start + train_window)
        splits.append(TemporalSplit(train_date_indices=train_indices, test_date_idx=test_idx))

    return splits


def build_dataset(
    data: dict | None = None,
    train_window: int | None = None,
    test_window: int | None = None,
    stride: int | None = None,
) -> PreparedDataset:
    """Build a PreparedDataset from cached snapshot data.

    Args:
        data: Dashboard data dict. If None, loads from cache.
        train_window: Training window size in months.
        test_window: Test window size.
        stride: Stride between splits.

    Returns:
        PreparedDataset ready for experiments.
    """
    if data is None:
        data = load_cached_snapshot()

    dates = data["dates"]
    tickers = data["tickers"]
    industries = data.get("industries", {})
    indices = data.get("indices", {})
    n_dates = len(dates)

    tw = train_window or settings.TRAIN_WINDOW_MONTHS
    tsw = test_window or settings.TEST_WINDOW_MONTHS
    st = stride or settings.STRIDE_MONTHS

    multiples, growth_arrays, gross_margin = _build_arrays(data, tickers, n_dates)
    valid_masks = _build_valid_masks(multiples, growth_arrays, data, tickers, n_dates)
    index_dummies = _build_index_dummies(indices, tickers)
    splits = _build_temporal_splits(n_dates, tw, tsw, st)

    # Load FMP factors if available
    fmp_factors, fmp_factor_names = _load_fmp_factors(tickers)

    dataset = PreparedDataset(
        dates=dates,
        tickers=tickers,
        industries=industries,
        indices=indices,
        multiples=multiples,
        growth=growth_arrays,
        gross_margin=gross_margin,
        valid_masks=valid_masks,
        index_dummies=index_dummies,
        fmp_factors=fmp_factors,
        fmp_factor_names=fmp_factor_names,
        splits=splits,
    )

    return dataset


def build_and_cache_dataset(**kwargs) -> PreparedDataset:
    """Build dataset and cache to disk."""
    dataset = build_dataset(**kwargs)
    cache_path = settings.prepared_dataset_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(dataset, f)
    print(f"Cached prepared dataset to: {cache_path}")
    print(f"  Dates: {dataset.n_dates}, Tickers: {dataset.n_tickers}")
    print(f"  Splits: {dataset.n_splits}")
    print(f"  Index dummies: {len(dataset.index_dummies)}")
    return dataset


def load_cached_dataset() -> PreparedDataset:
    """Load cached PreparedDataset from disk."""
    path = settings.prepared_dataset_path
    if not path.exists():
        raise FileNotFoundError(f"No cached dataset at {path}. Run prepare first.")
    with open(path, "rb") as f:
        return pickle.load(f)


def get_baseline_points(
    dataset: PreparedDataset,
    metric_type: str,
    date_idx: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract valid (growth_pct, multiple) points for a single date.

    Returns (X, y) where X = growth percentages, y = multiples.
    This replicates the production filter_points behavior.
    """
    mask = dataset.valid_masks[metric_type][date_idx]
    g = dataset.growth[metric_type][date_idx]
    m = dataset.multiples[metric_type][date_idx]

    valid = mask & np.isfinite(g) & np.isfinite(m)
    X = g[valid] * 100  # Convert to percentage (matching production)
    y = m[valid]

    return X, y


def get_valid_ticker_mask(
    dataset: PreparedDataset,
    metric_type: str,
    date_idx: int,
) -> np.ndarray:
    """Return boolean mask over tickers that are valid at this date.

    Use this to index into dataset.fmp_factors for valid points:
        mask = get_valid_ticker_mask(dataset, metric_type, date_idx)
        lmc = dataset.fmp_factors["log_market_cap"][mask]
    The resulting array aligns with the (X, y) from get_baseline_points.
    """
    mask = dataset.valid_masks[metric_type][date_idx]
    g = dataset.growth[metric_type][date_idx]
    m = dataset.multiples[metric_type][date_idx]
    return mask & np.isfinite(g) & np.isfinite(m)


def get_fmp_factor_for_points(
    dataset: PreparedDataset,
    metric_type: str,
    date_idx: int,
    factor_name: str,
    impute_nan: bool = True,
) -> np.ndarray:
    """Get an FMP factor array aligned with get_baseline_points output.

    Returns array of shape (n_valid_points,). NaN values are mean-imputed
    by default. Returns zeros if factor not available.
    """
    if factor_name not in dataset.fmp_factors:
        mask = get_valid_ticker_mask(dataset, metric_type, date_idx)
        return np.zeros(int(mask.sum()))

    raw = dataset.fmp_factors[factor_name]
    mask = get_valid_ticker_mask(dataset, metric_type, date_idx)
    values = raw[mask].copy()

    if impute_nan:
        finite = np.isfinite(values)
        if finite.any() and not finite.all():
            values[~finite] = np.nanmean(values)
        elif not finite.any():
            values[:] = 0.0

    return values


def get_baseline_r2(
    dataset: PreparedDataset,
    metric_type: str,
    date_idx: int,
) -> dict[str, float] | None:
    """Compute baseline OLS R² for a single date, matching production logic.

    Returns {slope, intercept, r2, n} or None if < 3 points.
    """
    X, y = get_baseline_points(dataset, metric_type, date_idx)

    n = len(X)
    if n < 3:
        return None

    sx = X.sum()
    sy = y.sum()
    sxy = (X * y).sum()
    sx2 = (X * X).sum()

    d = n * sx2 - sx * sx
    if abs(d) < 1e-12:
        return None

    slope = (n * sxy - sx * sy) / d
    intercept = (sy - slope * sx) / n
    sst = (y * y).sum() - sy * sy / n

    y_pred = slope * X + intercept
    sse = ((y - y_pred) ** 2).sum()

    r2 = (1 - sse / sst) if sst > 0 else 0.0

    return {"slope": float(slope), "intercept": float(intercept), "r2": float(r2), "n": int(n)}
