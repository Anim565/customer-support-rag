"""Local-only sampling plan; never modifies annotation workbooks."""
from pathlib import Path
import re, unicodedata
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedGroupKFold
import numpy as np
ROOT=Path('data/private/annotation_v61/full')
OUT=Path('data/private/sampling_v65')
def norm(s):
    return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',str(s)).casefold()))
def main():
    if OUT.exists(): raise SystemExit('Sampling plan already exists; preserve it rather than resplit.')
    df=pd.read_excel('data/private/privacy_review.xlsx',sheet_name='Privacy Review',keep_default_na=False,dtype={'record_id':str})
    df=df[df.privacy_approved.astype(str).str.strip().str.upper().eq('YES') & df.deidentified_question.astype(str).str.strip().ne('')].copy().reset_index(drop=True)
    assert df.record_id.is_unique
    frames=[]; done=set()
    for folder in sorted(ROOT.glob('batch_*')):
        raw=pd.read_csv(folder/'enquiries_retrieved.csv',dtype={'record_id':str},keep_default_na=False)
        raw=raw[raw.retrieval_status.ne('EXTRACTION_FAILED')]; done.update(raw.record_id)
        if raw.empty: continue
        ann=pd.read_excel(folder/'annotation_workbook.xlsx',keep_default_na=False)
        mp=pd.read_csv(folder/'annotation_row_map.csv',dtype={'record_id':str})
        ann['excel_row']=range(2,len(ann)+2)
        m=ann.merge(mp,on='excel_row',validate='one_to_one').merge(raw[['record_id','question','source_type']],on='record_id',suffixes=('','_raw'),validate='one_to_one')
        assert len(m)==len(ann)==len(mp)==len(raw) and m.question.eq(m.question_raw).all()
        m['decision_label']=m.decision_label.astype(str).str.strip().str.upper()
        assert m.decision_label.isin(['ANSWER','ESCALATE']).all()
        frames.append(m[['record_id','decision_label','source_type']])
    lab=pd.concat(frames,ignore_index=True); assert lab.record_id.is_unique
    assert set(lab.record_id)<=set(df.record_id)
    # Group exact normalized duplicates and strong character similarities across all eligible texts.
    texts=df.deidentified_question.map(norm).tolist(); parent=list(range(len(df)))
    def find(i):
        while parent[i]!=i: parent[i]=parent[parent[i]]; i=parent[i]
        return i
    def union(i,j):
        a,b=find(i),find(j)
        if a!=b: parent[max(a,b)]=min(a,b)
    seen={}
    for i,t in enumerate(texts):
        if t in seen: union(i,seen[t])
        else: seen[t]=i
    x=TfidfVectorizer(analyzer='char',ngram_range=(2,4),dtype=np.float32).fit_transform(texts)
    for start in range(0,len(df),128):
        sim=(x[start:start+128]@x.T).tocoo()
        for i,j in zip(sim.row[sim.data>=.90],sim.col[sim.data>=.90]): union(start+int(i),int(j))
    df['group_id']=[find(i) for i in range(len(df))]
    real=lab[lab.source_type.str.strip().str.lower().eq('real')].merge(df[['record_id','group_id']],on='record_id',validate='one_to_one')
    splitter=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42)
    tr,te=next(splitter.split(real,real.decision_label,real.group_id))
    test=real.iloc[te]; assert test.decision_label.nunique()==2, 'Test missing a class; inspect grouping before proceeding.'
    protected=set(test.group_id)
    df['partition']=np.where(df.group_id.isin(protected),'protected','development')
    pool=df[~df.record_id.isin(done)&df.partition.eq('development')].copy()
    pool['source']=pool.source_type.str.strip().str.lower()
    patterns=[r'\b(price|cost|charges?|quotation|quote|bei|how much|ngapi)\b',r'\b(tat|turnaround|how long|duration)\b',r'\b(specimen|sample type|which sample|what sample|which tube|volume|fasting|preparation)\b',r'\b(do you (offer|perform|run|do|test)|available|availability|mnafanya)\b']
    pool['score']=sum(pool.deidentified_question.str.contains(p,case=False,regex=True).astype(int) for p in patterns)
    pool=pool.sample(frac=1,random_state=42)
    realpool=pool[pool.source.eq('real') & pool.score.gt(0)].sort_values('score',ascending=False,kind='stable').drop_duplicates('group_id').head(50)
    synth=pool[pool.source.eq('synthetic') & ~pool.group_id.isin(realpool.group_id)].drop_duplicates('group_id').head(50)
    selected=[]
    for i in range(max(len(realpool),len(synth))):
        for p in (realpool,synth):
            if i<len(p): selected.append(p.iloc[i].record_id)
    OUT.mkdir(parents=True)
    df[['record_id','group_id','partition']].to_csv(OUT/'partitions.csv',index=False)
    test[['record_id','decision_label','group_id']].to_csv(OUT/'test_ids.csv',index=False)
    pd.DataFrame({'record_id':selected}).to_csv(OUT/'pilot_ids.csv',index=False)
    print('Protected test counts:',test.decision_label.value_counts().to_dict())
    print('Pilot selection:',len(realpool),'real;',len(synth),'synthetic')
    print('Plan saved:',OUT)
if __name__=='__main__': main()
