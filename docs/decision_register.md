
# Research Decision Register

This document records major technical and methodological decisions, the alternatives considered and the justification for each choice.

## Decision 001 — Development Language

**Selected:** Python 3.12.10

**Alternatives:** R, JavaScript and other programming languages.

**Rationale:** Python provides an established ecosystem for data preprocessing, machine learning, semantic retrieval, model evaluation and API development.

**Status:** Implemented.

## Decision 002 — Version Control

**Selected:** Git with GitHub.

**Alternatives:** Manual file versioning and cloud-folder synchronization.

**Rationale:** Git supports traceable code changes, reproducibility, controlled experimentation and recovery of previous versions.

**Status:** Implemented.

## Decision 003 — Research Architecture

**Proposed:** Retrieval-Augmented Generation combined with supervised escalation classification.

**Alternatives:** Rule-based chatbot, standalone generative model and retrieval-only customer-support system.

**Rationale:** The proposed architecture separates organizational information retrieval, response generation and escalation decisions. This enables component-level evaluation and comparison against simpler baseline approaches.

**Status:** Proposed; requires empirical validation.

## Decision 004 — Data Acquisition

**Selected method:** Pending investigation and reproducibility testing.

**Alternatives to evaluate:** Authorized API access, browser-based extraction and conventional HTML extraction.

**Rationale:** The extraction method must be justified using the structure, accessibility, reliability and authorization requirements of the DKL catalogue.

**Status:** Pending review of previous investigations.


## Decision 005 — Catalogue Record Identity and Deduplication

**Historical implementation:** SHA-256 hashing of constructed evidence text, followed by removal of duplicate hashes.

**Identified limitation:** Identical evidence text does not necessarily establish that two records represent the same catalogue entry.

**Proposed improvement:** Preserve the raw catalogue, validate source identifiers, assess duplicate IDs and codes, and distinguish record-level duplication from content-level duplication.

**Justification:** This approach reduces the risk of excluding legitimate catalogue entries and improves data traceability.

**Status:** Proposed; pending implementation and evaluation.



## Decision 006 — Escalation Training Dataset Design

**Proposed target:** Binary classification, with 0 representing ANSWER and 1 representing ESCALATE.

**Proposed inputs:** Anonymized customer enquiries and features derived from information available at inference time.

**Alternatives:** Question-only classification, evidence-aware classification and exclusively rule-based routing.

**Rationale:** Escalation requirements may depend on both the nature of the enquiry and the sufficiency of retrieved evidence. A question-only model may therefore fail to account for missing or changing catalogue information.

**Data quality requirements:** Human-reviewed labels, anonymization, conversation-level grouping, documented annotation criteria and protection against data leakage.

**Evaluation:** Compare rule-based, supervised and hybrid approaches using class-specific precision, recall, F1-score and confusion matrices.

**Status:** Proposed; pending dataset validation and experimentation.
