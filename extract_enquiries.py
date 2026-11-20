"""Conservative local candidate-enquiry extraction from WhatsApp Pipeline v2.

No external API calls, no automatic training approval. Python standard library only.
"""
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CATEGORIES = [
    ('PATIENT_CASE_FOLLOWUP', r'\b(patient|case|report|result|pending|release|status|registered|sample received|accession)\b.{0,90}\b(status|ready|pending|release|check|update|follow.?up|confirm|trace|sent|received)\b|\b(check|confirm|trace|update|follow.?up|release)\b.{0,90}\b(patient|case|report|result|sample)\b'),
    ('OPERATIONAL_REQUEST', r'\b(urgent|prioriti[sz]e|expedite|rush|process asap|re.?run|recollect|repeat test|escalat|critical|delay|complaint)\b'),
    ('SPECIMEN_PREPARATION', r'\b(specimen|sample type|container|tube|edta|serum|plasma|fasting|collection|collect|volume|transport|stability|storage|requirements?)\b'),
    ('PRICING', r'\b(price|pricing|cost|charges?|quotation|quote|how much|rate|discount|bill)\b'),
    ('TURNAROUND_TIME', r'\b(tat|turnaround|turn around|how long|when.*(ready|available)|duration|days? to (get|receive))\b'),
    ('TEST_AVAILABILITY', r'\b(available|availability|do you (do|offer|perform|run)|can you (do|perform|run)|test menu|offer this test)\b'),
    ('TEST_INFORMATION', r'\b(test|assay|profile|panel|screen|method|reference range|interpretation|cbc|fbc|hba1c|tsh|ana|pcr|culture|biopsy)\b'),
]
ESCALATE_CATS = {'PATIENT_CASE_FOLLOWUP', 'OPERATIONAL_REQUEST'}
REQUEST = re.compile(r'\?|\b(please|kindly|could you|can you|would you|i need|we need|advise|confirm|check|update|share|send|request|require|what|when|where|how|which|is there|do you|any update|follow.?up|status|available|price|cost|tat|urgent|pending|results?)\b', re.I)
LOW_VALUE = re.compile(r'^(hi|hello|hey|good morning|good afternoon|good evening|thanks|thank you|noted|received|okay|ok|alright|welcome|sure|yes|no|👍|🙏|\.)([\s.!]*)$', re.I)
INTERNAL = re.compile(r'\b(qc|calibration|reagent stock|shift handover|night shift|day shift|staff rota|analy[sz]er maintenance|internal audit|odoo|bench duty|lot number)\b', re.I)


def load_jsonl(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def classify(text):
    text = ' '.join(str(text).split())
    if not text or LOW_VALUE.fullmatch(text):
        return 'NON_ENQUIRY', 'EXCLUDE', 'LOW_VALUE', 0
    matches = [name for name, pattern in CATEGORIES if re.search(pattern, text, re.I)]
    request = bool(REQUEST.search(text))
    if not request and not matches:
        return 'UNCERTAIN', 'REVIEW', 'NO_REQUEST_SIGNAL', 0
    if not request and matches:
        return 'UNCERTAIN', 'REVIEW', 'TOPIC_WITHOUT_REQUEST', 0
    if INTERNAL.search(text) and not (set(matches) & ESCALATE_CATS):
        return 'POSSIBLE_INTERNAL', 'REVIEW', 'INTERNAL_TERMS', 1
    category = next((x for x in ['PATIENT_CASE_FOLLOWUP', 'OPERATIONAL_REQUEST', 'SPECIMEN_PREPARATION', 'PRICING', 'TURNAROUND_TIME', 'TEST_AVAILABILITY', 'TEST_INFORMATION'] if x in matches), 'GENERAL_ENQUIRY')
    decision = 'ESCALATE' if category in ESCALATE_CATS else 'ANSWER_CANDIDATE'
    return category, decision, 'RULE_BASED_PRELIMINARY', 1


def run(source, output):
    output.mkdir(parents=True, exist_ok=True)
    rows = list(load_jsonl(source / 'messages_anon.jsonl'))
    reviews = defaultdict(set)
    review_file = source / 'privacy_review.jsonl'
    if review_file.exists():
        for rec in load_jsonl(review_file):
            try:
                n = int(rec.get('record_number', -1))
            except (ValueError, TypeError):
                continue
            if n > 0:
                reviews[(str(rec.get('group_id', '')), n)].add(str(rec.get('reason', 'REVIEW')))
    # Process messages in their original file order, never combine across groups.
    groups = defaultdict(list)
    for row in rows:
        groups[str(row.get('group_id', ''))].append(row)
    candidates = []
    all_counts = Counter()
    categories = Counter()
    decisions = Counter()
    privacy_count = Counter()
    for group, messages in groups.items():
        messages.sort(key=lambda x: int(x.get('record_number', 0)))
        for i, msg in enumerate(messages):
            all_counts['messages_scanned'] += 1
            category, decision, reason, include = classify(msg.get('text', ''))
            all_counts['category_' + category] += 1
            if not include:
                continue
            record = int(msg.get('record_number', 0))
            flagset = sorted(reviews.get((group, record), set()))
            # Context is for local review only; may contain sensitive information.
            neighbors = [m for m in messages[max(0, i-2):min(len(messages), i+3)] if m is not msg]
            context = ' | '.join(f"{m.get('speaker','')}: {str(m.get('text','')).replace(chr(10),' ')[:250]}" for m in neighbors)
            candidates.append({
                'candidate_id': f'ENQ_{len(candidates)+1:06d}',
                'group_id': group,
                'record_number': record,
                'speaker': msg.get('speaker', ''),
                'text': msg.get('text', ''),
                'nearby_context_LOCAL_ONLY': context,
                'preliminary_category': category,
                'preliminary_decision': decision,
                'rule_reason': reason,
                'privacy_flags': ';'.join(flagset),
                'privacy_status': 'UNVALIDATED',
                'training_eligible': 'NO',
                'review_is_customer_enquiry': '',
                'review_complete_enquiry': '',
                'review_category': '',
                'review_decision': '',
                'review_privacy_cleared': '',
                'review_notes_NO_IDENTIFIERS': ''
            })
            categories[category] += 1
            decisions[decision] += 1
            privacy_count['flagged' if flagset else 'unflagged'] += 1
    fields = ['candidate_id','group_id','record_number','speaker','text','nearby_context_LOCAL_ONLY','preliminary_category','preliminary_decision','rule_reason','privacy_flags','privacy_status','training_eligible','review_is_customer_enquiry','review_complete_enquiry','review_category','review_decision','review_privacy_cleared','review_notes_NO_IDENTIFIERS']
    for name, selection in [('enquiry_candidates_LOCAL_ONLY.csv', candidates), ('review_sample_150_LOCAL_ONLY.csv', sample(candidates))]:
        with (output / name).open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(selection)
    report = {
        'source': str(source), 'messages_scanned': len(rows),
        'candidate_message_count_NOT_unique_enquiries': len(candidates),
        'excluded_or_uncertain_messages': len(rows)-len(candidates),
        'candidate_categories': dict(categories),
        'preliminary_decisions': dict(decisions),
        'candidate_privacy_flags': dict(privacy_count),
        'review_sample_size': min(150, len(candidates)),
        'important': [
            'Candidates are messages, not reconstructed unique enquiries.',
            'Heuristic labels are not verified ground truth.',
            'All outputs containing text are LOCAL ONLY and NOT privacy-cleared.',
            'Review both false negatives (excluded messages) and false positives before training.',
            'Do not upload or commit candidate or review CSVs.'
        ]
    }
    (output / 'extraction_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def sample(candidates):
    """Deterministic category-balanced sample; no random leakage into console."""
    by_category = defaultdict(list)
    for c in candidates:
        by_category[c['preliminary_category']].append(c)
    selected = []
    keys = sorted(by_category)
    while len(selected) < 150 and any(by_category.values()):
        for key in keys:
            if by_category[key] and len(selected) < 150:
                selected.append(by_category[key].pop(0))
    return selected


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, default=Path('data/processed/whatsapp_v2'))
    p.add_argument('--output', type=Path, default=Path('data/processed/enquiries_v1'))
    args = p.parse_args()
    run(args.input, args.output)
