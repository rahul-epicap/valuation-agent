"""Batch historical index membership loader.

Reads indices.json, splits into configurable batches, and POSTs each batch
to /api/indices/refresh-batch with current_only=false for full historical
membership data.

Usage:
    python run_index_batches.py --batch-size 5 --start-year 2010
    python run_index_batches.py --batch-size 2 --indices SPX,NDX
    python run_index_batches.py --batch-size 5 --skip 3   # resume from batch 4
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

INDICES_PATH = Path(__file__).resolve().parent / "indices.json"


def load_indices(subset: list[str] | None = None) -> list[str]:
    """Load index short_names from indices.json, optionally filtering."""
    with open(INDICES_PATH) as f:
        all_indices = json.load(f)

    short_names = [idx["short_name"] for idx in all_indices]

    if subset:
        subset_set = set(subset)
        unknown = subset_set - set(short_names)
        if unknown:
            print(
                f"WARNING: Unknown indices (not in indices.json): {', '.join(sorted(unknown))}"
            )
        short_names = [sn for sn in short_names if sn in subset_set]

    return short_names


def make_batches(items: list[str], size: int) -> list[list[str]]:
    """Split a list into chunks of the given size."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch historical index membership loader"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of indices per batch (default: 5)",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2010,
        help="Start year for historical depth (default: 2010)",
    )
    parser.add_argument(
        "--api",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--indices",
        default=None,
        help="Comma-separated short_names to process a subset (e.g. SPX,NDX,MSXXTECH)",
    )
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="Number of batches to skip (for resuming after failure)",
    )
    args = parser.parse_args()

    subset = [s.strip() for s in args.indices.split(",")] if args.indices else None
    short_names = load_indices(subset)

    if not short_names:
        print("ERROR: No indices to process.")
        sys.exit(1)

    batches = make_batches(short_names, args.batch_size)
    total_batches = len(batches)
    total_indices = len(short_names)
    url = f"{args.api.rstrip('/')}/api/indices/refresh-batch"

    print(
        f"Loaded {total_indices} indices -> {total_batches} batches of <={args.batch_size}"
    )
    print(f"Historical depth: {args.start_year}-present")
    print(f"Endpoint: {url}")
    if args.skip:
        print(f"Skipping first {args.skip} batches")
    print()

    grand_total = 0
    indices_done = args.skip * args.batch_size  # approximate for skipped

    for i, batch in enumerate(batches):
        if i < args.skip:
            continue

        label = f"Batch {i + 1}/{total_batches}"
        names_str = ", ".join(batch)
        print(f"{'=' * 60}")
        print(f"{label} -- {names_str}")
        print(f"{'=' * 60}")
        sys.stdout.flush()

        payload = json.dumps(
            {
                "short_names": batch,
                "current_only": False,
                "start_year": args.start_year,
            }
        ).encode()

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                result = json.loads(resp.read())
                elapsed = time.time() - t0

                batch_total = 0
                memberships = result.get("memberships_added", {})
                for sn in batch:
                    count = memberships.get(sn, 0)
                    status = (
                        f"{count:,} memberships"
                        if count >= 0
                        else "SKIPPED (not in DB)"
                    )
                    print(f"  {sn}: {status}")
                    if count > 0:
                        batch_total += count

                grand_total += batch_total
                indices_done += len(batch)
                print(
                    f"  OK in {elapsed:.0f}s -- {batch_total:,} new memberships this batch"
                )
                print(
                    f"  Progress: {indices_done}/{total_indices} indices done, {grand_total:,} total memberships"
                )

        except Exception as e:
            elapsed = time.time() - t0
            indices_done += len(batch)
            print(f"  FAILED after {elapsed:.0f}s: {e}")
            print(f"  Continuing to next batch... (resume with --skip {i + 1})")

        print()
        sys.stdout.flush()

    print(f"{'=' * 60}")
    print(f"ALL BATCHES COMPLETE -- {grand_total:,} total memberships added")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
