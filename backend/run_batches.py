"""Run BDH data fetch in batches and merge into a snapshot.

Usage:
    python run_batches.py ticker_batches.json --snapshot-id 1
    python run_batches.py ticker_batches.json --snapshot-id 1 --api http://localhost:8000/api/bloomberg/fetch-batch
"""

import argparse
import json
import sys
import time
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch BDH data fetch and merge")
    parser.add_argument("batches_file", help="Path to JSON file with ticker batches")
    parser.add_argument(
        "--snapshot-id",
        type=int,
        required=True,
        help="Snapshot ID to merge into",
    )
    parser.add_argument(
        "--api",
        default="http://localhost:8000/api/bloomberg/fetch-batch",
        help="Batch fetch API URL (default: http://localhost:8000/api/bloomberg/fetch-batch)",
    )
    args = parser.parse_args()

    with open(args.batches_file) as f:
        batches = json.load(f)

    total = len(batches)
    for i, batch in enumerate(batches):
        label = f"Batch {i + 1}/{total}"
        print(f"\n{'=' * 60}")
        print(f"{label}: {len(batch)} tickers ({batch[0]}...{batch[-1]})")
        print(f"{'=' * 60}")
        sys.stdout.flush()

        payload = json.dumps(
            {
                "tickers": batch,
                "snapshot_id": args.snapshot_id,
            }
        ).encode()

        req = urllib.request.Request(
            args.api,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                result = json.loads(resp.read())
                elapsed = time.time() - t0
                print(
                    f"  OK in {elapsed:.0f}s — "
                    f"ticker_count={result['ticker_count']}, "
                    f"date_count={result['date_count']}, "
                    f"industry_count={result['industry_count']}"
                )
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  FAILED after {elapsed:.0f}s: {e}")

        sys.stdout.flush()

    print(f"\n{'=' * 60}")
    print("ALL BATCHES COMPLETE")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
