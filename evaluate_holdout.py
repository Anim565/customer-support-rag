"""Frozen holdout evaluation: V4 lexical + actual FAISS fallback. No training/tuning."""
import argparse,csv,json
from pathlib import Path
from kb_paths import active_kb_folder
from ranking_v4 import rank_lexical,canonical

def load_docs(root):
    folder = active_kb_folder(root)
    docs=[json.loads(s) for s in (folder/'documents.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    return docs,folder

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cases',default='evaluation_cases_holdout.csv');ap.add_argument('--kb',default='data/knowledge_base');ap.add_argument('--out',default='data/evaluation/holdout_v4');ap.add_argument('--lexical-only',action='store_true');a=ap.parse_args()
    docs,folder=load_docs(Path(a.kb)); codes={str(d['code']) for d in docs}
    with open(a.cases,encoding='utf-8-sig',newline='') as f:cases=list(csv.DictReader(f))
    for c in cases:
        if c['expected_code'] and c['expected_code'] not in codes:raise ValueError(f"Missing expected code {c['expected_code']} in case {c['id']}")
    model=index=None
    if not a.lexical_only:
        import faiss
        from sentence_transformers import SentenceTransformer
        report=json.loads((folder/'quality_report.json').read_text(encoding='utf-8'))
        model=SentenceTransformer(report['embedding_model']);index=faiss.read_index(str(folder/'catalogue.faiss'))
        if index.ntotal!=len(docs):raise ValueError('Index and documents length differ')
    results=[]
    for c in cases:
        q=c['query'];expected=c['expected_code'].strip();lex=rank_lexical(q,docs,5)
        matches=[(d,'lexical',s) for d,s in lex];seen={str(d['code']) for d,_,_ in matches}
        if model is not None and len(matches)<5:
            import numpy as np
            vec=model.encode([q],normalize_embeddings=True,convert_to_numpy=True)
            distances,ids=index.search(vec,min(index.ntotal,100))
            vet=bool(set(canonical(q).split()) & {'vet','animal','dog','cat'})
            for sim,i in zip(distances[0],ids[0]):
                if i<0 or float(sim)<0.35:continue
                d=docs[int(i)];code=str(d['code'])
                if code in seen or (not vet and 'vet' in set(canonical(d['name']).split())):continue
                matches.append((d,'semantic',float(sim)));seen.add(code)
                if len(matches)>=5:break
        retrieved=[str(d['code']) for d,_,_ in matches];rank=retrieved.index(expected)+1 if expected in retrieved else None
        results.append({**c,'top1':retrieved[0] if retrieved else '', 'top1_method':matches[0][1] if matches else '', 'retrieved_codes':'|'.join(retrieved),'expected_rank':rank or '', 'hit_at_1':int(rank==1),'hit_at_5':int(rank is not None),'reciprocal_rank':1/rank if rank else 0,'no_result':int(not matches)})
    pos=[r for r in results if r['expected_code']];neg=[r for r in results if not r['expected_code']]
    metrics={'mode':'lexical-only' if a.lexical_only else 'hybrid lexical+FAISS','dataset_size':len(results),'positive_cases':len(pos),'negative_cases':len(neg),'top1_accuracy_on_positives':sum(r['hit_at_1'] for r in pos)/len(pos),'recall_at_5':sum(r['hit_at_5'] for r in pos)/len(pos),'mrr_at_5':sum(r['reciprocal_rank'] for r in pos)/len(pos),'no_result_rate_on_negatives':sum(r['no_result'] for r in neg)/len(neg),'caution':'Negative no-result is NOT a validated safe abstention metric. No answer generation, clinical safety, or escalation evaluated.'}
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    with (out/'holdout_case_results.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=results[0].keys());w.writeheader();w.writerows(results)
    (out/'holdout_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2));print('\nFailed positive cases:')
    for r in pos:
        if not r['hit_at_1']:print(f"{r['id']}: {r['query']} expected={r['expected_code']} top={r['top1'] or 'NONE'} rank={r['expected_rank'] or 'NONE'}")
    print('\nNegative cases returning candidates (not necessarily errors):')
    for r in neg:
        if not r['no_result']:print(f"{r['id']}: {r['query']} top={r['top1']}")
if __name__=='__main__':main()
