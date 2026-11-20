import argparse,csv,json
from pathlib import Path
from ranking_v4 import rank_lexical

def load_docs(kb):
    root=Path(kb);current=json.loads((root/'current.json').read_text(encoding='utf-8'));folder=Path(current['path'])
    return [json.loads(line) for line in (folder/'documents.jsonl').read_text(encoding='utf-8').splitlines()]
def evaluate(docs,cases,out):
    codes={str(d['code']) for d in docs};results=[]
    for case in cases:
        expected=case['expected_code'].strip();query=case['query']
        if expected and expected not in codes:raise ValueError(f'Expected code missing: {expected} for {query}')
        matches=rank_lexical(query,docs,5);found=[str(r['code']) for r,_ in matches]
        rank=found.index(expected)+1 if expected in found else None
        results.append({**case,'retrieved_codes':'|'.join(found),'top1':found[0] if found else '', 'rank':rank or '', 'hit_at_1':int(rank==1),'hit_at_5':int(rank is not None),'reciprocal_rank':1/rank if rank else 0,'lexical_abstained':int(not found),'correct_abstention':int(not expected and not found)})
    pos=[r for r in results if r['expected_code']];neg=[r for r in results if not r['expected_code']]
    metrics={'dataset_size':len(results),'positive_cases':len(pos),'no_catalogue_answer_cases':len(neg),'precision_at_1_proxy':sum(r['hit_at_1'] for r in pos)/len(pos),'recall_at_5':sum(r['hit_at_5'] for r in pos)/len(pos),'mrr_at_5':sum(r['reciprocal_rank'] for r in pos)/len(pos),'lexical_no_match_rate_on_negatives':sum(r['correct_abstention'] for r in neg)/len(neg),'IMPORTANT':'Lexical/code ranking only; does not evaluate FAISS fallback, answer correctness, clinical safety or escalation.'}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with (out/'retrieval_case_results.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=results[0].keys());w.writeheader();w.writerows(results)
    (out/'retrieval_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2));print('\nFailed cases:')
    for r in results:
        if (r['expected_code'] and not r['hit_at_1']) or (not r['expected_code'] and not r['correct_abstention']):print(f"{r['id']}: {r['query']} | expected={r['expected_code'] or 'NONE'} | top={r['top1'] or 'NONE'}")
def main():
    p=argparse.ArgumentParser();p.add_argument('--kb',default='data/knowledge_base');p.add_argument('--cases',default='evaluation_cases_stress.csv');p.add_argument('--out',default='data/evaluation/stress_v4');a=p.parse_args()
    with open(a.cases,encoding='utf-8-sig',newline='') as f:cases=list(csv.DictReader(f))
    evaluate(load_docs(a.kb),cases,a.out)
if __name__=='__main__':main()
