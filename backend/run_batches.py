"""Run BDH data fetch in batches and merge into snapshot #1."""

import json
import sys
import time
import urllib.request

API = "http://localhost:8000/api/bloomberg/fetch-batch"
SNAPSHOT_ID = 1

with open("/tmp/ticker_batches.json") as f:
    batches = json.load(f)

total = len(batches)
for i, batch in enumerate(batches):
    label = f"Batch {i + 1}/{total}"
    print(f"\n{'='*60}")
    print(f"{label}: {len(batch)} tickers ({batch[0]}...{batch[-1]})")
    print(f"{'='*60}")
    sys.stdout.flush()

    payload = json.dumps({
        "tickers": batch,
        "snapshot_id": SNAPSHOT_ID,
    }).encode()

    req = urllib.request.Request(
        API,
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

print(f"\n{'='*60}")
print("ALL BATCHES COMPLETE")
print(f"{'='*60}")
