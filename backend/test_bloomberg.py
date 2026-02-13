"""
Standalone Bloomberg integration test.

Run from the backend directory:
    python test_bloomberg.py

Tests in order:
  1. tickers.json loads correctly
  2. BloombergService initializes
  3. Bloomberg session connects
  4. BDP query (INDUSTRY_SECTOR for 3 tickers)
  5. BDH query (CURR_ENTP_VAL for 3 tickers, 3 months)
  6. BDH query with override (BEST_SALES + 1BF for 3 tickers, 3 months)
  7. Full fetch_all() with a tiny date range to validate schema
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

PASS = "[PASS]"
FAIL = "[FAIL]"
SKIP = "[SKIP]"

EXPECTED_METRIC_KEYS = {"er", "eg", "pe", "rg", "xg", "fe"}
SAMPLE_TICKERS = ["ADBE US Equity", "CRM US Equity", "MSFT US Equity"]


def test_tickers_json() -> bool:
    """Test 1: tickers.json loads and has expected shape."""
    print("\n--- Test 1: tickers.json ---")
    tickers_path = Path(__file__).resolve().parent / "tickers.json"
    try:
        with open(tickers_path) as f:
            tickers = json.load(f)
        assert isinstance(tickers, list), "Expected a JSON array"
        assert len(tickers) > 200, f"Expected 200+ tickers, got {len(tickers)}"
        assert all(isinstance(t, str) and t.endswith(" US Equity") for t in tickers), (
            "All tickers should end with ' US Equity'"
        )
        print(f"  {PASS} Loaded {len(tickers)} tickers")
        print(f"  First 5: {tickers[:5]}")
        return True
    except Exception as e:
        print(f"  {FAIL} {e}")
        return False


def test_service_init() -> bool:
    """Test 2: BloombergService initializes and loads tickers."""
    print("\n--- Test 2: BloombergService init ---")
    try:
        from app.services.bloomberg_service import BloombergService

        svc = BloombergService()
        assert len(svc.tickers) > 200
        print(f"  {PASS} Service created, {len(svc.tickers)} tickers loaded")
        return True
    except Exception as e:
        print(f"  {FAIL} {e}")
        return False


def test_session_connect():
    """Test 3: Bloomberg session connects."""
    print("\n--- Test 3: Bloomberg session connect ---")
    try:
        from app.services.bloomberg_service import BloombergService

        svc = BloombergService()
        svc.start()
        print(f"  {PASS} Bloomberg session started successfully")
        return svc
    except Exception as e:
        print(f"  {FAIL} {e}")
        print("  Make sure Bloomberg Terminal is running and logged in.")
        return None


async def test_bdp_query(svc) -> bool:
    """Test 4: BDP query for INDUSTRY_SECTOR."""
    print("\n--- Test 4: BDP query (INDUSTRY_SECTOR) ---")
    try:
        df = await asyncio.to_thread(svc._bdp_sync, SAMPLE_TICKERS, ["INDUSTRY_SECTOR"])
        print("  Raw DataFrame:")
        print(f"    shape: {df.shape}")
        print(f"    columns: {list(df.columns)}")
        print(f"    index name: {df.index.name}")
        print(f"    dtypes:\n{df.dtypes}")
        df_reset = df.reset_index()
        print("  After reset_index:")
        print(f"    columns: {list(df_reset.columns)}")
        print(f"    data:\n{df_reset.to_string(index=False)}")
        assert not df.empty, "Expected non-empty result"
        print(f"  {PASS} BDP query returned {len(df)} rows")
        return True
    except Exception as e:
        print(f"  {FAIL} {e}")
        return False


async def test_bdh_query(svc) -> bool:
    """Test 5: BDH query for CURR_ENTP_VAL (no overrides)."""
    print("\n--- Test 5: BDH query (CURR_ENTP_VAL, 3 months) ---")
    try:
        df = await asyncio.to_thread(
            svc._bdh_sync,
            SAMPLE_TICKERS,
            "CURR_ENTP_VAL",
            "2025-10-01",
            "2026-01-01",
            None,
        )
        print("  Raw DataFrame:")
        print(f"    shape: {df.shape}")
        print(f"    columns: {list(df.columns)}")
        print(f"    index name: {df.index.name}")
        if hasattr(df.columns, "names"):
            print(f"    column names: {df.columns.names}")
        print(f"    dtypes:\n{df.dtypes}")
        df_reset = df.reset_index()
        print("  After reset_index:")
        print(f"    columns: {list(df_reset.columns)}")
        print(f"    sample rows:\n{df_reset.head(10).to_string(index=False)}")

        # Test our parser
        from app.services.bloomberg_service import BloombergService as BS

        parsed = BS._parse_bdh_dataframe(df, "CURR_ENTP_VAL")
        print(f"  Parsed result: {len(parsed)} tickers")
        for ticker, date_vals in parsed.items():
            print(f"    {ticker}: {dict(list(date_vals.items())[:3])}...")

        assert not df.empty, "Expected non-empty result"
        assert len(parsed) > 0, "Parser returned no tickers"
        print(
            f"  {PASS} BDH query returned {len(df)} rows, parsed {len(parsed)} tickers"
        )
        return True
    except Exception as e:
        print(f"  {FAIL} {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_bdh_override_query(svc) -> bool:
    """Test 6: BDH query with BEST_FPERIOD_OVERRIDE."""
    print("\n--- Test 6: BDH query (BEST_SALES + 1BF override, 3 months) ---")
    try:
        df = await asyncio.to_thread(
            svc._bdh_sync,
            SAMPLE_TICKERS,
            "BEST_SALES",
            "2025-10-01",
            "2026-01-01",
            [("BEST_FPERIOD_OVERRIDE", "1BF")],
        )
        print("  Raw DataFrame:")
        print(f"    shape: {df.shape}")
        print(f"    columns: {list(df.columns)}")
        df_reset = df.reset_index()
        print("  After reset_index:")
        print(f"    columns: {list(df_reset.columns)}")
        print(f"    sample rows:\n{df_reset.head(10).to_string(index=False)}")

        from app.services.bloomberg_service import BloombergService as BS

        parsed = BS._parse_bdh_dataframe(df, "BEST_SALES")
        print(f"  Parsed result: {len(parsed)} tickers")
        for ticker, date_vals in parsed.items():
            print(f"    {ticker}: {dict(list(date_vals.items())[:3])}...")

        assert not df.empty, "Expected non-empty result"
        print(f"  {PASS} BDH override query works")
        return True
    except Exception as e:
        print(f"  {FAIL} {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_fetch_all_mini(svc) -> bool:
    """Test 7: Full fetch_all() with a 1-month range to validate schema."""
    print("\n--- Test 7: fetch_all() mini test (1 month, 3 tickers) ---")

    original_tickers = svc._tickers
    svc._tickers = SAMPLE_TICKERS

    try:
        result = await svc.fetch_all(
            start_date="2025-12-01",
            end_date="2026-01-01",
        )

        # Validate top-level keys
        assert "dates" in result, "Missing 'dates' key"
        assert "tickers" in result, "Missing 'tickers' key"
        assert "industries" in result, "Missing 'industries' key"
        assert "fm" in result, "Missing 'fm' key"

        dates = result["dates"]
        tickers = result["tickers"]
        industries = result["industries"]
        fm = result["fm"]

        print(f"  dates: {dates}")
        print(f"  tickers: {tickers}")
        print(f"  industries: {industries}")
        print(f"  fm keys: {list(fm.keys())}")

        assert isinstance(dates, list), "dates should be a list"
        assert len(dates) >= 1, f"Expected at least 1 date, got {len(dates)}"
        assert isinstance(tickers, list), "tickers should be a list"
        assert len(tickers) >= 1, f"Expected at least 1 ticker, got {len(tickers)}"

        # Verify industries have short ticker keys (not numeric)
        for k in industries:
            assert not k.isdigit(), (
                f"Industry key '{k}' looks like a numeric index, not a ticker"
            )

        # Check that fm has expected structure
        for ticker in tickers:
            assert ticker in fm, f"Ticker '{ticker}' missing from fm"
            metrics = fm[ticker]
            assert set(metrics.keys()) == EXPECTED_METRIC_KEYS, (
                f"Ticker '{ticker}' has keys {set(metrics.keys())}, "
                f"expected {EXPECTED_METRIC_KEYS}"
            )
            for key in EXPECTED_METRIC_KEYS:
                arr = metrics[key]
                assert isinstance(arr, list), f"{ticker}.{key} should be a list"
                assert len(arr) == len(dates), (
                    f"{ticker}.{key} has {len(arr)} values but there are {len(dates)} dates"
                )

        # Print sample values for one ticker
        sample = tickers[0]
        print(f"\n  Sample data for {sample}:")
        for key in sorted(EXPECTED_METRIC_KEYS):
            vals = fm[sample][key]
            print(f"    {key}: {vals}")

        # Count non-null values
        total = 0
        non_null = 0
        for t in tickers:
            for k in EXPECTED_METRIC_KEYS:
                for v in fm[t][k]:
                    total += 1
                    if v is not None:
                        non_null += 1
        pct = (non_null / total * 100) if total > 0 else 0
        print(f"\n  Data density: {non_null}/{total} values non-null ({pct:.1f}%)")

        print(f"  {PASS} Schema validated successfully")
        return True

    except Exception as e:
        print(f"  {FAIL} {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        svc._tickers = original_tickers


async def run_live_tests(svc):
    """Run tests that need a live Bloomberg connection."""
    results = {}
    results["bdp_query"] = await test_bdp_query(svc)
    results["bdh_query"] = await test_bdh_query(svc)
    results["bdh_override"] = await test_bdh_override_query(svc)
    results["fetch_all_mini"] = await test_fetch_all_mini(svc)
    return results


def main():
    print("=" * 60)
    print("Bloomberg Integration Test (BDH-based)")
    print("=" * 60)

    results = {}

    # Test 1: tickers.json
    results["tickers_json"] = test_tickers_json()

    # Test 2: Service init
    results["service_init"] = test_service_init()

    # Test 3: Bloomberg session
    svc = test_session_connect()
    results["session_connect"] = svc is not None

    if svc is None:
        print(f"\n  {SKIP} Skipping live Bloomberg tests (no session)")
        results["bdp_query"] = None
        results["bdh_query"] = None
        results["bdh_override"] = None
        results["fetch_all_mini"] = None
    else:
        try:
            live_results = asyncio.run(run_live_tests(svc))
            results.update(live_results)
        finally:
            svc.stop()
            print("\n  Bloomberg session stopped.")

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        if passed is None:
            status = SKIP
        elif passed:
            status = PASS
        else:
            status = FAIL
        print(f"  {status} {name}")

    failed = sum(1 for v in results.values() if v is False)
    if failed:
        print(f"\n{failed} test(s) FAILED")
        sys.exit(1)
    else:
        print("\nAll tests passed (or skipped)!")
        sys.exit(0)


if __name__ == "__main__":
    main()
