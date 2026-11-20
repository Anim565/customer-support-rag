
import argparse
import json
import re
from pathlib import Path
from functools import lru_cache
from collections import Counter, defaultdict

import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

from kb_paths import active_kb_folder
from ranking_v4 import rank_lexical, canonical, field_aliases


# =========================================================
# 1. CONFIGURATION
# =========================================================

INPUT_FILE = Path(
    "data/raw/DKL_Combined_Enquiries.xlsx"
)

OUTPUT_DIR = Path(
    "data/processed/annotation_v1"
)

KB_ROOT = "data/knowledge_base"

TOP_K = 5
SEMANTIC_THRESHOLD = 0.35
BATCH_SIZE = 32


# =========================================================
# 2. INTENT GROUPING
# =========================================================

INTENT_PATTERNS = {
    "PRICE": [
        r"\bprice\b",
        r"\bcost\b",
        r"\bcharges?\b",
        r"\bpricing\b",
        r"\bquotation\b",
        r"\bquote\b",
        r"\bhow much\b",
        r"\bfees?\b",
        r"\brates?\b",
        r"\bbei\b",
        r"\bngapi\b",
        r"\bpesa\b",
        r"\bmnacharge\b",
        r"\bbei gani\b",
    ],

    "TAT": [
        r"\btat\b",
        r"\bturnaround\b",
        r"\bhow long\b",
        r"\bhow soon\b",
        r"\bhow many (hours|days|weeks)\b",
        r"\bwhen.*results?\b",
        r"\bresults?.*when\b",
        r"\bresults?.*ready\b",
        r"\bsame.day\b",
        r"\btime frame\b",
        r"\bhow fast\b",
        r"\bmuda\b",
        r"\bsiku ngapi\b",
        r"\bmasaa mangapi\b",
        r"\byatatoka lini\b",
        r"\bzinatoka lini\b",
        r"\bitachukua muda gani\b",
    ],

    "SPECIMEN": [
        r"\bspecimens?\b",
        r"\bsamples?\b",
        r"\btubes?\b",
        r"\bcontainers?\b",
        r"\bvolume\b",
        r"\bhow many ml\b",
        r"\bhow much blood\b",
        r"\bcollected in\b",
        r"\btransport medium\b",
        r"\bstability\b",
        r"\bedta\b",
        r"\bserum\b",
        r"\bplasma\b",
        r"\bsampuli\b",
        r"\bdamu kiasi gani\b",
        r"\bchupa gani\b",
    ],

    "PREPARATION": [
        r"\bfasting\b",
        r"\bfast\b",
        r"\bpreparation\b",
        r"\bprepare\b",
        r"\bprecautions?\b",
        r"\bcan i eat\b",
        r"\bcan i drink\b",
        r"\bbefore eating\b",
        r"\bempty stomach\b",
        r"\bbefore breakfast\b",
        r"\bshould i stop\b",
        r"\bkusubiri bila kula\b",
        r"\bbila kula\b",
        r"\bkufunga\b",
        r"\bnifunge\b",
        r"\bnisikule\b",
        r"\bnile\b",
    ],

    "AVAILABILITY": [
        r"\bdo you (do|offer|perform|run|provide|have)\b",
        r"\bis.*available\b",
        r"\bavailability\b",
        r"\bcan you (do|run|perform)\b",
        r"\bin stock\b",
        r"\bin.house\b",
        r"\bmnayo\b",
        r"\bmnafanya\b",
        r"\bmnatoa\b",
        r"\binapatikana\b",
        r"\biko available\b",
    ],

    "TEST_INFORMATION": [
        r"\bwhat is\b",
        r"\bwhat does.*test\b",
        r"\bwhat does.*include\b",
        r"\bwhat does.*measure\b",
        r"\bwhat is included\b",
        r"\bparameters\b",
        r"\bcomponents\b",
        r"\btests included\b",
        r"\bdifference between\b",
        r"\bwhat is the difference\b",
        r"\bni nini\b",
        r"\binahusisha nini\b",
    ],

    "CLINICAL": [
        r"\bwhat does.*mean\b",
        r"\binterpret\b",
        r"\binterpretation\b",
        r"\bdiagnos\w*\b",
        r"\bwhat medication\b",
        r"\bwhich medicine\b",
        r"\bwhat medicine\b",
        r"\bwhat treatment\b",
        r"\bshould i take\b",
        r"\bshould i change\b",
        r"\bwhat test should i\b",
        r"\bwhich test should i\b",
        r"\bwhat test.*recommend\b",
        r"\bwhich test.*recommend\b",
        r"\bis it normal\b",
        r"\bis this normal\b",
        r"\bis it dangerous\b",
        r"\bwhat is causing\b",
        r"\bnitumie dawa gani\b",
        r"\binamaanisha nini\b",
    ],

    "PATIENT_SPECIFIC": [
        r"\bmy results?\b",
        r"\bmy report\b",
        r"\bpatient.s results?\b",
        r"\bpatient.s report\b",
        r"\bcase id\b",
        r"\bcase number\b",
        r"\baccession\b",
        r"\bresults? status\b",
        r"\bwhere are.*results?\b",
        r"\bsend.*results?\b",
        r"\bshare.*results?\b",
        r"\bresults? for patient\b",
        r"\bmajibu yangu\b",
        r"\bresults zangu\b",
        r"\bresults za mgonjwa\b",
    ],

    "OTHER": [
        r"\bopening hours\b",
        r"\bclosing time\b",
        r"\blocation\b",
        r"\bwhere are you\b",
        r"\baddress\b",
        r"\binsurance\b",
        r"\bmpesa\b",
        r"\bpayment method\b",
        r"\bappointment\b",
        r"\bhome collection\b",
        r"\bcomplaint\b",
        r"\brefund\b",
        r"\bmko wapi\b",
    ],
}

COMPILED_PATTERNS = {
    intent: [
        re.compile(pattern, re.IGNORECASE)
        for pattern in patterns
    ]
    for intent, patterns in INTENT_PATTERNS.items()
}


def detect_intents(question):
    detected = []

    for intent, patterns in COMPILED_PATTERNS.items():
        if any(p.search(question) for p in patterns):
            detected.append(intent)

    # Avoid assigning PRICE solely because "ngapi"
    # occurs in a duration or volume question.
    explicit_price = re.search(
        r"\b(price|cost|charge|charges|bei|pesa|"
        r"quotation|quote|fees?|rates?)\b",
        question,
        re.IGNORECASE,
    )

    duration_or_volume = re.search(
        r"\b(siku ngapi|masaa mangapi|"
        r"how much blood|how many ml|"
        r"how many days|how many hours)\b",
        question,
        re.IGNORECASE,
    )

    if duration_or_volume and not explicit_price:
        if "PRICE" in detected:
            detected.remove("PRICE")

    return detected or ["OTHER"]


INTENT_TO_FIELDS = {
    "PRICE": "price",
    "TAT": "tat",
    "SPECIMEN": "specimen",
    "PREPARATION": "preparation",
    "AVAILABILITY": "catalogue_listing",
    "TEST_INFORMATION": "test_information",
}


def requested_fields(intents):
    return [
        INTENT_TO_FIELDS[i]
        for i in intents
        if i in INTENT_TO_FIELDS
    ]


# =========================================================
# 3. KNOWLEDGE BASE
# =========================================================

def load_knowledge_base():

    folder = active_kb_folder(KB_ROOT)

    print(f"\nKnowledge base: {folder.name}")

    with open(
        folder / "documents.jsonl",
        encoding="utf-8"
    ) as f:
        docs = [
            json.loads(line)
            for line in f
            if line.strip()
        ]

    report = json.loads(
        (folder / "quality_report.json").read_text(
            encoding="utf-8"
        )
    )

    print(f"Catalogue records: {len(docs)}")

    index = faiss.read_index(
        str(folder / "catalogue.faiss")
    )

    if index.ntotal != len(docs):
        raise ValueError(
            "FAISS index and catalogue document "
            "counts do not match."
        )

    print("Loading embedding model once...")

    model = SentenceTransformer(
        report["embedding_model"],
        device="cpu"
    )

    if model.get_sentence_embedding_dimension() != index.d:
        raise ValueError(
            "Embedding dimension does not match FAISS."
        )

    return docs, index, model, folder.name


# =========================================================
# 4. CATALOGUE TEST IDENTIFICATION
# =========================================================

GENERIC_ALIASES = {
    "test", "tests", "blood", "urine", "stool",
    "sample", "profile", "screen", "panel",
    "serum", "plasma", "culture", "result",
    "results", "total", "free", "only",
    "male", "female", "normal", "routine",
    "fluid", "body", "other", "control",
    "in", "it", "is", "as", "at", "or",
    "to", "no", "do", "on", "an", "am",
    "us", "we", "me", "be", "he", "she",
}


class TestIdentifier:

    def __init__(self, docs):

        self.alias_index = defaultdict(set)
        self.prefix_index = defaultdict(list)

        for doc in docs:

            aliases = set(field_aliases(doc))

            # Preserve the complete catalogue name.
            aliases.add(
                canonical(doc.get("name", ""))
            )

            for alias in aliases:

                alias = canonical(alias)

                if len(alias) < 2:
                    continue

                if alias in GENERIC_ALIASES:
                    continue

                if not re.search(r"[a-z]", alias):
                    continue

                self.alias_index[alias].add(
                    str(doc.get("code", ""))
                )

        for alias in self.alias_index:

            words = tuple(alias.split())

            if words:
                self.prefix_index[words[0]].append(words)

        for word in self.prefix_index:

            self.prefix_index[word].sort(
                key=len,
                reverse=True
            )

        print(
            f"Catalogue aliases indexed: "
            f"{len(self.alias_index)}"
        )

    def identify(self, question):

        words = canonical(question).split()

        matches = []
        position = 0

        while position < len(words):

            found = None

            candidates = self.prefix_index.get(
                words[position], []
            )

            for candidate in candidates:

                end = position + len(candidate)

                if tuple(words[position:end]) == candidate:
                    found = candidate
                    break

            if found:

                matches.append(" ".join(found))
                position += len(found)

            else:

                position += 1

        return list(dict.fromkeys(matches))


# =========================================================
# 5. FALLBACK QUERY PREPARATION
# =========================================================

NOISE_PATTERNS = [
    r"\b(good morning|good afternoon|good evening)\b",
    r"\b(hello|hi|hey|habari|sasa|mambo)\b",
    r"\b(kindly|please|tafadhali|asante)\b",
    r"\b(i would like to know|i want to know)\b",
    r"\b(nataka kujua|naomba kujua)\b",
    r"\b(how much|how long|how soon)\b",
    r"\b(do you offer|do you do|do you have)\b",
    r"\b(can you do|can you run)\b",
    r"\b(mnafanya|mnayo|inapatikana)\b",
    r"\b(bei ni ngapi|bei ya|ni ngapi)\b",
    r"\b(price|cost|charges|quotation|tat)\b",
    r"\b(turnaround time|specimen requirements)\b",
    r"\b(which sample|which tube|should i fast)\b",
    r"\b(please advise|let me know)\b",
    r"\b(thank you|thanks|shukran)\b",
]


def clean_search_query(question):

    cleaned = question

    for pattern in NOISE_PATTERNS:

        cleaned = re.sub(
            pattern,
            " ",
            cleaned,
            flags=re.IGNORECASE
        )

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned or question


def build_search_queries(question, identifier):

    detected_tests = identifier.identify(question)

    if detected_tests:

        # Search every identified test separately.
        return detected_tests, "CATALOGUE_ALIAS"

    # Numeric codes, spelling errors and unknown
    # test names can still reach V4 retrieval.
    return [
        clean_search_query(question)
    ], "FALLBACK_QUERY"


# =========================================================
# 6. BATCH V4 RETRIEVAL
# =========================================================

def run_batch_retrieval(queries, docs, index, model):

    unique_queries = list(dict.fromkeys(queries))

    results = {}
    semantic_queries = []

    print(
        f"\nUnique search queries: "
        f"{len(unique_queries)}"
    )

    print("Running V4 lexical retrieval...")

    for number, query in enumerate(
        unique_queries, start=1
    ):

        lexical_matches = rank_lexical(
            query, docs, TOP_K
        )

        results[query] = [
            (record, "lexical", float(score))
            for record, score in lexical_matches
        ]

        if len(lexical_matches) < TOP_K:

            semantic_queries.append(query)

        if number % 100 == 0:

            print(
                f"Lexical retrieval: "
                f"{number}/{len(unique_queries)}"
            )

    print(
        f"\nSemantic fallback queries: "
        f"{len(semantic_queries)}"
    )

    if not semantic_queries:

        return results

    print("Generating embeddings in batches...")

    vectors = model.encode(
        semantic_queries,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True
    ).astype("float32")

    distances, indices = index.search(
        vectors,
        min(index.ntotal, 100)
    )

    print("Completing semantic retrieval...")

    for query, scores, locations in zip(
        semantic_queries,
        distances,
        indices
    ):

        matches = results[query]

        seen = {
            str(record["code"])
            for record, _, _ in matches
        }

        vet_query = bool(
            set(canonical(query).split())
            & {"vet", "animal", "dog", "cat"}
        )

        for similarity, location in zip(
            scores, locations
        ):

            if location < 0:
                continue

            if float(similarity) < SEMANTIC_THRESHOLD:
                continue

            record = docs[int(location)]
            code = str(record["code"])

            if code in seen:
                continue

            is_veterinary = (
                "vet" in set(
                    canonical(record["name"]).split()
                )
            )

            if is_veterinary and not vet_query:
                continue

            matches.append(
                (
                    record,
                    "semantic",
                    float(similarity)
                )
            )

            seen.add(code)

            if len(matches) >= TOP_K:
                break

    return results


# =========================================================
# 7. RAW CATALOGUE EVIDENCE
# =========================================================

def as_text(value):

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False
        )

    return str(value)


def candidate_evidence(
    query,
    record,
    method,
    score,
    rank
):

    metadata = record.get("metadata", {})

    return {
        "search_query": query,
        "rank": rank,
        "test_code": str(record.get("code", "")),
        "test_name": as_text(record.get("name")),
        "retrieval_method": method,
        "retrieval_score": score,
        "price": as_text(metadata.get("rate")),
        "tat": as_text(metadata.get("reportDays")),
        "report_date": as_text(
            metadata.get("reportDate")
        ),
        "specimen": as_text(
            metadata.get("specimenReqQuantity")
        ),
        "instructions": as_text(
            metadata.get("instructions")
        ),
        "description": as_text(
            metadata.get("description")
        ),
        "test_details": as_text(
            metadata.get("testDetails")
        ),
    }


def evidence_for_annotation(candidates, field):

    if not candidates:
        return "NO MATCH RETURNED"

    lines = []

    for item in candidates:

        value = item.get(field, "")

        if not str(value).strip():
            value = "[Not provided]"

        prefix = (
            f'{item["search_query"]} | '
            f'#{item["rank"]} | '
            f'{item["test_code"]}'
        )

        lines.append(
            f"{prefix}: {value}"
        )

    result = "\n\n".join(lines)

    # Excel permits at most 32,767 characters per cell.
    if len(result) > 32000:

        result = (
            result[:31900]
            + "\n[TRUNCATED: see raw CSV for full evidence]"
        )

    return result


# =========================================================
# 8. ANNOTATION WORKBOOK
# =========================================================

def create_annotation_workbook(annotation_df, path):

    instructions = pd.DataFrame({
        "Item": [
            "Purpose",
            "ANSWER",
            "ESCALATE",
            "Multiple intents",
            "Multiple tests",
            "Incorrect retrieval",
            "Missing information",
            "Clinical enquiries",
            "Patient-specific enquiries",
            "Availability",
            "Turnaround time",
            "Missing preparation instructions",
            "Unclear cases",
            "Independence",
            "Question text",
            "Candidate evidence",
        ],

        "Guidance": [
            "Assess whether the available catalogue "
            "evidence can safely and completely resolve "
            "the original enquiry.",

            "Assign ANSWER only when all essential "
            "requested information is supported by "
            "relevant evidence.",

            "Assign ESCALATE when any essential "
            "information is unsupported, unclear, "
            "incorrect or unsafe to answer.",

            "All requested intents must be addressed.",

            "All requested tests must be addressed.",

            "Do not use information from an incorrect "
            "test or substitute another test.",

            "Do not supplement missing catalogue "
            "evidence from personal knowledge.",

            "Escalate individualized clinical advice "
            "and patient result interpretation.",

            "Escalate requests for individual patient "
            "reports, result status or case details.",

            "Catalogue listing supports general service "
            "offering, not current stock or operational "
            "availability.",

            "Catalogue TAT is a standard estimate, "
            "not a patient-specific result promise.",

            "An empty instructions field does not "
            "establish that no preparation is needed.",

            "Leave the label blank if uncertain and "
            "return to the case for adjudication.",

            "Assign labels independently of model "
            "predictions or automated decisions.",

            "Do not modify original questions.",

            "Each item is identified by search query, "
            "candidate rank and catalogue code. "
            "Rank alone does not establish correctness.",
        ]
    })

    with pd.ExcelWriter(
        path,
        engine="openpyxl"
    ) as writer:

        annotation_df.to_excel(
            writer,
            sheet_name="Annotation",
            index=False
        )

        instructions.to_excel(
            writer,
            sheet_name="Instructions",
            index=False
        )

        workbook = writer.book
        ws = workbook["Annotation"]

        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

        header_fill = PatternFill(
            fill_type="solid",
            fgColor="17365D"
        )

        for cell in ws[1]:

            cell.fill = header_fill

            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )

            cell.alignment = Alignment(
                vertical="center",
                wrap_text=True
            )

        ws.row_dimensions[1].height = 32

        widths = {
            "A": 62,  # Question
            "B": 50,  # Test names
            "C": 28,  # Test codes
            "D": 34,  # Price
            "E": 34,  # TAT
            "F": 48,  # Specimen
            "G": 60,  # Instructions
            "H": 60,  # Description
            "I": 55,  # Details
            "J": 20,  # Decision label
            "K": 48,  # Label reason
        }

        for column, width in widths.items():

            ws.column_dimensions[column].width = width

        for row in ws.iter_rows(min_row=2):

            for cell in row:

                cell.alignment = Alignment(
                    vertical="top",
                    wrap_text=True
                )

                # Prevent question or catalogue text from
                # accidentally being interpreted as a formula.
                if cell.data_type == "f":
                    cell.data_type = "s"

            ws.row_dimensions[row[0].row].height = 100

            for cell in row[9:11]:

                cell.fill = PatternFill(
                    fill_type="solid",
                    fgColor="FFF2CC"
                )

        validation = DataValidation(
            type="list",
            formula1='"ANSWER,ESCALATE"',
            allow_blank=True
        )

        validation.showErrorMessage = True
        validation.errorTitle = "Invalid decision"
        validation.error = (
            "Select ANSWER or ESCALATE."
        )
        validation.errorStyle = "stop"

        ws.add_data_validation(validation)

        validation.add(
            f"J2:J{ws.max_row}"
        )

        guide = workbook["Instructions"]

        guide.column_dimensions["A"].width = 30
        guide.column_dimensions["B"].width = 115
        guide.freeze_panes = "A2"

        for cell in guide[1]:

            cell.fill = header_fill
            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )

        for row in guide.iter_rows(min_row=2):

            for cell in row:

                cell.alignment = Alignment(
                    wrap_text=True,
                    vertical="top"
                )

            guide.row_dimensions[row[0].row].height = 36


# =========================================================
# 9. MAIN PROCESSING PIPELINE
# =========================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process a limited number for pilot testing."
    )

    args = parser.parse_args()

    output_dir = (
        OUTPUT_DIR / "pilot"
        if args.limit
        else OUTPUT_DIR
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    print("\nLoading combined dataset...")

    df = pd.read_excel(INPUT_FILE)

    required = {"question", "source_type"}

    if not required.issubset(df.columns):

        raise ValueError(
            f"Required columns missing: "
            f"{required - set(df.columns)}"
        )

    df = df[["question", "source_type"]].copy()

    if df["question"].isna().any():

        raise ValueError(
            "Missing questions detected."
        )

    df["question"] = df["question"].astype(str)

    if df["question"].str.strip().eq("").any():

        raise ValueError(
            "Blank questions detected."
        )

    normalized = (
        df["question"]
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    if normalized.duplicated().any():

        raise ValueError(
            "Duplicate normalized questions detected. "
            "Resolve before annotation."
        )

    if args.limit:

        df = df.sample(
            n=min(args.limit, len(df)),
            random_state=42
        )

    df = df.reset_index(drop=True)

    print(f"Enquiries to process: {len(df)}")
    print(df["source_type"].value_counts())

    docs, index, model, kb_version = (
        load_knowledge_base()
    )

    identifier = TestIdentifier(docs)

    prepared = []
    all_queries = []

    print("\nDetecting intents and test names...")

    for question, source in df.itertuples(
        index=False,
        name=None
    ):

        intents = detect_intents(question)

        queries, query_method = build_search_queries(
            question,
            identifier
        )

        prepared.append({
            "question": question,
            "source_type": source,
            "intent_group": ";".join(intents),
            "requested_fields": ";".join(
                requested_fields(intents)
            ),
            "search_queries": queries,
            "query_extraction_method": query_method,
        })

        all_queries.extend(queries)

    retrieval_results = run_batch_retrieval(
        all_queries,
        docs,
        index,
        model
    )

    retrieved_rows = []
    annotation_rows = []

    intent_counter = Counter()
    retrieval_counter = Counter()

    print("\nPreparing output files...")

    for item in prepared:

        candidates = []

        intent_counter.update(
            item["intent_group"].split(";")
        )

        for query in item["search_queries"]:

            matches = retrieval_results.get(
                query, []
            )

            for rank, match in enumerate(
                matches, start=1
            ):

                record, method, score = match

                evidence = candidate_evidence(
                    query,
                    record,
                    method,
                    score,
                    rank
                )

                candidates.append(evidence)

        top_candidates = [
            candidate
            for candidate in candidates
            if candidate["rank"] == 1
        ]

        retrieval_counter.update([
            "match_returned"
            if candidates
            else "no_match"
        ])

        retrieved_rows.append({
            "question": item["question"],
            "source_type": item["source_type"],
            "intent_group": item["intent_group"],
            "requested_fields": item["requested_fields"],

            "search_queries": ";".join(
                item["search_queries"]
            ),

            "query_extraction_method":
                item["query_extraction_method"],

            "retrieved_test_name": ";".join(
                c["test_name"]
                for c in top_candidates
            ),

            "retrieved_test_code": ";".join(
                c["test_code"]
                for c in top_candidates
            ),

            "retrieval_method": ";".join(
                c["retrieval_method"]
                for c in top_candidates
            ),

            "retrieval_score": ";".join(
                str(c["retrieval_score"])
                for c in top_candidates
            ),

            "candidate_count": len(candidates),

            "candidate_evidence_json": json.dumps(
                candidates,
                ensure_ascii=False
            ),

            "knowledge_base_version": kb_version,
        })

        annotation_rows.append({
            "question": item["question"],

            "retrieved_test_name":
                evidence_for_annotation(
                    candidates, "test_name"
                ),

            "retrieved_test_code":
                evidence_for_annotation(
                    candidates, "test_code"
                ),

            "retrieved_price":
                evidence_for_annotation(
                    candidates, "price"
                ),

            "retrieved_tat":
                evidence_for_annotation(
                    candidates, "tat"
                ),

            "retrieved_specimen":
                evidence_for_annotation(
                    candidates, "specimen"
                ),

            "retrieved_instructions":
                evidence_for_annotation(
                    candidates, "instructions"
                ),

            "retrieved_description":
                evidence_for_annotation(
                    candidates, "description"
                ),

            "retrieved_test_details":
                evidence_for_annotation(
                    candidates, "test_details"
                ),

            "decision_label": "",
            "label_reason": "",
        })

    retrieval_df = pd.DataFrame(retrieved_rows)

    annotation_df = pd.DataFrame(annotation_rows)

    # Hide source ordering during human annotation.
    annotation_df = annotation_df.sample(
        frac=1,
        random_state=42
    ).reset_index(drop=True)

    retrieval_path = (
        output_dir / "enquiries_retrieved.csv"
    )

    retrieval_df.to_csv(
        retrieval_path,
        index=False,
        encoding="utf-8-sig"
    )

    annotation_path = (
        output_dir / "annotation_workbook.xlsx"
    )

    create_annotation_workbook(
        annotation_df,
        annotation_path
    )

    summary = {
        "total_enquiries": len(df),
        "source_distribution":
            df["source_type"].value_counts().to_dict(),
        "intent_distribution": dict(intent_counter),
        "unique_search_queries": len(set(all_queries)),
        "retrieval_summary": dict(retrieval_counter),
        "knowledge_base_version": kb_version,
        "top_k_per_search_query": TOP_K,
        "semantic_threshold": SEMANTIC_THRESHOLD,
        "automatic_decision_labels": False,
    }

    summary_path = (
        output_dir / "intent_retrieval_summary.json"
    )

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\n" + "=" * 60)
    print("PROCESSING COMPLETED")
    print("=" * 60)

    print(json.dumps(summary, indent=2))

    print("\nFiles generated:")
    print(retrieval_path)
    print(annotation_path)
    print(summary_path)

    print(
        "\nNo ANSWER or ESCALATE labels "
        "have been assigned automatically."
    )

    print("\nIndependent human annotation is next.")


if __name__ == "__main__":
    main()
