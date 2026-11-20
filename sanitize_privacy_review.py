"""Export privacy-approved enquiries for research analysis."""

import argparse
from pathlib import Path
import pandas as pd


def sanitize(source, output):
    df = pd.read_excel(
        source,
        sheet_name="Privacy Review",
        keep_default_na=False
    )

    approved = df[
        df["privacy_approved"]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("YES")
        & df["deidentified_question"]
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    columns = [
        "record_id",
        "source_type",
        "deidentified_question",
        "privacy_flags",
        "privacy_approved"
    ]

    sanitized = approved[columns].copy()

    assert "original_question" not in sanitized.columns

    output.parent.mkdir(parents=True, exist_ok=True)

    sanitized.to_excel(
        output,
        sheet_name="Privacy Review",
        index=False
    )

    print("Original records:", len(df))
    print("Sanitized records:", len(sanitized))
    print("Excluded records:", len(df) - len(sanitized))
    print("\nSource distribution:")
    print(sanitized["source_type"].value_counts())
    print("\nRetained columns:")
    print(sanitized.columns.tolist())
    print("\nSaved to:", output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/private/privacy_review.xlsx")
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

    sanitize(args.input, args.output)
