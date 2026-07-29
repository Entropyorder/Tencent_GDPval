#!/usr/bin/env python3
"""Select a reproducible, semantically diverse random subset of queries."""

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from finance_forensics.query_selection import select_diverse_queries
from finance_forensics.retrieval import DEFAULT_EMBEDDING_MODEL


def main():
    parser = argparse.ArgumentParser(
        description="Select queries with randomized farthest-point sampling."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--random-pool-size", type=int, default=5)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    args = parser.parse_args()

    manifest = select_diverse_queries(
        input_path=args.input,
        output_path=args.output,
        manifest_path=args.manifest,
        count=args.count,
        seed=args.seed,
        model_name=args.model,
        random_pool_size=args.random_pool_size,
        cache_dir=PROJECT_ROOT / ".cache" / "fastembed",
    )
    print(
        f"[selection] selected={manifest['selected_query_count']} "
        f"from={manifest['input_query_count']} output={args.output.resolve()}"
    )


if __name__ == "__main__":
    main()
