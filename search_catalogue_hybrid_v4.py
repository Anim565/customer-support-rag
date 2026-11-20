"""Search using v4 lexical/code ranking, with semantic fallback for remaining slots."""
import argparse,json
from pathlib import Path
from kb_paths import active_kb_folder
from ranking_v4 import rank_lexical,canonical

def main():
    p=argparse.ArgumentParser();p.add_argument('query');p.add_argument('--output',default='data/knowledge_base');p.add_argument('--top-k',type=int,default=5);a=p.parse_args()
    folder = active_kb_folder(a.output)
    docs=[json.loads(line) for line in (folder/'documents.jsonl').read_text(encoding='utf-8').splitlines()]
    matches=[(r,'lexical',score) for r,score in rank_lexical(a.query,docs,a.top_k)]
    seen={str(r['code']) for r,_,_ in matches}
    if len(matches)<a.top_k:
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
            report=json.loads((folder/'quality_report.json').read_text(encoding='utf-8'))
            model=SentenceTransformer(report['embedding_model'])
            v=model.encode([a.query],normalize_embeddings=True,convert_to_numpy=True)
            idx=faiss.read_index(str(folder/'catalogue.faiss'))
            distances,indices=idx.search(v,min(idx.ntotal,100))
            vet=bool(set(canonical(a.query).split()) & {'vet','animal','dog','cat'})
            for sim,i in zip(distances[0],indices[0]):
                if i<0 or float(sim)<0.35:continue
                r=docs[int(i)];code=str(r['code'])
                if code in seen:continue
                if not vet and 'vet' in set(canonical(r['name']).split()):continue
                matches.append((r,'semantic',float(sim)));seen.add(code)
                if len(matches)>=a.top_k:break
        except ImportError:pass
    for rank,(r,method,score) in enumerate(matches,1):
        print(f'\n{rank}. [{r["code"]}] {r["name"]} | match={method} | score={score:.3f}')
        m=r.get('metadata',{})
        for label,key in [('Synonyms','synonyms'),('Specimen','specimenReqQuantity'),('Collection instructions','instructions'),('Description','description'),('Tests included','testDetails'),('Reported turnaround','reportDays'),('Report date','reportDate'),('Standard price (KES)','rate')]:
            value=m.get(key)
            if value is not None and str(value).strip():print(f'{label}: {str(value)[:450]}')
    if not matches:print('No reliable catalogue match. Request clarification or escalate.')
    print('\nNote: Search ranking is not a validated answerability or clinical-safety decision.')
if __name__=='__main__':main()
