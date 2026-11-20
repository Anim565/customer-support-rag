"""Compare fresh batch outputs with stored V6-era outputs on development only."""
import argparse,json,time
from pathlib import Path
import pandas as pd
from llm_query_extractor_v7 import QueryExtractor

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
        chunk=d.iloc[i:i+5]; outputs=e.extract_many(chunk.question.tolist(),privacy_approved=True,use_cache=False,fallback=False)
        for row,new in zip(chunk.itertuples(),outputs):
            old=json.loads(row.extraction_json); a,b=signature(old),signature(new); flags=[x==y for x,y in zip(a,b)];rows.append(dict(record_id=row.record_id,intents=flags[0],requests=flags[1],mentioned=flags[2],retrieval_flag=flags[3],context=flags[4],ambiguity=flags[5],all_fields=all(flags),old_json=json.dumps(old),new_json=json.dumps(new)))
        print('Compared',len(rows),flush=True)
    out=pd.DataFrame(rows);out.to_csv(base/'batch_v7_validation.csv',index=False);print(out.drop(columns=['record_id','old_json','new_json']).mean().round(3));print('Wall seconds:',round(time.monotonic()-start,2));print('Review disagreements locally: data/private/batch_v7_validation.csv')
if __name__=='__main__':main()
