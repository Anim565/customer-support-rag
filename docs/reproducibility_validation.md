# Data Preparation Reproducibility Validation

Validation date: 20 November 2026

## Objective

To verify that formalized data preparation scripts reproduce
intermediate research datasets previously generated through
interactive Python commands.

## Environment

- Python 3.12.10
- Windows
- Project virtual environment
- Dependencies recorded in requirements-research-lock.txt

## Validation method

The original research artifacts were preserved. Each script
generated a separate output in a restricted validation directory.

Original and regenerated datasets were loaded into pandas and
compared using pandas.testing.assert_frame_equal.

## Results

| Artifact | Rows | Columns | Result |
|---|---:|---:|---|
| Privacy review sanitized dataset | 2611 | 5 | Identical |
| Master annotated dataset | 1217 | 24 | Identical |
| Combined synthetic evidence audit | 3500 | 28 | Identical |

## Scripts validated

- sanitize_privacy_review.py
- export_master_dataset.py
- merge_synthetic_audits.py

All three scripts passed syntax validation and execution.

## Additional software validation

Following repository cleanup:

- 33 existing Python scripts passed syntax validation.
- All core application imports passed.
- All 16 existing unit tests passed.
- Three additional data preparation scripts passed validation.

## Scope and limitations

The validation establishes reproducibility of the three
intermediate transformations from their existing source artifacts.

It does not establish complete end-to-end reproducibility
from the original historical messages.

The original combined enquiry workbook creation, initial
synthetic enquiry generation and original annotation batch
consolidation have not been fully reconstructed as executable
procedures.

Human privacy review and evidence annotation remain required
components of the research methodology.

No original datasets, trained models or frozen evaluation
results were modified during this validation.

## Knowledge base portability validation

Validation date: 20 November 2026

The research scripts integrate_v4_evidence.py and
evaluate_holdout.py were updated to use the shared
active_kb_folder function in kb_paths.py.

Validation confirmed:

- Both scripts passed syntax validation.
- Both scripts resolved knowledge base version 20261116T084302Z.
- Both scripts loaded identical sets of 2143 documents.
- Both scripts successfully loaded a relocated knowledge base.
- Resolution succeeded despite an intentionally invalid
  original path in the temporary manifest.
- The original knowledge base remained unchanged.

The change affected path resolution only. Retrieval algorithms,
model parameters and frozen experimental results were unchanged.
The test establishes knowledge base resolution portability,
not complete cross-platform reproducibility of the research.
