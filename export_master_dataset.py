"""Export the master labelled dataset before final partitioning."""

import argparse
from pathlib import Path
import pandas as pd


def export_master(source, output):
    df = pd.read_csv(
        source,
        keep_default_na=False,
        dtype={"record_id": str, "group_id": str}
    )

    print("Original shape:", df.shape)

    df = df.drop(
        columns=["partition", "original_partition"]
    )

    assert df.record_id.is_unique
    assert df.group_id.str.strip().ne("").all()
    assert "partition" not in df.columns
    assert "original_partition" not in df.columns

    output.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        output,
        index=False,
        encoding="utf-8-sig"
    )

    print("New shape:", df.shape)
    print("\nClass distribution:")
    print(df.decision_label.value_counts())
    print("\nSource distribution:")
    print(df.source_type.value_counts())
    print("\nSaved to:", output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        required=True
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

    export_master(args.input, args.output)
