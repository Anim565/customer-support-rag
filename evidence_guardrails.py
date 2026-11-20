
"""Conservative evidence verification for the RAG prototype."""

import re
from decimal import Decimal, InvalidOperation

from evidence_features import FIELDS, present
from llm_query_extractor_v64 import validate, INTENT_FIELDS
from ranking_v4 import canonical, field_aliases


SPECIMENS = {
    "serum", "plasma", "urine", "stool",
    "saliva", "csf", "sputum", "blood"
}

QUALIFIERS = {
    "igg", "igm", "iga", "ige",
    "total", "free", "pcr", "fish",
    "qualitative", "quantitative",
    "fasting", "random", "24hour",
    "canine", "feline", "veterinary"
}


def normalized(text):
    text = str(text).lower()

    text = re.sub(
        r"\b24[\s-]*(?:hours?|hrs?|h)\b",
        "24hour",
        text
    )

    return canonical(text)


def modifiers(text, vocabulary):
    return set(normalized(text).split()) & vocabulary



def scope_signature(text):
    """
    Identify explicit investigation combinations
    in the primary test name.
    """

    text = str(text).lower()

    # Exclude parenthetical synonyms and descriptions.
    text = re.sub(r"\([^)]*\)", " ", text)

    # Standardize explicit combination markers.
    text = re.sub(
        r"\b(?:and|with|plus)\b",
        "+",
        text
    )

    parts = [
        normalized(part)
        for part in text.split("+")
        if part.strip()
    ]

    return parts


def scope_compatible(query, candidate_name):
    """
    Reject candidates containing explicit additional
    investigations that the customer did not request.
    """

    requested_parts = scope_signature(query)
    candidate_parts = scope_signature(candidate_name)

    if not requested_parts or not candidate_parts:
        return False

    # Standalone versus combined investigation.
    if len(requested_parts) != len(candidate_parts):
        return False

    # Combined investigations require matching components.
    if len(requested_parts) > 1:
        return set(requested_parts) == set(candidate_parts)

    # Standalone identity is checked separately
    # by the existing name and synonym verification.
    return True



def valid_price(value):
    try:
        price = Decimal(str(value))
        return price.is_finite() and price > 0
    except (InvalidOperation, ValueError):
        return False


def verify_evidence(
    question,
    extraction,
    candidates,
    documents
):
    """
    Returns:
        passed: boolean
        reason: diagnostic explanation
        verified: selected catalogue evidence
    """

    def reject(reason):
        return False, reason, []

    validate(extraction)

    intents = set(extraction["intent_group"])

    if not intents or not intents <= set(INTENT_FIELDS):
        return reject("Unsupported or mixed enquiry intent")

    if extraction["ambiguity_flag"]:
        return reject("Enquiry flagged as ambiguous")

    if extraction["context_dependent"]:
        return reject("Previous conversation required")

    requests = extraction["requested_tests"]

    if not requests:
        return reject("No requested tests identified")

    # A catalogue listing cannot establish live availability.
    if "AVAILABILITY" in intents:
        if re.search(
            r"\b(in stock|out of stock|reagents?|"
            r"today|currently|right now|in.house)\b",
            question,
            re.I
        ):
            return reject("Live operational availability required")

    docs_by_code = {
        str(d["code"]): d for d in documents
    }

    verified = []

    for request in requests:

        query = request["test_name"]
        fields = request["requested_fields"]
        query_norm = normalized(query)

        hits = [
            c for c in candidates
            if c["search_query"] == query
        ]

        if not hits:
            return reject(f"No evidence for {query}")

        compatible = []

        for candidate in hits:

            code = str(candidate["test_code"])
            doc = docs_by_code.get(code)

            if doc is None:
                continue

            name = str(doc["name"])

            aliases = {
                normalized(a)
                for a in field_aliases(doc)
            }

            aliases.add(normalized(name))

            # Strict identity confirmation using
            # the catalogue name or a known alias.
            if query_norm not in aliases:
                continue
            
            # Confirm investigation scope.
            if not scope_compatible(query, name):
                continue


            candidate_text = (
                name + " " +
                str(candidate.get("specimen", ""))
            )

            requested_specimens = modifiers(
                query, SPECIMENS
            )

            known_specimens = modifiers(
                candidate_text, SPECIMENS
            )

            if not requested_specimens <= known_specimens:
                continue

            requested_qualifiers = modifiers(
                query, QUALIFIERS
            )

            candidate_qualifiers = modifiers(
                candidate_text, QUALIFIERS
            )

            if not requested_qualifiers <= candidate_qualifiers:
                continue

            # Check requested fields against one
            # candidate, not across unrelated candidates.
            complete = all(
                any(
                    present(candidate.get(key))
                    for key in FIELDS[field]
                )
                for field in fields
            )

            if not complete:
                continue

            if "price" in fields:
                if not valid_price(candidate.get("price")):
                    continue

            compatible.append(candidate)

        # Multiple different matching codes remain ambiguous.
        unique = {
            str(c["test_code"]): c
            for c in compatible
        }

        if not unique:
            return reject(
                f"Unable to verify identity or evidence for {query}"
            )

        if len(unique) != 1:
            return reject(
                f"Multiple compatible catalogue tests for {query}"
            )

        chosen = next(iter(unique.values()))

        item = {
            "requested_test": query,
            "test_code": str(chosen["test_code"]),
            "test_name": chosen["test_name"],
            "requested_fields": fields,
            "evidence": {}
        }

        for field in fields:
            for key in FIELDS[field]:
                if present(chosen.get(key)):
                    item["evidence"][key] = chosen[key]

        verified.append(item)

    return True, "All requested evidence verified", verified
