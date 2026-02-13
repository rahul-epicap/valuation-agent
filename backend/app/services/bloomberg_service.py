"""
Bloomberg Data Bridge service.

Fetches financial data directly from Bloomberg Desktop API (DAPI) via the `blp`
library, transforms it into the same dashboard JSON format produced by
excel_parser.py, and returns it ready for snapshot storage.

Uses BDH (Bloomberg Data History) for time-series data and BDP for reference
data. Does NOT require BQL authorization.

Prerequisite: Bloomberg Terminal must be running and logged in on the same
machine as the backend server.

BDH Field Mapping:
    CURR_ENTP_VAL                    → Enterprise Value
    BEST_SALES + 1BF override       → Forward (FY1) Revenue consensus
    BEST_SALES + 2BF override       → Next (FY2) Revenue consensus (for growth)
    BEST_GROSS_MARGIN + 1BF         → Forward (FY1) Gross Margin % consensus
    BEST_EPS + 1BF                  → Forward (FY1) EPS consensus  (= fe)
    IS_COMP_EPS_EXCL_STOCK_COMP     → Annual trailing EPS (via YEARLY BDH, forward-filled)
    BEST_PE_RATIO                   → Forward P/E ratio            (= pe)

Derived in Python:
    er = EV / Forward Revenue
    eg = EV / (BEST_GROSS_MARGIN/100 * Forward Revenue)
    rg = (FY2 Revenue / FY1 Revenue) - 1
    xg = (Forward EPS / Trailing EPS) - 1
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from blp import blp

logger = logging.getLogger(__name__)

# Path to the canonical ticker list
_TICKERS_PATH = Path(__file__).resolve().parent.parent.parent / "tickers.json"

# BDH batch size — keeps each query under Bloomberg's row limits
_BATCH_SIZE = 40

# All metric keys that each ticker must have in the output (matches excel_parser)
_ALL_METRIC_KEYS = ("er", "eg", "pe", "rg", "xg", "fe")


def _clean_ticker(bbg_ticker: str) -> str:
    """Strip ' US Equity' suffix to get the short ticker symbol."""
    s = bbg_ticker.strip()
    if s.endswith(" US Equity"):
        return s[: -len(" US Equity")].strip()
    return s


def _format_date(dt: date | datetime | pd.Timestamp) -> str:
    """Format a date as YYYY-MM-DD string."""
    if isinstance(dt, pd.Timestamp):
        return dt.strftime("%Y-%m-%d")
    if isinstance(dt, (date, datetime)):
        return dt.strftime("%Y-%m-%d")
    return str(dt)[:10]


def _safe_float(val: object) -> float | None:
    """Convert a value to float or None, handling NaN/Inf/missing."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


class BloombergService:
    """Wraps the blp library to fetch Bloomberg data and produce dashboard JSON."""

    def __init__(self) -> None:
        self._bquery: blp.BlpQuery | None = None
        self._tickers: list[str] = []
        self._load_tickers()

    def _load_tickers(self) -> None:
        """Load the ticker universe from tickers.json."""
        with open(_TICKERS_PATH) as f:
            self._tickers = json.load(f)
        logger.info("Loaded %d tickers from %s", len(self._tickers), _TICKERS_PATH)

    def start(self) -> None:
        """Open a Bloomberg session. Call once on app startup."""
        self._bquery = blp.BlpQuery().start()
        logger.info("Bloomberg session started")

    def stop(self) -> None:
        """Close the Bloomberg session. Call on app shutdown."""
        if self._bquery is not None:
            try:
                self._bquery.stop()
            except Exception:
                logger.exception("Error stopping Bloomberg session")
            self._bquery = None
            logger.info("Bloomberg session stopped")

    @property
    def tickers(self) -> list[str]:
        return list(self._tickers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_bbg_date(date_str: str) -> str:
        """Convert YYYY-MM-DD to YYYYMMDD for Bloomberg API."""
        return date_str.replace("-", "")

    @staticmethod
    def _shift_date_back(date_str: str, years: int) -> str:
        """Shift a YYYY-MM-DD date back by N years."""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        shifted = dt.replace(year=dt.year - years)
        return shifted.strftime("%Y-%m-%d")

    def _bdh_sync(
        self,
        securities: list[str],
        field: str,
        start_date: str,
        end_date: str,
        overrides: list[tuple[str, str]] | None = None,
        fill_prev: bool = False,
    ) -> pd.DataFrame:
        """Run a BDH query synchronously (meant to be called in a thread)."""
        if self._bquery is None:
            raise RuntimeError("Bloomberg session not started")
        options: dict[str, str] = {"periodicitySelection": "MONTHLY"}
        if fill_prev:
            options["periodicityAdjustment"] = "CALENDAR"
        return self._bquery.bdh(
            securities=securities,
            fields=[field],
            start_date=self._to_bbg_date(start_date),
            end_date=self._to_bbg_date(end_date),
            overrides=overrides,
            options=options,
        )

    def _bdh_yearly_sync(
        self,
        securities: list[str],
        field: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Run a BDH query with YEARLY periodicity (for annual fundamental data)."""
        if self._bquery is None:
            raise RuntimeError("Bloomberg session not started")
        return self._bquery.bdh(
            securities=securities,
            fields=[field],
            start_date=self._to_bbg_date(start_date),
            end_date=self._to_bbg_date(end_date),
            options={"periodicitySelection": "YEARLY"},
        )

    def _bdp_sync(self, securities: list[str], fields: list[str]) -> pd.DataFrame:
        """Run a BDP query synchronously."""
        if self._bquery is None:
            raise RuntimeError("Bloomberg session not started")
        return self._bquery.bdp(securities, fields)

    @staticmethod
    def _batches(items: list[str], size: int) -> list[list[str]]:
        """Split a list into batches of the given size."""
        return [items[i : i + size] for i in range(0, len(items), size)]

    @staticmethod
    def _parse_bdh_dataframe(
        df: pd.DataFrame,
        field: str,
    ) -> dict[str, dict[str, float | None]]:
        """
        Parse a BDH result DataFrame into {ticker: {date_str: value}}.

        BDH DataFrames from the blp library typically have:
          - Index: date
          - Columns: MultiIndex (security, field) or flat (security) for single field
        Or sometimes:
          - Index: MultiIndex (security, date)
          - Columns: field names
        """
        result: dict[str, dict[str, float | None]] = {}

        if df.empty:
            return result

        df = df.reset_index()
        cols = list(df.columns)

        # Detect format: look for a 'date' column and 'security' column
        # After reset_index, common column patterns:
        #   ['date', ('ADBE US Equity', 'FIELD'), ('CRM US Equity', 'FIELD'), ...]
        #   ['index', 'date', 'FIELD']  (if multi-index was security, date)
        #   ['date', 'ADBE US Equity', 'CRM US Equity', ...]  (single field)
        #   ['security', 'date', 'FIELD']

        # Strategy: find the date column, then iterate all other columns as tickers
        date_col = None
        security_col = None

        for c in cols:
            c_str = str(c).lower() if not isinstance(c, tuple) else ""
            if c_str in ("date", "index") and date_col is None:
                # Check if it actually contains dates
                sample = df[c].iloc[0] if len(df) > 0 else None
                if isinstance(sample, (datetime, date, pd.Timestamp)):
                    date_col = c
            elif c_str == "security":
                security_col = c

        if security_col is not None and date_col is not None:
            # Long format: security, date, field columns
            val_col = None
            for c in cols:
                if c not in (security_col, date_col, "index"):
                    val_col = c
                    break
            if val_col is None:
                return result
            for _, row in df.iterrows():
                ticker = str(row[security_col]).strip()
                dt = row[date_col]
                date_str = _format_date(dt)
                val = _safe_float(row[val_col])
                result.setdefault(ticker, {})[date_str] = val

        elif date_col is not None:
            # Wide format: date column + one column per security
            for c in cols:
                if c == date_col:
                    continue
                # Column might be a tuple like ('ADBE US Equity', 'CURR_ENTP_VAL')
                if isinstance(c, tuple):
                    ticker = str(c[0]).strip()
                else:
                    ticker = str(c).strip()
                    # Skip non-ticker columns
                    if ticker.lower() in ("index", "level_0"):
                        continue

                for _, row in df.iterrows():
                    dt = row[date_col]
                    date_str = _format_date(dt)
                    val = _safe_float(row[c])
                    result.setdefault(ticker, {})[date_str] = val
        else:
            # Fallback: try to parse whatever structure we got
            logger.warning(
                "BDH result has unexpected format. Columns: %s", cols
            )

        return result

    async def _fetch_bdh_metric(
        self,
        field: str,
        start_date: str,
        end_date: str,
        overrides: list[tuple[str, str]] | None = None,
        fill_prev: bool = False,
    ) -> dict[str, dict[str, float | None]]:
        """Fetch one BDH field for all tickers, batched."""
        result: dict[str, dict[str, float | None]] = {}

        for batch in self._batches(self._tickers, _BATCH_SIZE):
            try:
                df = await asyncio.to_thread(
                    self._bdh_sync, batch, field, start_date, end_date, overrides, fill_prev
                )
            except Exception:
                logger.exception(
                    "BDH query failed for field=%s, batch starting with %s",
                    field,
                    batch[0],
                )
                for t in batch:
                    result.setdefault(t, {})
                continue

            if df.empty:
                for t in batch:
                    result.setdefault(t, {})
                continue

            parsed = self._parse_bdh_dataframe(df, field)
            for ticker, date_vals in parsed.items():
                result.setdefault(ticker, {}).update(date_vals)

        return result

    async def _fetch_yearly_bdh_metric(
        self,
        field: str,
        start_date: str,
        end_date: str,
    ) -> dict[str, dict[str, float | None]]:
        """
        Fetch one BDH field with YEARLY periodicity for all tickers, batched.

        Returns sparse {ticker: {date_str: value}} with one entry per fiscal year.
        Use _forward_fill_yearly_to_monthly() to expand to the monthly date grid.
        """
        result: dict[str, dict[str, float | None]] = {}

        for batch in self._batches(self._tickers, _BATCH_SIZE):
            try:
                df = await asyncio.to_thread(
                    self._bdh_yearly_sync, batch, field, start_date, end_date
                )
            except Exception:
                logger.exception(
                    "BDH YEARLY query failed for field=%s, batch starting with %s",
                    field,
                    batch[0],
                )
                for t in batch:
                    result.setdefault(t, {})
                continue

            if df.empty:
                for t in batch:
                    result.setdefault(t, {})
                continue

            parsed = self._parse_bdh_dataframe(df, field)
            for ticker, date_vals in parsed.items():
                result.setdefault(ticker, {}).update(date_vals)

        return result

    @staticmethod
    def _forward_fill_yearly_to_monthly(
        yearly_data: dict[str, dict[str, float | None]],
        monthly_dates: list[str],
    ) -> dict[str, list[float | None]]:
        """
        Forward-fill sparse yearly data to a monthly date grid.

        For each ticker, sorts its yearly data points by date, then for each
        monthly date assigns the most recent yearly value (or None if no yearly
        value precedes it).
        """
        arrays: dict[str, list[float | None]] = {}

        for bbg_ticker, date_vals in yearly_data.items():
            short = _clean_ticker(bbg_ticker)
            # Sort yearly observations by date
            sorted_yearly = sorted(date_vals.items(), key=lambda x: x[0])

            values: list[float | None] = []
            yearly_idx = 0
            current_val: float | None = None

            for m_date in monthly_dates:
                # Advance yearly_idx while the yearly date <= the monthly date
                while (
                    yearly_idx < len(sorted_yearly)
                    and sorted_yearly[yearly_idx][0] <= m_date
                ):
                    current_val = sorted_yearly[yearly_idx][1]
                    yearly_idx += 1
                values.append(current_val)

            arrays[short] = values

        return arrays

    async def _fetch_industries(self) -> dict[str, str]:
        """Fetch INDUSTRY_SECTOR for all tickers via BDP."""
        industries: dict[str, str] = {}

        for batch in self._batches(self._tickers, _BATCH_SIZE):
            try:
                df = await asyncio.to_thread(
                    self._bdp_sync, batch, ["INDUSTRY_SECTOR"]
                )
            except Exception:
                logger.exception(
                    "BDP INDUSTRY_SECTOR failed for batch starting with %s",
                    batch[0],
                )
                continue

            if df.empty:
                continue

            df = df.reset_index()

            # BDP returns columns like ['security', 'INDUSTRY_SECTOR']
            # After reset_index there may be an extra 'index' column
            sec_col = None
            for c in df.columns:
                if str(c).lower() == "security":
                    sec_col = c
                    break

            if sec_col is None:
                # Fallback: look for a column containing " US Equity" values
                for c in df.columns:
                    sample = df[c].iloc[0] if len(df) > 0 else ""
                    if isinstance(sample, str) and "Equity" in sample:
                        sec_col = c
                        break

            if sec_col is None:
                logger.warning("BDP result: cannot find security column. Columns: %s", list(df.columns))
                continue

            for _, row in df.iterrows():
                ticker_bbg = str(row[sec_col]).strip()
                short = _clean_ticker(ticker_bbg)
                sector = row.get("INDUSTRY_SECTOR")
                if sector and isinstance(sector, str) and sector.strip():
                    industries[short] = sector.strip()

        return industries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_all(
        self,
        start_date: str = "2015-01-01",
        end_date: str | None = None,
    ) -> dict:
        """
        Fetch all metrics from Bloomberg and assemble the dashboard JSON.

        Returns a dict with the same schema as excel_parser.parse_excel():
        {
            "dates": [...],
            "tickers": [...],
            "industries": {...},
            "fm": { ticker: { er, eg, pe, rg, xg, fe: [...] } }
        }
        """
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")

        logger.info(
            "Starting Bloomberg fetch: %d tickers, %s to %s",
            len(self._tickers),
            start_date,
            end_date,
        )

        # Fetch all BDH metrics concurrently
        # Gross profit is derived: BEST_GROSS_MARGIN (%) * BEST_SALES (1BF) / 100
        # Revenue growth: BEST_SALES(2BF) / BEST_SALES(1BF) - 1
        # EPS growth: BEST_EPS(1BF) / IS_COMP_EPS_EXCL_STOCK_COMP (annual) - 1
        (
            ev_data,
            fwd_rev_data,
            nxt_rev_data,
            gross_margin_data,
            fwd_eps_data,
            trail_eps_yearly_data,
            pe_data,
            industries,
        ) = await asyncio.gather(
            self._fetch_bdh_metric("CURR_ENTP_VAL", start_date, end_date),
            self._fetch_bdh_metric(
                "BEST_SALES", start_date, end_date,
                overrides=[("BEST_FPERIOD_OVERRIDE", "1BF")],
            ),
            self._fetch_bdh_metric(
                "BEST_SALES", start_date, end_date,
                overrides=[("BEST_FPERIOD_OVERRIDE", "2BF")],
            ),
            self._fetch_bdh_metric(
                "BEST_GROSS_MARGIN", start_date, end_date,
                overrides=[("BEST_FPERIOD_OVERRIDE", "1BF")],
            ),
            self._fetch_bdh_metric(
                "BEST_EPS", start_date, end_date,
                overrides=[("BEST_FPERIOD_OVERRIDE", "1BF")],
            ),
            # Fetch yearly data starting 2 years earlier to ensure we capture the
            # most recent annual value for forward-filling (fiscal year-ends vary)
            self._fetch_yearly_bdh_metric(
                "IS_COMP_EPS_EXCL_STOCK_COMP",
                self._shift_date_back(start_date, years=2),
                end_date,
            ),
            self._fetch_bdh_metric("BEST_PE_RATIO", start_date, end_date),
            self._fetch_industries(),
        )

        # Build unified date list from monthly BDH data
        # (exclude yearly trail_eps_yearly_data — those dates are fiscal year-ends
        #  and would add odd non-monthly dates to the grid)
        all_dates_set: set[str] = set()
        for data in [
            ev_data,
            fwd_rev_data,
            nxt_rev_data,
            gross_margin_data,
            fwd_eps_data,
            pe_data,
        ]:
            for ticker_dates in data.values():
                all_dates_set.update(ticker_dates.keys())

        all_dates = sorted(all_dates_set)
        num_dates = len(all_dates)
        logger.info("Unified date range: %d dates", num_dates)

        # Build short ticker list
        short_tickers = sorted({_clean_ticker(t) for t in self._tickers})

        # Helper: convert {bbg_ticker: {date: val}} → {short_ticker: [val_per_date]}
        def to_arrays(
            data: dict[str, dict[str, float | None]],
        ) -> dict[str, list[float | None]]:
            arrays: dict[str, list[float | None]] = {}
            for bbg_ticker, date_vals in data.items():
                short = _clean_ticker(bbg_ticker)
                values = [date_vals.get(d) for d in all_dates]
                arrays[short] = values
            return arrays

        ev_arrays = to_arrays(ev_data)
        fwd_rev_arrays = to_arrays(fwd_rev_data)
        nxt_rev_arrays = to_arrays(nxt_rev_data)
        gm_arrays = to_arrays(gross_margin_data)
        fwd_eps_arrays = to_arrays(fwd_eps_data)
        # Trailing EPS: yearly data forward-filled to monthly grid
        trail_eps_arrays = self._forward_fill_yearly_to_monthly(
            trail_eps_yearly_data, all_dates
        )
        pe_arrays = to_arrays(pe_data)

        # Compute derived metrics
        er_arrays: dict[str, list[float | None]] = {}
        eg_arrays: dict[str, list[float | None]] = {}
        rg_arrays: dict[str, list[float | None]] = {}
        xg_arrays: dict[str, list[float | None]] = {}

        null_arr = [None] * num_dates

        for ticker in short_tickers:
            ev_vals = ev_arrays.get(ticker, null_arr)
            fwd_rev_vals = fwd_rev_arrays.get(ticker, null_arr)
            nxt_rev_vals = nxt_rev_arrays.get(ticker, null_arr)
            gm_vals = gm_arrays.get(ticker, null_arr)
            fwd_eps_vals = fwd_eps_arrays.get(ticker, null_arr)
            trail_eps_vals = trail_eps_arrays.get(ticker, null_arr)

            er_vals: list[float | None] = []
            eg_vals: list[float | None] = []
            rg_vals: list[float | None] = []
            xg_vals: list[float | None] = []

            for i in range(num_dates):
                ev = ev_vals[i] if i < len(ev_vals) else None
                fwd_rev = fwd_rev_vals[i] if i < len(fwd_rev_vals) else None
                nxt_rev = nxt_rev_vals[i] if i < len(nxt_rev_vals) else None
                gm = gm_vals[i] if i < len(gm_vals) else None
                fwd_eps = fwd_eps_vals[i] if i < len(fwd_eps_vals) else None
                trail_eps = trail_eps_vals[i] if i < len(trail_eps_vals) else None

                # EV / Forward Revenue
                if ev is not None and fwd_rev is not None and fwd_rev != 0:
                    er_vals.append(ev / fwd_rev)
                else:
                    er_vals.append(None)

                # EV / Forward Gross Profit
                # Gross Profit = BEST_GROSS_MARGIN (%) * BEST_SALES (1BF) / 100
                if (
                    ev is not None
                    and gm is not None
                    and fwd_rev is not None
                    and gm != 0
                    and fwd_rev != 0
                ):
                    fwd_gp = gm / 100.0 * fwd_rev
                    eg_vals.append(ev / fwd_gp)
                else:
                    eg_vals.append(None)

                # Revenue Growth = BEST_SALES(2BF) / BEST_SALES(1BF) - 1
                if fwd_rev is not None and nxt_rev is not None and fwd_rev != 0:
                    rg_vals.append(nxt_rev / fwd_rev - 1.0)
                else:
                    rg_vals.append(None)

                # EPS Growth = BEST_EPS(1BF) / IS_COMP_EPS_EXCL_STOCK_COMP - 1
                if fwd_eps is not None and trail_eps is not None and trail_eps != 0:
                    xg_vals.append(fwd_eps / trail_eps - 1.0)
                else:
                    xg_vals.append(None)

            er_arrays[ticker] = er_vals
            eg_arrays[ticker] = eg_vals
            rg_arrays[ticker] = rg_vals
            xg_arrays[ticker] = xg_vals

        # Assemble fm dict
        fm: dict[str, dict[str, list[float | None]]] = {}
        for ticker in short_tickers:
            fm[ticker] = {
                "er": er_arrays.get(ticker, null_arr),
                "eg": eg_arrays.get(ticker, null_arr),
                "pe": pe_arrays.get(ticker, null_arr),
                "rg": rg_arrays.get(ticker, null_arr),
                "xg": xg_arrays.get(ticker, null_arr),
                "fe": fwd_eps_arrays.get(ticker, null_arr),
            }

        result = {
            "dates": all_dates,
            "tickers": short_tickers,
            "industries": industries,
            "fm": fm,
        }

        logger.info(
            "Bloomberg fetch complete: %d dates, %d tickers, %d industries",
            len(all_dates),
            len(short_tickers),
            len(industries),
        )

        return result
