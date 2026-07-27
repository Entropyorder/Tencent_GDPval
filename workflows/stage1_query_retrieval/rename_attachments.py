#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from finance_forensics.attachment_naming import rename_retrieved_attachments


def main():
    parser = argparse.ArgumentParser(
        description="Rename retrieved attachments using document_catalog.json."
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=PROJECT_ROOT / "output" / "catalog" / "document_catalog.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "output" / "retrieval",
    )
    args = parser.parse_args()

    result = rename_retrieved_attachments(args.catalog, args.output_dir)
    print(
        f"done total={result['total']} renamed={result['renamed']} "
        f"unchanged={result['unchanged']} output={args.output_dir.resolve()}"
    )


if __name__ == "__main__":
    main()
