"""Correct pseudonymized WhatsApp message roles without exposing sender names.

Run from the customer-support-rag project root:
    python correct_message_roles.py
"""
from pathlib import Path
import csv
import re
from collections import Counter

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'data' / 'private' / 'messages_anon.csv'
STAFF_IDS = ROOT / 'data' / 'private' / 'staff_ids.txt'
OUTPUT = ROOT / 'data' / 'processed' / 'messages_roles_corrected.csv'


def read_staff_ids(path):
    if not path.is_file():
        raise SystemExit(f'Missing staff ID file: {path}')
    values = [line.strip().lstrip('\ufeff') for line in path.read_text(encoding='utf-8-sig').splitlines()]
    ids = {v for v in values if v and not v.startswith('#')}
    if not ids:
        raise SystemExit('staff_ids.txt is empty. No changes made.')
    if any(not re.fullmatch(r'(?:CLIENT|STAFF)_\d+', value) for value in ids):
        raise SystemExit('Invalid ID format in staff_ids.txt; use exact pseudonyms such as CLIENT_001.')
    return ids


def main():
    staff_ids = read_staff_ids(STAFF_IDS)
    if not INPUT.is_file():
        raise SystemExit(f'Missing input CSV: {INPUT}\nCopy your anonymized messages CSV here first.')
    with INPUT.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        required = {'group_id', 'msg_idx', 'date', 'time', 'speaker', 'role', 'text'}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise SystemExit(f'Unexpected CSV columns. Expected at least {sorted(required)}')
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not rows:
        raise SystemExit('Input CSV has no messages.')
    speakers = {r['speaker'].strip() for r in rows}
    unknown = sorted(staff_ids - speakers)
    if unknown:
        raise SystemExit('These staff IDs do not occur in the CSV (check pseudonyms): ' + ', '.join(unknown))
    for row in rows:
        row['role'] = 'staff' if row['speaker'].strip() in staff_ids else 'client'
    counts = Counter(r['role'] for r in rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.resolve() == INPUT.resolve():
        raise SystemExit('Output must not overwrite input.')
    with OUTPUT.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print('Corrected CSV:', OUTPUT)
    print('Total messages:', len(rows))
    print('Staff messages:', counts['staff'])
    print('Client/other messages:', counts['client'])
    print('Distinct staff IDs:', len(staff_ids))
    print('Distinct remaining speaker IDs:', len(speakers - staff_ids))
    print('Groups:', len({r['group_id'] for r in rows}))
    print('Original CSV unchanged:', INPUT)
    print('NOTE: Non-staff IDs are provisionally labelled client; they may include other senders.')


if __name__ == '__main__':
    main()
