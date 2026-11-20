"""Combine synthetic enquiry and hard-negative evidence audits."""

import argparse
from pathlib import Path
import pandas as pd


def merge_audits(synthetic, hard_negatives, output):
    a = pd.read_csv(synthetic)
    b = pd.read_csv(hard_negatives)

    combined = pd.concat(
        [a, b],
        ignore_index=True,
        sort=False
    )

    assert len(combined) == len(a) + len(b)

    output.parent.mkdir(parents=True, exist_ok=True)

    combined.to_csv(output, index=False)

    print("Synthetic records:", len(a))
    print("Hard-negative records:", len(b))
    print("Combined records:", len(combined))
    print("Saved to:", output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--synthetic",
        type=Path,
        default=Path(
            "data/processed/synthetic_v4_evidence_audit.csv"
        )
    )

    parser.add_argument(
        "--hard-negatives",
        type=Path,
        default=Path(
            "data/processed/hard_negatives_v4_audit.csv"
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True
    )

    args = parser.parse_args()

    if args.output.exists():
        raise FileExistsError(
            f"Output already exists: {args.output}"
        )

    merge_audits(
        args.synthetic,
        args.hard_negatives,
        args.output
    )
