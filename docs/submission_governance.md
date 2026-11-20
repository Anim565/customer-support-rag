# Submission and Artifact Governance

Date: 20 November 2026

## Repository arrangement

The research project is submitted through a single public
GitHub repository in accordance with the academic
submission requirements.

The researcher confirmed authorization for public
distribution of the frozen laboratory catalogue,
derived knowledge base artifacts and trained classifier.

Underlying customer-level research datasets remain
restricted and are not included in the public repository.

## Privacy preparation

- Both research notebooks were cleared of saved outputs.
- Original executed notebooks were retained locally.
- Notebook source privacy reviews were completed.
- Fitted vocabulary privacy reviews were completed.
- Preliminary credential screening found no matching
  credential patterns across 53 inspected files.
- Restricted research datasets remain excluded from Git.

## Historical repository screening

Before public-release documentation updates, the accessible
Git history was screened using automated file-path and
credential-pattern checks.

Results:

- Historical commits: 6
- Unique historical file paths: 71
- Unique Git blobs encountered: 83
- Restricted historical file paths detected: 0
- Potential credential findings: 0

Selected binary artifacts were excluded from text-based
credential scanning.

These checks reduce disclosure risk but do not constitute
an independent or comprehensive privacy audit.

## Deployment artifact integrity

Exactly seven approved deployment artifacts are included.

Their combined size is 9,348,113 bytes.

Original SHA-256 fingerprints were verified and recorded
in docs/artifact_manifest.json.

All seven artifact fingerprints were independently
rechecked against the cloned submission repository and
the previously validated backend Docker image.

No retraining or modification of the frozen classifier
or knowledge base was performed during submission preparation.

## Excluded material

- Original customer conversations.
- Customer-level training and evaluation datasets.
- Annotation workbooks.
- LLM extraction caches.
- Local vocabulary review files.
- API credentials.
- Archived experiments.

## Deployment validation

The submitted repository was cloned into a separate
development directory for deployment verification.

Validation results included:

- Seven of seven deployment artifact checksums matched.
- Ten of ten backend source files matched after
  normalization of Windows and Linux line endings.
- Docker Compose build completed successfully using
  existing build-layer caches.
- Backend and frontend containers started successfully.
- The backend health endpoint confirmed pipeline loading.
- Dependency validation detected no broken requirements.
- CPU-only PyTorch execution was confirmed.
- All three final API smoke tests passed, covering
  grounded answering, escalation and privacy blocking.

The validation did not constitute a completely cache-free
build or deployment on an independent computer.

## Reproducibility

The repository supports deployment of the frozen research
prototype without model retraining.

Independent reproduction of training requires authorized
access to the restricted research datasets.

External API credentials, dependency installation and
embedding model availability remain necessary.

The framework is a research prototype and is not approved
for autonomous clinical or production use.
