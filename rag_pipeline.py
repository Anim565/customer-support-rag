
"""End-to-end laboratory customer support RAG pipeline."""

import json
import math
import time
import importlib.metadata
from pathlib import Path

import joblib
import pandas as pd

from prepare_annotation_dataset import (
    load_knowledge_base,
    candidate_evidence
)

from prepare_annotation_v5 import Retriever, normalize
from llm_query_extractor_v64 import QueryExtractor
from evidence_features import make_features
from evidence_guardrails import verify_evidence

from response_generator import (
    ResponseGenerator,
    ESCALATION_MESSAGE
)


ROOT = Path(__file__).resolve().parent

MODEL_DIR = ROOT / "data/private/modelling_v1"

CATALOGUE_INTENTS = {
    "PRICE",
    "TAT",
    "SPECIMEN",
    "PREPARATION",
    "AVAILABILITY",
    "TEST_INFORMATION"
}


class RAGPipeline:

    def __init__(self):

        started = time.perf_counter()

        # Load the frozen decision policy.
        self.policy = json.loads(
            (MODEL_DIR / "policy.json").read_text(
                encoding="utf-8"
            )
        )

        # Verify package compatibility.
        for package, expected in self.policy["versions"].items():

            actual = importlib.metadata.version(package)

            if actual != expected:
                raise RuntimeError(
                    f"Package mismatch: {package}. "
                    f"Expected {expected}, found {actual}"
                )

        # Load the locally trained classifier.
        self.classifier = joblib.load(
            MODEL_DIR / "classifier.joblib"
        )

        self.threshold = float(
            self.policy["threshold"]
        )

        if self.policy["model"] != "XGB":
            raise RuntimeError(
                "Unexpected classifier configuration"
            )

        if self.policy["feature"] != "D":
            raise RuntimeError(
                "Unexpected feature configuration"
            )

        if list(self.classifier.classes_) != [0, 1]:
            raise RuntimeError(
                "Unexpected classifier class ordering"
            )

        # Load the knowledge base.
        (
            self.documents,
            self.index,
            self.embedding_model,
            self.kb_version
        ) = load_knowledge_base()

        # Prevent silent knowledge base changes.
        if str(self.kb_version) != str(
            self.policy["kb_version"]
        ):
            raise RuntimeError(
                "Knowledge base version does not "
                "match the trained model"
            )

        # Initialize existing retrieval component.
        self.retriever = Retriever(
            self.documents,
            self.index,
            self.embedding_model
        )

        # Initialize language model components.
        self.extractor = QueryExtractor()
        self.generator = ResponseGenerator()

        self.startup_seconds = round(
            time.perf_counter() - started, 3
        )

        print(
            f"RAG initialized in "
            f"{self.startup_seconds} seconds"
        )

    def retrieve_evidence(self, question, extraction):

        requests = extraction["requested_tests"]
        intents = extraction["intent_group"]

        candidates = []
        missing = []

        vet = bool(
            set(normalize(question).split())
            & {
                "vet", "veterinary", "dog",
                "cat", "canine", "feline"
            }
        )

        for request in requests:

            query = request["test_name"]

            hits = self.retriever.retrieve(
                query, vet
            )

            if not hits:
                missing.append(query)

            for rank, hit in enumerate(hits, 1):

                document, method, score = hit

                evidence = candidate_evidence(
                    query,
                    document,
                    method,
                    score,
                    rank
                )

                evidence["requested_fields"] = (
                    request["requested_fields"]
                )

                candidates.append(evidence)

        # Reproduce training-time retrieval statuses.
        status = "NOT_APPLICABLE"

        if requests:

            if not missing:
                status = "MATCH_FOUND"

            elif candidates:
                status = "PARTIAL_MATCH"

            else:
                status = "NO_MATCH"

        elif set(intents) & CATALOGUE_INTENTS:
            status = "TEST_NOT_IDENTIFIED"

        return candidates, status

    def predict(self, question, extraction, candidates, status):

        # Reproduce the feature engineering interface
        # used during training.
        row = {
            "question": question,
            "extraction_json": json.dumps(
                extraction, ensure_ascii=False
            ),
            "candidate_evidence_json": json.dumps(
                candidates, ensure_ascii=False
            ),
            "retrieval_status": status
        }

        features = make_features(
            pd.DataFrame([row])
        )

        score = float(
            self.classifier.predict_proba(features)[0, 1]
        )

        if not math.isfinite(score):
            raise ValueError("Invalid classifier score")

        if self.policy["all_escalate"]:
            decision = "ESCALATE"

        elif score >= self.threshold:
            decision = "ANSWER"

        else:
            decision = "ESCALATE"

        return decision, score

    def process(self, question, *, privacy_approved=False):

        started = time.perf_counter()

        result = {
            "decision": "ESCALATE",
            "response": ESCALATION_MESSAGE,
            "reason": "",
            "classifier_decision": None,
            "model_score": None,
            "threshold": self.threshold,
            "knowledge_base_version": self.kb_version,
            "extraction": None,
            "retrieval_status": None,
            "candidates": [],
            "verified_evidence": [],
            "guardrail_passed": None,
            "generation": None,
            "timings": {}
        }

        def finish(reason):

            result["reason"] = reason

            result["timings"]["total_seconds"] = round(
                time.perf_counter() - started, 3
            )

            return result

        if privacy_approved is not True:
            return finish("Privacy approval required")

        if not isinstance(question, str):
            return finish("Invalid enquiry")

        question = question.strip()

        if not question:
            return finish("Empty enquiry")

        if len(question) > 2000:
            return finish("Enquiry exceeds input limit")

        stage = "extraction"

        try:

            # Stage 1: LLM query extraction.
            tick = time.perf_counter()

            extraction = self.extractor.extract(
                question,
                privacy_approved=True
            )

            result["extraction"] = extraction

            result["timings"]["extraction_seconds"] = round(
                time.perf_counter() - tick, 3
            )

            # Stage 2: Hybrid retrieval.
            stage = "retrieval"
            tick = time.perf_counter()

            candidates, status = self.retrieve_evidence(
                question, extraction
            )

            result["candidates"] = candidates
            result["retrieval_status"] = status

            result["timings"]["retrieval_seconds"] = round(
                time.perf_counter() - tick, 3
            )

            # Stage 3: Feature engineering and classification.
            stage = "classification"
            tick = time.perf_counter()

            decision, score = self.predict(
                question,
                extraction,
                candidates,
                status
            )

            result["classifier_decision"] = decision
            result["model_score"] = score

            result["timings"]["classification_seconds"] = round(
                time.perf_counter() - tick, 3
            )

            if decision == "ESCALATE":
                return finish(
                    "Classifier selected escalation"
                )

            # Stage 4: Evidence verification.
            stage = "evidence_verification"
            tick = time.perf_counter()

            passed, reason, verified = verify_evidence(
                question,
                extraction,
                candidates,
                self.documents
            )

            result["guardrail_passed"] = passed
            result["verified_evidence"] = verified

            result["timings"]["verification_seconds"] = round(
                time.perf_counter() - tick, 3
            )

            if not passed:
                return finish(
                    f"Evidence verification: {reason}"
                )

            # Stage 5: LLM response generation and validation.
            stage = "generation"
            tick = time.perf_counter()

            generated = self.generator.generate(
                question,
                verified,
                privacy_approved=True
            )

            result["generation"] = generated

            result["timings"]["generation_seconds"] = round(
                time.perf_counter() - tick, 3
            )

            if generated["decision"] != "ANSWER":
                return finish(generated["reason"])

            # Every stage has passed.
            result["decision"] = "ANSWER"
            result["response"] = generated["response"]

            return finish(
                "Classifier, evidence verification "
                "and response validation passed"
            )

        except Exception as exc:

            # Fail safely instead of exposing
            # internal errors to the customer.
            return finish(
                f"{stage} failed: {type(exc).__name__}"
            )


if __name__ == "__main__":

    pipeline = RAGPipeline()

    print("\nLaboratory RAG research prototype")
    print("Use synthetic or approved de-identified enquiries.")
    print("Type exit to stop.\n")

    while True:

        question = input("Enquiry: ").strip()

        if question.lower() in {"exit", "quit"}:
            break

        approved = input(
            "Approved for external processing? (yes/no): "
        ).strip().lower() == "yes"

        result = pipeline.process(
            question,
            privacy_approved=approved
        )

        print("\nDecision:", result["decision"])
        print("Classifier:", result["classifier_decision"])
        print("Score:", result["model_score"])
        print("Reason:", result["reason"])
        print("Response draft:")
        print(result["response"])
        print("Timings:", result["timings"])
        print()
