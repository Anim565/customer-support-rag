"""Audit synthetic enquiries against actual DKL v4 knowledge-base retrieval.

Run in the project root, where ranking_v4.py and data/knowledge_base/current.json exist.
No synthetic evidence-status column is used to derive retrieval features.
This is an evidence audit, NOT an automatic relabelling or model training step.
"""
import argparse, csv, json, re, sys
from pathlib import Path
from kb_paths import active_kb_folder
from collections import Counter

try:
    from ranking_v4 import rank_lexical, canonical
except ImportError:
    sys.exit('ERROR: ranking_v4.py not found. Copy this script into the project root next to ranking_v4.py.')

FIELD_MAP = {
    'price': ('rate',), 'specimen': ('specimenReqQuantity',),
    'instructions': ('instructions',), 'tat': ('reportDays', 'reportDate'),
    'availability': ('name',),
}
PATIENT_RISK = re.compile(r'\b(my|mine|patient|report|result|biopsy|prescription|diagnos|treat|medicine|medication|dawa|matokeo yangu|mgonjwa|my mum|my dad)\b', re.I)

def nonempty(v):
    return v is not None and str(v).strip().lower() not in {'', 'none', 'null', 'nan', 'n/a'}

def load_kb(root):
    folder = active_kb_folder(root)
    docs = [json.loads(line) for line in (folder/'documents.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    return folder, docs

def semantic_fallback(query, folder, docs, lexical, top_k, model, index):
    import numpy as np
    seen = {str(r.get('code')) for r, _ in lexical}
    result = [(r, 'lexical', score) for r, score in lexical]
    if len(result) >= top_k or model is None: return result
    vec = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
    distances, indices = index.search(np.asarray(vec, dtype='float32'), min(index.ntotal, 100))
    vet = bool(set(canonical(query).split()) & {'vet','animal','dog','cat'})
    for sim, idx in zip(distances[0], indices[0]):
        if idx < 0 or float(sim) < 0.35: continue
        r = docs[int(idx)]; code = str(r.get('code'))
        if code in seen: continue
        if not vet and 'vet' in set(canonical(r.get('name', '')).split()): continue
        result.append((r, 'semantic', float(sim))); seen.add(code)
        if len(result) >= top_k: break
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', default='data/synthetic/synthetic_all_v2.csv')
    ap.add_argument('--kb', default='data/knowledge_base')
    ap.add_argument('--out', default='data/processed/synthetic_v4_evidence_audit.csv')
    ap.add_argument('--top-k', type=int, default=5)
    ap.add_argument('--lexical-only', action='store_true', help='Diagnostic only; not full v4 retrieval')
    args = ap.parse_args()
    kb = Path(args.kb)
    if not (kb/'current.json').exists(): sys.exit(f'ERROR: missing {kb}/current.json; build KB first.')
    folder, docs = load_kb(kb)
    model = index = None
    if not args.lexical_only:
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            report = json.loads((folder/'quality_report.json').read_text(encoding='utf-8'))
            model = SentenceTransformer(report['embedding_model'])
            index = faiss.read_index(str(folder/'catalogue.faiss'))
            if index.ntotal != len(docs): sys.exit('ERROR: FAISS index/document count mismatch')
        except (ImportError, FileNotFoundError, KeyError) as exc:
            sys.exit(f'ERROR: full V4 semantic retrieval unavailable: {exc}. Install dependencies/build KB; use --lexical-only only for diagnostics.')
    with open(args.input, encoding='utf-8-sig', newline='') as f:
        source = list(csv.DictReader(f))
    if not source: sys.exit('ERROR: no input records')
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    extra = ['v4_mode','retrieval_count','top_match_code','top_match_name','top_match_method','top_match_score','expected_test_in_top5','expected_test_rank','matched_field_present','retrieved_field_value','safety_keyword_flag','evidence_audit_status','requires_label_review']
    counts = Counter()
    with out.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(source[0])+extra, extrasaction='ignore'); writer.writeheader()
        for row in source:
            q = row.get('enquiry', '')
            lex = rank_lexical(q, docs, args.top_k)
            hits = semantic_fallback(q, folder, docs, lex, args.top_k, model, index)
            expected = str(row.get('test_code') or '').strip()
            if expected.endswith('.0'): expected = expected[:-2]
            found = next(((i+1, r) for i,(r,_,_) in enumerate(hits) if expected and str(r.get('code')) == expected), None)
            field = (row.get('requested_field') or '').strip().lower()
            keys = FIELD_MAP.get(field, ())
            # Check the requested field on the exact expected test, not an unrelated top result.
            value = None
            if found and keys:
                rec = found[1]; meta = rec.get('metadata', {})
                value = next((str((rec if k == 'name' else meta).get(k)) for k in keys if nonempty((rec if k == 'name' else meta).get(k))), None)
            top = hits[0] if hits else None
            has_evidence = bool(found and value)
            safety = bool(PATIENT_RISK.search(q))
            # Audit status is not the final ground truth: 'patient' keyword can be benign (e.g. 'patient price').
            if not expected or not keys:
                status = 'manual_review_non_catalogue_or_unknown_field'
            elif has_evidence:
                status = 'expected_test_and_field_retrieved'
            elif found:
                status = 'expected_test_found_field_missing'
            else:
                status = 'expected_test_not_in_top_k'
            orig = (row.get('label') or '').upper()
            conflict = (orig == 'ANSWER' and not has_evidence) or (orig == 'ESCALATE' and has_evidence)
            row.update({
                'v4_mode':'lexical_only_diagnostic' if args.lexical_only else 'hybrid_v4',
                'retrieval_count':len(hits), 'top_match_code':str(top[0].get('code')) if top else '',
                'top_match_name':str(top[0].get('name')) if top else '',
                'top_match_method':top[1] if top else '',
                'top_match_score':f'{top[2]:.5f}' if top else '',
                'expected_test_in_top5':int(bool(found)), 'expected_test_rank':found[0] if found else '',
                'matched_field_present':int(has_evidence), 'retrieved_field_value':(value or '')[:300],
                'safety_keyword_flag':int(safety), 'evidence_audit_status':status,
                'requires_label_review':int(conflict or status.startswith('manual_review') or safety),
            })
            counts[status] += 1
            if conflict: counts['label_evidence_conflict'] += 1
            writer.writerow(row)
    print(f'Wrote {len(source)} rows: {out}')
    print('Retrieval mode:', 'LEXICAL ONLY DIAGNOSTIC' if args.lexical_only else 'HYBRID V4')
    print('Audit counts:', dict(counts))
    print('WARNING: This does not prove answerability or clinical safety. Do not train on synthetic evidence_status or evidence_excerpt.')
    print('WARNING: Do not auto-flip labels based on retrieval; review conflicts and apply patient-safety policy.')

if __name__ == '__main__': main()
