
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
