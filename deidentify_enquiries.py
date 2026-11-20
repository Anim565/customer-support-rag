
import re
from pathlib import Path

import pandas as pd

INPUT = Path("data/raw/DKL_Combined_Enquiries.xlsx")
OUTPUT = Path("data/private/privacy_review.xlsx")

PATTERNS = [
    (
        "URL",
        r"https?://[^\s]+|www\.[^\s]+",
        "[LINK]"
    ),
    (
        "EMAIL",
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL]"
    ),
    (
        "PHONE",
        r"(?<!\w)(?:\+254|254|0)[\s-]?[17](?:[\s-]?\d){8}(?!\d)",
        "[PHONE]"
    ),
    (
        "CASE_ID",
        r"\b(?:case|accession|patient|invoice|bill)"
        r"\s*(?:id|number|no\.?|#)?\s*[:#-]?\s*"
        r"(?=[A-Za-z0-9/-]*\d)[A-Za-z0-9/-]{4,}\b",
        "[CASE_REFERENCE]"
    ),
    (
        "LONG_NUMBER",
        r"\b\d{7,}\b",
        "[IDENTIFIER]"
    ),
    (
        "DATE",
        r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b",
        "[DATE]"
    ),
]

REVIEW_PATTERN = re.compile(
    r"\b(patient|name|mr|mrs|miss|dr|"
    r"case|accession|report|result|invoice|bill|"
    r"gender|dob|born|male|female)\b",
    re.IGNORECASE
)

def redact(text):
    cleaned = text
    detected = []

    for category, pattern, replacement in PATTERNS:
        cleaned, count = re.subn(
            pattern,
            replacement,
            cleaned,
            flags=re.IGNORECASE
        )
        if count:
            detected.append(category)

    if REVIEW_PATTERN.search(cleaned):
        detected.append("POSSIBLE_PERSONAL_CONTEXT")

    return cleaned, ";".join(detected)


def main():
    df = pd.read_excel(INPUT)

    rows = []

    for i, row in df.iterrows():
        question = str(row["question"])

        cleaned, flags = redact(question)

        rows.append({
            "record_id": i + 1,
            "source_type": row["source_type"],
            "original_question": question,
            "deidentified_question": cleaned,
            "privacy_flags": flags,
            "privacy_approved": ""
        })

    result = pd.DataFrame(rows)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with pd.ExcelWriter(
        OUTPUT,
        engine="openpyxl"
    ) as writer:

        result.to_excel(
            writer,
            sheet_name="Privacy Review",
            index=False
        )

        ws = writer.book["Privacy Review"]
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions

        widths = [12, 15, 85, 85, 40, 20]

        for col, width in zip("ABCDEF", widths):
            ws.column_dimensions[col].width = width

        from openpyxl.styles import Alignment
        from openpyxl.worksheet.datavalidation import DataValidation

        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.data_type = "s"

                cell.alignment = Alignment(
                    wrap_text=True,
                    vertical="top"
                )

        validation = DataValidation(
            type="list",
            formula1='"YES,NO"',
            allow_blank=True
        )

        ws.add_data_validation(validation)
        validation.add(f"F2:F{ws.max_row}")

    print("Total enquiries:", len(result))
    print(
        "Automatically flagged:",
        result["privacy_flags"].ne("").sum()
    )
    print("Output:", OUTPUT)
    print("Manual privacy approval required.")
    print("No data sent to any external API.")


if __name__ == "__main__":
    main()
