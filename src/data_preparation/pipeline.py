"""WhatsApp export preprocessing. Local processing only; outputs require privacy review."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import zipfile
from datetime import datetime
from collections import Counter
from pathlib import Path

INVIS = '\u200e\u200f\u202a\u202c\u2066\u2067\u2068\u2069'
DATE = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
TIME = r'\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AaPp][Mm])?'
ANDROID = re.compile(rf'^{DATE},?\s+{TIME}\s+-\s+')
IOS = re.compile(rf'^\[{DATE},?\s+{TIME}\]\s*')
HEADER = re.compile(rf'^(?:{DATE},?\s+{TIME}\s+-\s+|\[{DATE},?\s+{TIME}\]\s*)')
SYSTEM = re.compile(r'joined using this group.s invite link|left the group|was added|was removed|messages and calls are end.to.end encrypted|changed the group description|changed this group.s icon|created this group|deleted this message|changed the subject|changed the group settings', re.I)
PATTERNS = [
 ('EMAIL', re.compile(r'(?<!\w)[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)')),
 ('PHONE', re.compile(r'(?<!\w)(?:\+?254|0)[\s-]?[17]\d{2}[\s-]?\d{3}[\s-]?\d{3}(?!\w)')),
 ('PHONE', re.compile(r'(?<!\w)\+?\d{1,3}[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{4}(?!\w)')),
 ('URL', re.compile(r'https?://\S+|www\.\S+', re.I)),
 ('CASE_ID', re.compile(r'\b(?:case|patient|lab|sample|accession|ref(?:erence)?)[\s#:.-]*(?:no\.?\s*)?[A-Za-z]*\d[A-Za-z0-9_/-]{3,}\b', re.I)),
 ('CASE_ID', re.compile(r'\b\d{4,}[_/-]\d{1,4}(?:[_/-]\d{1,4})?\b')),
 ('LONG_NUMBER', re.compile(r'(?<![\w.])\d{7,}(?![\w.])')),
 ('MENTION', re.compile(r'@\+?\d[\d\s-]{7,}|@\S+')),
 ('NATIONAL_ID', re.compile(r'\b(?:national\s+id|passport|nhif|sha\s+number|id\s*(?:no|number))\s*[:#-]?\s*[A-Z0-9-]{5,}\b', re.I)),
]

def load_exports(folder: Path):
    """Yield source name and decoded chat text; ZIP members are never extracted."""
    for path in sorted(folder.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() == '.txt':
            yield str(path.relative_to(folder)), decode(path.read_bytes())
        elif path.suffix.lower() == '.zip':
            with zipfile.ZipFile(path) as archive:
                for member in sorted(archive.infolist(), key=lambda x: x.filename):
                    if member.is_dir() or not member.filename.lower().endswith('.txt'):
                        continue
                    if member.file_size > 50_000_000:
                        raise ValueError('ZIP member exceeds 50MB limit')
                    yield f'{path.relative_to(folder)}::{member.filename}', decode(archive.read(member))

def decode(data: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-16', 'cp1252'):
        try:
            return data.decode(encoding)
        except UnicodeError:
            continue
    return data.decode('utf-8', errors='replace')

def reconstruct(text: str):
    records, current, orphan = [], None, []
    for line in text.splitlines():
        line = line.lstrip(INVIS)
        if HEADER.match(line):
            if current is not None:
                records.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
        elif line.strip():
            orphan.append(line)
    if current is not None:
        records.append(current)
    return ['\n'.join(r) for r in records], orphan

def classify(record: str):
    first, *rest = record.split('\n')
    m = HEADER.match(first)
    if not m:
        return 'UNRECOGNIZED', '', record, ''
    stamp = m.group(0)
    body = first[m.end():]
    if SYSTEM.search(body) and ': ' not in body:
        return 'SYSTEM_EVENT', '', '\n'.join([body, *rest]), stamp
    if ': ' in body:
        sender, msg = body.split(': ', 1)
        if sender.strip():
            return 'USER_MESSAGE', sender.strip(), '\n'.join([msg, *rest]), stamp
    return 'UNRECOGNIZED', '', '\n'.join([body, *rest]), stamp

# Contextual patterns intentionally conservative: ambiguous text goes to review.
NAME_CONTEXT = re.compile(
    r"\b(?P<prefix>(?i:patient(?:\s+name)?|client(?:\s+name)?|name|mr|mrs|ms|dr))"
    r"\s*[:.-]?\s+(?P<name>[A-Z][a-z]{1,}(?:\s+[A-Z][a-z]{1,}){1,3})\b"
)
NAME_CUE = re.compile(r"\b(patient|client|name|mr|mrs|ms|dr)\b", re.I)


def _local_ner(text: str):
    """Optional offline spaCy PERSON entities. Never download models automatically."""
    try:
        import spacy
        nlp = _local_ner._model
    except AttributeError:
        try:
            nlp = spacy.load('en_core_web_sm')
        except (OSError, ImportError):
            return []
        _local_ner._model = nlp
    except ImportError:
        return []
    return [ent.text for ent in nlp(text).ents if ent.label_ == 'PERSON']


def scrub(text: str, extra_names=(), use_ner=False):
    """Conservative pseudonymization, not a guarantee of de-identification."""
    for label, pattern in PATTERNS:
        text = pattern.sub(f'[{label}]', text)
    text = NAME_CONTEXT.sub(lambda m: m.group('prefix') + ' [PERSON]', text)
    names = list(extra_names)
    if use_ner:
        names.extend(_local_ner(text))
    for name in sorted(set(names), key=len, reverse=True):
        if name.strip():
            text = re.sub(r'(?<!\w)' + re.escape(name.strip()) + r'(?!\w)', '[PERSON]', text, flags=re.I)
    return text


def possible_leaks(text: str):
    """Flags are review cues, not a validated privacy detector."""
    flags = {label for label, pattern in PATTERNS if pattern.search(text)}
    if NAME_CONTEXT.search(text):
        flags.add('POSSIBLE_NAME')
    return sorted(flags)


def privacy_risk_flags(original: str, cleaned: str):
    """Conservative review triggers; no claim of recall/sensitivity."""
    flags = set(possible_leaks(cleaned))
    if NAME_CUE.search(original) and '[PERSON]' not in cleaned:
        flags.add('NAME_CUE_UNRESOLVED')
    # A multiword capitalized phrase may be a name or a laboratory term.
    # Flag rather than redact it automatically to avoid clinical information loss.
    if re.search(r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b', cleaned):
        flags.add('CAPITALIZED_PHRASE_REVIEW')
    return sorted(flags)

def process(folder: Path, output: Path, extra_names=(), use_ner=False):
    output.mkdir(parents=True, exist_ok=True)
    if folder.resolve() == output.resolve() or folder.resolve() in output.resolve().parents:
        raise ValueError('Output must not be inside the input folder')
    counts = Counter()
    rows, reviews, source_hashes = [], [], set()
    # Each export gets a stable pseudonymous group ID; no identity mapping is exported.
    for source, chat in load_exports(folder):
        digest = hashlib.sha256(chat.encode('utf-8')).hexdigest()
        if digest in source_hashes:
            counts['duplicate_exports'] += 1
            continue
        source_hashes.add(digest)
        counts['exports_processed'] += 1
        group = f'GROUP_{counts["exports_processed"]:03d}'
        speakers = {}
        records, orphan = reconstruct(chat)
        counts['orphan_lines'] += len(orphan)
        if orphan:
            reviews.append({'group_id': group, 'record_number': 0, 'reason': 'ORPHAN_LINES', 'text': scrub('\n'.join(orphan), extra_names, use_ner)})
        for i, record in enumerate(records, 1):
            kind, sender, message, stamp = classify(record)
            counts[kind] += 1
            if kind == 'SYSTEM_EVENT':
                continue
            if kind == 'UNRECOGNIZED':
                reviews.append({'group_id': group, 'record_number': i, 'reason': kind, 'text': scrub(message, extra_names, use_ner)})
                continue
            if sender not in speakers:
                speakers[sender] = f'PARTICIPANT_{len(speakers)+1:03d}'
            clean = scrub(message, extra_names, use_ner)
            flags = privacy_risk_flags(message, clean)
            if flags:
                counts['messages_flagged_for_privacy_review'] += 1
                reviews.append({'group_id': group, 'record_number': i, 'reason': 'POSSIBLE_IDENTIFIER:' + ','.join(flags), 'text': clean})
            rows.append({'group_id': group, 'record_number': i, 'speaker': speakers[sender], 'timestamp_text': stamp.strip(), 'text': clean, 'privacy_review_required': bool(flags)})
    with (output / 'messages_anon.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['group_id','record_number','speaker','timestamp_text','text','privacy_review_required'])
        writer.writeheader(); writer.writerows(rows)
    with (output / 'messages_anon.jsonl').open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    with (output / 'privacy_review.jsonl').open('w', encoding='utf-8') as f:
        for row in reviews:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    report = dict(counts)
    report.update({'retained_messages': len(rows), 'review_records': len(reviews), 'privacy_review_messages': counts['messages_flagged_for_privacy_review'], 'ner_enabled': use_ner, 'privacy_validation_status': 'NOT VALIDATED — HUMAN REVIEW REQUIRED', 'notes': ['Rule-based and optional local NER redaction cannot guarantee anonymization.', 'Sender IDs are scoped per export.', 'Exact timestamps are retained; assess re-identification risk.', 'No automatic deduplication of messages within distinct exports.']})
    (output / 'audit_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--names-file', type=Path, help='Optional local file of names to redact; never commit')
    parser.add_argument('--use-ner', action='store_true', help='Use locally installed spaCy en_core_web_sm; requires offline setup')
    args = parser.parse_args()
    if not args.input.is_dir():
        parser.error('Input must be an existing directory')
    names = args.names_file.read_text(encoding='utf-8').splitlines() if args.names_file else []
    if args.use_ner:
        try:
            import spacy
            spacy.load('en_core_web_sm')
        except (ImportError, OSError) as exc:
            parser.error('Local spaCy model en_core_web_sm is required for --use-ner')
    print(json.dumps(process(args.input, args.output, names, args.use_ner), indent=2))
if __name__ == '__main__':
    main()
