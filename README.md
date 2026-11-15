
# Development of a Retrieval-Augmented Customer Support Framework with Intelligent Escalation

## A Diagnostic Laboratory Case Study

### Project Overview

This project investigates the development and evaluation of an AI-assisted customer support framework using Dr. Kalebi Labs (DKL) as a case study.

The proposed system combines Retrieval-Augmented Generation (RAG) with a supervised machine learning model to support customer enquiries and identify situations requiring human intervention.

### Problem Statement

Diagnostic laboratories receive customer enquiries concerning test availability, pricing, specimen requirements, turnaround times, result status and other services.

Traditional keyword-based information retrieval may fail when customer terminology differs from the terminology used in laboratory catalogues.

Furthermore, not all enquiries can be resolved using publicly available information. Some require access to internal systems, individualized clinical interpretation or operational intervention.

### Research Objectives

1. Develop a reproducible pipeline for acquiring, validating and preparing laboratory catalogue information.
2. Implement and evaluate a semantic retrieval system for customer enquiries.
3. Develop a retrieval-augmented response generation framework grounded in verified laboratory information.
4. Train and evaluate a supervised machine learning classifier for identifying enquiries requiring human escalation.
5. Evaluate the integrated framework using retrieval, classification and response-quality metrics.

### Proposed Methodology

The study will adopt an applied machine learning case-study approach.

The methodology will include:

1. Preliminary website and data-source investigation.
2. Laboratory catalogue extraction and validation.
3. Customer enquiry dataset preparation and anonymization.
4. Semantic retrieval using sentence embeddings and FAISS.
5. Retrieval-augmented response generation.
6. Supervised escalation classification and model comparison.
7. Component-level and end-to-end evaluation.
8. Prototype deployment and maintenance planning.

### Proposed Technologies

- Python
- Visual Studio Code
- Git and GitHub
- Pandas
- Sentence Transformers
- FAISS
- Scikit-learn
- XGBoost
- Large Language Model API or approved local model
- FastAPI
- Docker

Technology choices will be reviewed and justified during implementation.

### Data Protection

The project will distinguish public laboratory catalogue information from confidential operational and customer information.

Customer enquiry data will require appropriate authorization, anonymization and controlled storage.

Raw customer records, patient information and credentials must not be committed to the public repository.

### Research Reproducibility

The project will maintain documentation of:

- Data sources and extraction procedures.
- Dataset versions and preprocessing decisions.
- Model configurations and experimental parameters.
- Evaluation methods and results.
- Technical limitations and research decisions.

### Project Status

Initial development environment configured.

Historical website-investigation scripts have been identified in a separate project and will be reviewed as preliminary research evidence.

Implementation and evaluation are ongoing.
