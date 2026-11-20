
"""
Streamlit frontend for the laboratory customer support
RAG system.

All machine learning inference is performed by FastAPI.
The frontend communicates with the backend over HTTP.
"""

import os
import time

import requests
import streamlit as st


# ---------------------------------------------------------
# 1. Configuration
# ---------------------------------------------------------

API_URL = os.getenv(
    "RAG_API_URL",
    "http://127.0.0.1:8000"
).rstrip("/")

REQUEST_TIMEOUT = 180

ESCALATION_MESSAGE = (
    "Thank you for your enquiry. Our customer support "
    "team will need to review this request to provide "
    "accurate information."
)

st.set_page_config(
    page_title="DKL Laboratory Assistant",
    page_icon="🔬",
    layout="centered"
)


# ---------------------------------------------------------
# 2. Backend communication
# ---------------------------------------------------------

def check_backend():

    try:

        response = requests.get(
            f"{API_URL}/health",
            timeout=5
        )

        response.raise_for_status()

        return (
            response.json().get("pipeline_loaded")
            is True
        )

    except (requests.RequestException, ValueError):

        return False


def get_metadata():

    try:

        response = requests.get(
            f"{API_URL}/metadata",
            timeout=5
        )

        response.raise_for_status()

        return response.json()

    except (requests.RequestException, ValueError):

        return {}


def submit_enquiry(question, privacy_approved):

    start = time.perf_counter()

    try:

        response = requests.post(

            f"{API_URL}/chat",

            json={
                "question": question,
                "privacy_approved": privacy_approved
            },

            timeout=REQUEST_TIMEOUT

        )

        response.raise_for_status()

        result = response.json()

        if result.get("decision") not in {
            "ANSWER", "ESCALATE"
        }:
            raise ValueError("Invalid backend decision")

        if not isinstance(result.get("response"), str):
            raise ValueError("Invalid backend response")

        result["client_latency_seconds"] = round(
            time.perf_counter() - start,
            3
        )

        return result

    except (requests.RequestException, ValueError):

        return {

            "decision": "ESCALATE",

            "response": ESCALATION_MESSAGE,

            "service_status": "DEGRADED",

            "knowledge_base_version": "Unavailable",

            "processing_time_seconds": None,

            "client_latency_seconds": round(
                time.perf_counter() - start,
                3
            )

        }


# ---------------------------------------------------------
# 3. Session state
# ---------------------------------------------------------

if "messages" not in st.session_state:

    st.session_state.messages = []

if "results" not in st.session_state:

    st.session_state.results = []


# ---------------------------------------------------------
# 4. Sidebar
# ---------------------------------------------------------

with st.sidebar:

    st.header("System information")

    backend_ready = check_backend()

    if backend_ready:

        st.success("Backend connected")

        metadata = get_metadata()

    else:

        st.error("Backend unavailable")

        metadata = {}

    if metadata:

        st.caption("Knowledge base version")

        st.code(
            metadata.get(
                "knowledge_base_version",
                "Unavailable"
            ),
            language=None
        )

        st.write(
            "Classifier:",
            metadata.get("classifier", "Unknown")
        )

        st.write(
            "Feature set:",
            metadata.get("feature_set", "Unknown")
        )

        threshold = metadata.get(
            "decision_threshold"
        )

        if threshold is not None:

            st.write(
                "Decision threshold:",
                f"{threshold:.4f}"
            )

    st.divider()

    st.subheader("Privacy and authorization")

    privacy_approved = st.checkbox(
        "I confirm that this enquiry is synthetic "
        "or approved for external API processing.",
        value=False
    )

    st.caption(
        "Do not enter patient-identifiable or "
        "confidential clinical information."
    )

    show_diagnostics = st.checkbox(
        "Show response diagnostics",
        value=False
    )

    st.divider()

    st.subheader("Session performance")

    results = st.session_state.results

    processed = len(results)

    answered = sum(
        r["decision"] == "ANSWER"
        for r in results
    )

    escalated = sum(
        r["decision"] == "ESCALATE"
        for r in results
    )

    degraded = sum(
        r.get("service_status") == "DEGRADED"
        for r in results
    )

    coverage = (
        100 * answered / processed
        if processed else 0
    )

    col1, col2 = st.columns(2)

    col1.metric("Enquiries", processed)

    col2.metric("Answered", answered)

    col1.metric("Escalated", escalated)

    col2.metric("Coverage", f"{coverage:.1f}%")

    st.metric("Technical failures", degraded)

    if results:

        latencies = [
            r["client_latency_seconds"]
            for r in results
            if "client_latency_seconds" in r
        ]

        if latencies:

            st.metric(
                "Mean client latency",
                f"{sum(latencies) / len(latencies):.2f} s"
            )

    if st.button(
        "Clear conversation",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.session_state.results = []

        st.rerun()


# ---------------------------------------------------------
# 5. Main interface
# ---------------------------------------------------------

st.title("🔬 DKL Laboratory Assistant")

st.caption(
    "Evidence-grounded laboratory customer support"
)

st.info(
    "Research prototype for laboratory test prices, "
    "turnaround times, specimen requirements and "
    "catalogue information. Not intended for "
    "clinical decision-making."
)

if not backend_ready:

    st.warning(
        "The backend service is unavailable. "
        "Please ensure FastAPI is running."
    )

if not st.session_state.messages:

    st.markdown(
        """
        Welcome. You may ask about:

        - Laboratory test prices
        - Turnaround times
        - Specimen requirements
        - Test preparation
        - Catalogue availability
        """
    )


# ---------------------------------------------------------
# 6. Display conversation
# ---------------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.text(message["content"])

        if message["role"] == "assistant":

            result = message.get("result", {})

            if result.get("service_status") == "DEGRADED":

                st.warning(
                    "The backend encountered a "
                    "technical processing failure."
                )

            if show_diagnostics and result:

                with st.expander(
                    "Response diagnostics"
                ):

                    st.json(result)


# ---------------------------------------------------------
# 7. Receive customer enquiries
# ---------------------------------------------------------

question = st.chat_input(

    "Ask about a laboratory test...",

    max_chars=2000,

    disabled=(
        not backend_ready
        or not privacy_approved
    )

)

if question and question.strip():

    st.session_state.messages.append({

        "role": "user",

        "content": question

    })

    with st.chat_message("user"):

        st.text(question)

    with st.spinner("Processing your enquiry..."):

        result = submit_enquiry(

            question,

            privacy_approved

        )

    st.session_state.results.append(result)

    st.session_state.messages.append({

        "role": "assistant",

        "content": result["response"],

        "result": result

    })

    st.rerun()
