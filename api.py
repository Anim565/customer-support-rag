
"""
FastAPI service for the laboratory customer support
Retrieval-Augmented Generation system.

This service exposes the existing evaluated RAG pipeline
without modifying its trained classifier or decision policy.
"""

import logging
import threading

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field, StrictBool, ConfigDict

from rag_pipeline import RAGPipeline


# ---------------------------------------------------------
# 1. Application configuration
# ---------------------------------------------------------

API_VERSION = "1.0.0"

ESCALATION_MESSAGE = (
    "Thank you for your enquiry. Our customer support "
    "team will need to review this request to provide "
    "accurate information."
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# 2. Request and response schemas
# ---------------------------------------------------------

class ChatRequest(BaseModel):

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        min_length=1,
        max_length=2000,
        description="Laboratory customer support enquiry"
    )

    privacy_approved: StrictBool = Field(
        default=False,
        description=(
            "Confirmation that the enquiry is synthetic "
            "or approved for external API processing"
        )
    )


class ChatResponse(BaseModel):

    decision: Literal["ANSWER", "ESCALATE"]

    response: str

    knowledge_base_version: str

    processing_time_seconds: float

    service_status: Literal[
        "PROCESSED",
        "PRIVACY_BLOCKED",
        "DEGRADED"
    ]


# ---------------------------------------------------------
# 3. Application lifecycle
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    # Load the expensive resources only once at startup.
    app.state.pipeline = RAGPipeline()

    # Serialize pipeline access for shared resources,
    # including the SQLite extraction cache.
    app.state.pipeline_lock = threading.Lock()

    app.state.ready = True

    try:
        yield
    finally:
        app.state.ready = False


# ---------------------------------------------------------
# 4. Initialize FastAPI
# ---------------------------------------------------------

app = FastAPI(

    title="Laboratory Customer Support RAG API",

    description=(
        "Research prototype for evidence-grounded "
        "laboratory customer support enquiries. "
        "The system automatically answers supported "
        "enquiries and escalates unsupported requests."
    ),

    version=API_VERSION,

    lifespan=lifespan

)


# ---------------------------------------------------------
# 5. Root endpoint
# ---------------------------------------------------------

@app.get("/")
def root():

    return {

        "name": "Laboratory Customer Support RAG API",

        "version": API_VERSION,

        "status": "running",

        "documentation": "/docs",

        "health": "/health",

        "disclaimer": (
            "Research prototype. "
            "Not intended for clinical decision-making."
        )

    }


# ---------------------------------------------------------
# 6. Health endpoint
# ---------------------------------------------------------

@app.get("/health")
def health(request: Request):

    ready = getattr(
        request.app.state,
        "ready",
        False
    )

    if not ready:
        raise HTTPException(
            status_code=503,
            detail="Backend is not ready"
        )

    return {

        "status": "healthy",

        "pipeline_loaded": True

    }


# ---------------------------------------------------------
# 7. Metadata endpoint
# ---------------------------------------------------------

@app.get("/metadata")
def metadata(request: Request):

    pipeline = request.app.state.pipeline

    return {

        "api_version": API_VERSION,

        "knowledge_base_version": str(
            pipeline.kb_version
        ),

        "classifier": str(
            pipeline.policy.get("model", "Unknown")
        ),

        "feature_set": str(
            pipeline.policy.get("feature", "Unknown")
        ),

        "decision_threshold": float(
            pipeline.threshold
        ),

        "supported_decisions": [
            "ANSWER",
            "ESCALATE"
        ],

        "deployment_status": "Research prototype"

    }


# ---------------------------------------------------------
# 8. Main chat endpoint
# ---------------------------------------------------------

@app.post(
    "/chat",
    response_model=ChatResponse
)
def chat(payload: ChatRequest, request: Request):

    pipeline = request.app.state.pipeline

    question = payload.question.strip()

    if not question:

        raise HTTPException(
            status_code=422,
            detail="Question cannot be empty"
        )

    # Reject unauthorized processing before invoking
    # the RAG pipeline or any external inference service.

    if not payload.privacy_approved:

        return ChatResponse(

            decision="ESCALATE",

            response=(
                "This enquiry has not been approved "
                "for external processing."
            ),

            knowledge_base_version=str(
                pipeline.kb_version
            ),

            processing_time_seconds=0.0,

            service_status="PRIVACY_BLOCKED"

        )

    try:

        with request.app.state.pipeline_lock:

            result = pipeline.process(

                question,

                privacy_approved=True

            )

        reason = str(
            result.get("reason", "")
        ).lower()

        degraded = (
            "failed:" in reason
            or "ratelimiterror" in reason
            or "timeout" in reason
            or "exception" in reason
        )

        decision = result["decision"]

        if decision not in {"ANSWER", "ESCALATE"}:
            raise ValueError("Invalid pipeline decision")

        return ChatResponse(

            decision=(
                "ESCALATE" if degraded else decision
            ),

            response=(
                ESCALATION_MESSAGE
                if degraded
                else str(result["response"])
            ),

            knowledge_base_version=str(
                pipeline.kb_version
            ),

            processing_time_seconds=float(
                result.get("timings", {}).get(
                    "total_seconds", 0.0
                )
            ),

            service_status=(
                "DEGRADED"
                if degraded
                else "PROCESSED"
            )

        )

    except Exception as exc:

        # Do not expose internal exceptions, customer
        # enquiries, credentials or stack traces publicly.

        logger.error(
            "Pipeline request failed: %s",
            type(exc).__name__
        )

        return ChatResponse(

            decision="ESCALATE",

            response=ESCALATION_MESSAGE,

            knowledge_base_version=str(
                pipeline.kb_version
            ),

            processing_time_seconds=0.0,

            service_status="DEGRADED"

        )
