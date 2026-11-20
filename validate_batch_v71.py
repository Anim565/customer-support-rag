"""Compare fresh batch outputs with stored V6-era outputs on development only."""
import argparse,json,time
from pathlib import Path
import pandas as pd
from llm_query_extractor_v71 import QueryExtractor

def signature(x):
    return (set(x['intent_group']), {(r['test_name'].strip().casefold(),tuple(sorted(r['requested_fields']))) for r in x['requested_tests']},set(t.strip().casefold() for t in x['mentioned_tests']),x['catalogue_retrieval_required'],x['context_dependent'],x['ambiguity_flag'])
def main():
    p=argparse.ArgumentParser();p.add_argument('--authorized',action='store_true');a=p.parse_args()
    if not a.authorized:p.error('Institutional approval required')
    base=Path('data/private'); part=pd.read_csv(base/'sampling_v65/partitions.csv',dtype={'record_id':str}); approved=pd.read_excel(base/'privacy_review.xlsx',sheet_name='Privacy Review',dtype={'record_id':str},keep_default_na=False); approved=approved[approved.privacy_approved.astype(str).str.strip().str.upper().eq('YES')]
    frames=[pd.read_csv(f,dtype={'record_id':str},keep_default_na=False) for f in sorted((base/'annotation_v61/full').glob('batch_*/enquiries_retrieved.csv'))]
    d=pd.concat(frames);d=d[d.retrieval_status.ne('EXTRACTION_FAILED')].drop_duplicates('record_id');d=d.merge(part[part.partition.eq('development')][['record_id']],on='record_id');d=d.merge(approved[['record_id','deidentified_question']],on='record_id');d=d[d.question.eq(d.deidentified_question)]
    d=d.sample(frac=1,random_state=42); cat=d[d.retrieval_status.ne('NOT_APPLICABLE')].head(15); other=d[~d.record_id.isin(cat.record_id)].head(30-len(cat));d=pd.concat([cat,other]).sample(frac=1,random_state=42)
    e=QueryExtractor(); rows=[];start=time.monotonic()
    for i in range(0,len(d),5):
        chunk=d.iloc[i:i+5]
        try:
            outputs=e.extract_many(chunk.question.tolist(),privacy_approved=True,use_cache=False,fallback=False)
        except ValueError:
            for row in chunk.itertuples():
                rows.append(dict(record_id=row.record_id,status='FAILED'))
            pd.DataFrame(rows).to_csv(base/'batch_v71_validation.csv',index=False)
            print('Failed batch; continuing:', i+1, 'to', i+len(chunk),flush=True)
            continue
        for row,new in zip(chunk.itertuples(),outputs):
            old=json.loads(row.extraction_json); a,b=signature(old),signature(new); flags=[x==y for x,y in zip(a,b)];rows.append(dict(record_id=row.record_id,status='OK',intents=flags[0],requests=flags[1],mentioned=flags[2],retrieval_flag=flags[3],context=flags[4],ambiguity=flags[5],all_fields=all(flags),old_json=json.dumps(old),new_json=json.dumps(new)))
        pd.DataFrame(rows).to_csv(base/'batch_v71_validation.csv',index=False)
        print('Attempted',len(rows),flush=True)
    out=pd.DataFrame(rows)
    print('Record outcomes:',out.status.value_counts().to_dict())
    ok=out[out.status.eq('OK')]
    if len(ok): print(ok[['intents','requests','mentioned','retrieval_flag','context','ambiguity','all_fields']].mean().round(3))
    print('Wall seconds:',round(time.monotonic()-start,2))
    print('Review locally: data/private/batch_v71_validation.csv')
if __name__=='__main__':main()
