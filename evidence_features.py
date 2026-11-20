"""Deterministic features shared by training and inference; no fitted state."""
import json
import numpy as np
import pandas as pd
INTENTS='PRICE TAT SPECIMEN PREPARATION AVAILABILITY TEST_INFORMATION PATIENT_SPECIFIC CLINICAL LOGISTICS ORDER_MANAGEMENT OTHER'.split()
FIELDS={'price':['price'],'tat':['tat'],'specimen':['specimen'],'preparation':['instructions'],'test_information':['description','test_details'],'catalogue_listing':['test_code']}
STATUSES='NOT_APPLICABLE MATCH_FOUND TEST_NOT_IDENTIFIED NO_MATCH PARTIAL_MATCH'.split()
def present(v):
    return v is not None and str(v).strip().lower() not in ('','nan','none','null','[]','{}')
def make_features(df):
    rows=[]
    for r in df.to_dict('records'):
        x=json.loads(r['extraction_json']) if isinstance(r['extraction_json'],str) else r['extraction_json']
        cs=json.loads(r['candidate_evidence_json']) if isinstance(r['candidate_evidence_json'],str) else r['candidate_evidence_json']
        req=x['requested_tests']; q=str(r['question']); f={'question':q}
        for i in INTENTS: f['s_intent_'+i]=int(i in x['intent_group'])
        for k in ['context_dependent','ambiguity_flag','catalogue_retrieval_required']: f['s_'+k]=int(x[k])
        f.update(s_intent_count=len(x['intent_group']),s_test_count=len(req),s_mentioned_count=len(x['mentioned_tests']),s_field_count=sum(len(t['requested_fields']) for t in req))
        for k in FIELDS: f['s_field_'+k]=sum(k in t['requested_fields'] for t in req)
        for k in STATUSES: f['r_status_'+k]=int(r['retrieval_status']==k)
        f['r_candidate_count']=len(cs)
        for method in ['lexical','semantic']:
            subset=[c for c in cs if c['retrieval_method']==method]; scores=[float(c['retrieval_score']) for c in subset]; top=[float(c['retrieval_score']) for c in subset if int(c['rank'])==1]
            f['r_'+method+'_count']=len(scores); f['r_'+method+'_max']=max(scores,default=np.nan); f['r_'+method+'_top_mean']=np.mean(top) if top else np.nan
        matched=complete=top_complete=covered=total=0
        for t in req:
            hits=[c for c in cs if c['search_query']==t['test_name']]; fields=t['requested_fields']; total+=len(fields); matched+=bool(hits)
            def has(c,k): return any(present(c.get(v)) for v in FIELDS[k])
            complete+=any(all(has(c,k) for k in fields) for c in hits)
            top_complete+=any(int(c['rank'])==1 and all(has(c,k) for k in fields) for c in hits)
            covered+=sum(any(has(c,k) for c in hits) for k in fields)
        f.update(r_matched_fraction=matched/len(req) if req else np.nan,r_complete_candidate_fraction=complete/len(req) if req else np.nan,r_top_complete_fraction=top_complete/len(req) if req else np.nan,r_field_coverage=covered/total if total else np.nan,r_unmatched_count=len(req)-matched)
        rows.append(f)
    return pd.DataFrame(rows,index=df.index)
