FROM python:3.12.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/cache/huggingface \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    TOKENIZERS_PARALLELISM=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-backend.txt .

RUN python -m pip install --no-cache-dir \
    torch==2.15.0 \
    --index-url https://download.pytorch.org/whl/cpu

RUN python -m pip install --no-cache-dir \
    -r requirements-backend.txt \
    && python -m pip check

COPY api.py .
COPY rag_pipeline.py .
COPY evidence_guardrails.py .
COPY response_generator.py .
COPY llm_query_extractor_v64.py .
COPY prepare_annotation_dataset.py .
COPY prepare_annotation_v5.py .
COPY ranking_v4.py .
COPY evidence_features.py .
COPY kb_paths.py .

COPY data/knowledge_base/current.json \
    data/knowledge_base/current.json

COPY data/knowledge_base/versions/20261116T084302Z/catalogue.csv \
    data/knowledge_base/versions/20261116T084302Z/catalogue.csv

COPY data/knowledge_base/versions/20261116T084302Z/catalogue.faiss \
    data/knowledge_base/versions/20261116T084302Z/catalogue.faiss

COPY data/knowledge_base/versions/20261116T084302Z/documents.jsonl \
    data/knowledge_base/versions/20261116T084302Z/documents.jsonl

COPY data/knowledge_base/versions/20261116T084302Z/quality_report.json \
    data/knowledge_base/versions/20261116T084302Z/quality_report.json

COPY data/private/modelling_v1/classifier.joblib \
    data/private/modelling_v1/classifier.joblib

COPY data/private/modelling_v1/policy.json \
    data/private/modelling_v1/policy.json

RUN mkdir -p /app/cache/huggingface /app/data/private

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
