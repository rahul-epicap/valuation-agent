"""Spot check: validate BDS INDX_MWEIGHT_HIST calls on Bloomberg Terminal.

Run on a machine with Bloomberg Terminal active:
    cd backend && python test_bds_spot.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blp import blp

bq = blp.BlpQuery().start()

# --- SPX Index ---
print("=== SPX Index  - INDX_MWEIGHT_HIST (2024-01-01) ===\n")
df_spx = bq.bds(
    security="SPX Index",
    field="INDX_MWEIGHT_HIST",
    overrides=[("END_DATE_OVERRIDE", "20240101")],
)
print(f"Columns: {list(df_spx.columns)}")
print(f"Shape: {df_spx.shape}")
print(f"\nFirst 10 rows:\n{df_spx.head(10).to_string()}")
print(f"\nTicker count: {len(df_spx)}")

# Validate ~500 constituents for S&P 500
assert len(df_spx) >= 400, f"Expected ~500 SPX constituents, got {len(df_spx)}"
print(f"  OK SPX constituent count looks reasonable ({len(df_spx)})")

# --- NDX Index ---
print("\n\n=== NDX Index  - INDX_MWEIGHT_HIST (2024-01-01) ===\n")
df_ndx = bq.bds(
    security="NDX Index",
    field="INDX_MWEIGHT_HIST",
    overrides=[("END_DATE_OVERRIDE", "20240101")],
)
print(f"Columns: {list(df_ndx.columns)}")
print(f"Shape: {df_ndx.shape}")
print(f"\nFirst 10 rows:\n{df_ndx.head(10).to_string()}")
print(f"\nTicker count: {len(df_ndx)}")

# Validate ~100 constituents for Nasdaq 100
assert len(df_ndx) >= 80, f"Expected ~100 NDX constituents, got {len(df_ndx)}"
print(f"  OK NDX constituent count looks reasonable ({len(df_ndx)})")

# --- Check column names for ticker extraction ---
print("\n\n=== Column Analysis ===\n")
for name, df in [("SPX", df_spx), ("NDX", df_ndx)]:
    print(f"{name} columns: {list(df.columns)}")
    for col in df.columns:
        sample = df[col].iloc[0] if len(df) > 0 else None
        print(f"  {col}: type={type(sample).__name__}, sample={sample}")

# --- Test an older date (2010) ---
print("\n\n=== SPX Index  - INDX_MWEIGHT_HIST (2010-01-01) ===\n")
df_old = bq.bds(
    security="SPX Index",
    field="INDX_MWEIGHT_HIST",
    overrides=[("END_DATE_OVERRIDE", "20100101")],
)
print(f"Shape: {df_old.shape}")
print(f"Ticker count: {len(df_old)}")
print(f"  OK 2010 data available: {len(df_old)} constituents")

bq.stop()
print("\n\nAll checks passed!")
