"""Run only on locally reviewed, explicitly approved enquiries."""
import argparse, json, time, shutil
from groq import RateLimitError, APIConnectionError, APIStatusError
from pathlib import Path
from collections import Counter
import pandas as pd
import prepare_annotation_dataset as v1
from prepare_annotation_v5 import Retriever, normalize
from llm_query_extractor_v64 import QueryExtractor

FIELDS={'retrieved_test_name':'test_name','retrieved_test_code':'test_code','retrieved_price':'price','retrieved_tat':'tat','retrieved_specimen':'specimen','retrieved_instructions':'instructions','retrieved_description':'description','retrieved_test_details':'test_details'}

def extract_resilient(extractor, question):
    for attempt in range(3):
        try:
            return extractor.extract(question, privacy_approved=True)
        except RateLimitError as exc:
            header = exc.response.headers.get('retry-after', '')
            try: delay = max(5, float(header))
            except ValueError: delay = min(120, 15 * 2**attempt)
            if delay > 300 or attempt == 2: raise
            print(f'Rate limit: waiting {delay:.0f}s before retrying same record', flush=True)
            time.sleep(delay)
        except APIConnectionError:
            if attempt == 2: raise
            time.sleep(min(60, 5 * 2**attempt))


def export_batch(out, raw, ann, number):
    if not raw: return
    dest = out / f'batch_{number:04d}'
    temp = out / f'.pending_{number:04d}'
    if dest.exists(): raise RuntimeError('Refusing to overwrite existing batch')
    if temp.exists(): shutil.rmtree(temp)
    temp.mkdir()
    frame = pd.DataFrame(raw)
    frame.to_csv(temp/'enquiries_retrieved.csv', index=False, encoding='utf-8-sig')
    with pd.ExcelWriter(temp/'pilot_diagnostics.xlsx', engine='openpyxl') as writer:
        frame.drop(columns=['candidate_evidence_json']).to_excel(writer,index=False)
        for sheet in writer.book.worksheets:
            for cells in sheet.iter_rows():
                for cell in cells:
                    if cell.data_type=='f': cell.data_type='s'
    if ann:
        # Preserve workbook's original column positions; mapping uses original row order.
        v1.create_annotation_workbook(pd.DataFrame(ann).drop(columns=['record_id']),temp/'annotation_workbook.xlsx')
        pd.DataFrame({'excel_row':range(2,len(ann)+2),'record_id':[r['record_id'] for r in ann]}).to_csv(temp/'annotation_row_map.csv',index=False)
    temp.rename(dest)
    print(f'Saved {dest}: {len(ann)} annotation rows; {len(raw)-len(ann)} failures',flush=True)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--limit',type=int); p.add_argument('--seed',type=int,default=100); p.add_argument('--batch-size',type=int,default=50); p.add_argument('--authorized',action='store_true'); a=p.parse_args()
    if not a.authorized: p.error('Confirm institutional authorization with --authorized before external processing.')
    df=pd.read_excel('data/private/privacy_review.xlsx',sheet_name='Privacy Review',keep_default_na=False)
    total=len(df); df=df[df.privacy_approved.astype(str).str.strip().str.upper().eq('YES')].copy()
    df=df[df.deidentified_question.astype(str).str.strip().ne('')]
    print(f'Approved nonblank records: {len(df)}/{total}')
    if not len(df): raise SystemExit('No approved records. Review workbook locally first.')
    if a.limit: df=df.sample(n=min(a.limit,len(df)),random_state=a.seed)
    out=Path('data/private/annotation_v61')/(f'pilot_{a.seed}' if a.limit else 'full'); out.mkdir(parents=True,exist_ok=True)
    docs,index,model,version=v1.load_knowledge_base(); retriever=Retriever(docs,index,model); extractor=QueryExtractor(); cache={}; raw=[]; ann=[]
    total_approved=len(df)
    done=set(); numbers=[]
    for folder in sorted(out.glob('batch_*')):
        numbers.append(int(folder.name.split('_')[-1]))
        prior=pd.read_csv(folder/'enquiries_retrieved.csv',dtype={'record_id':str},keep_default_na=False)
        if set(prior.knowledge_base_version)!={str(version)}: raise SystemExit('Knowledge base changed; do not mix versions.')
        done.update(prior.loc[prior.retrieval_status.ne('EXTRACTION_FAILED'),'record_id'])
    df=df[~df.record_id.astype(str).isin(done)]
    number=max(numbers,default=0)+1; success=total_approved-len(df); failed=0
    print(f'Already exported: {success}; outstanding: {len(df)}',flush=True)
    if a.batch_size<1: p.error('--batch-size must be positive')
    try:
        for num,row in enumerate(df.itertuples(index=False),1):
            q=str(row.deidentified_question); candidates=[]; missing=[]; error=''; x=None
            try: x=extract_resilient(extractor,q)
            except (RateLimitError, APIConnectionError, APIStatusError): raise
            except Exception as exc: error=type(exc).__name__
            if x is None:
                ii=[]; requests=[]; status='EXTRACTION_FAILED'
            else:
                ii=x['intent_group']; requests=x['requested_tests']; status='NOT_APPLICABLE'
                vet=bool(set(normalize(q).split())&{'vet','veterinary','dog','cat','canine','feline'})
                for req in requests:
                    query=req['test_name']; key=(query,vet)
                    if key not in cache: cache[key]=retriever.retrieve(query,vet)
                    if not cache[key]: missing.append(query)
                    for rank,(d,method,score) in enumerate(cache[key],1):
                        c=v1.candidate_evidence(query,d,method,score,rank); c['requested_fields']=req['requested_fields']; candidates.append(c)
                if requests: status='MATCH_FOUND' if not missing else 'PARTIAL_MATCH' if candidates else 'NO_MATCH'
                elif set(ii)&{'PRICE','TAT','SPECIMEN','PREPARATION','AVAILABILITY','TEST_INFORMATION'}: status='TEST_NOT_IDENTIFIED'
            tops=[c for c in candidates if c['rank']==1]
            raw.append(dict(record_id=row.record_id,question=q,source_type=row.source_type,intent_group=';'.join(ii),requested_fields=';'.join(sorted({f for r in requests for f in r['requested_fields']})),search_queries=';'.join(r['test_name'] for r in requests),retrieval_status=status,unmatched_queries=';'.join(missing),retrieved_test_name=';'.join(str(c['test_name']) for c in tops),retrieved_test_code=';'.join(str(c['test_code']) for c in tops),retrieval_method=';'.join(c['retrieval_method'] for c in tops),retrieval_score=';'.join(str(c['retrieval_score']) for c in tops),candidate_count=len(candidates),candidate_evidence_json=json.dumps(candidates,ensure_ascii=False),extraction_json=json.dumps(x,ensure_ascii=False),context_dependent=x['context_dependent'] if x else '',ambiguity_flag=x['ambiguity_flag'] if x else '',extraction_error=error,knowledge_base_version=version))
            # Failed extractions are retained for diagnostics, not silently treated as no retrieval.
            if x is not None:
                r={'question':q,'record_id':row.record_id}; r.update({k:v1.evidence_for_annotation(candidates,v) for k,v in FIELDS.items()}); r.update(decision_label='',label_reason=''); ann.append(r)
            success += int(x is not None); failed += int(x is None)
            if num%10==0: print(f'Done {success}/{total_approved}; failures this run {failed}; remaining {total_approved-success}',flush=True)
            if len(raw)>=a.batch_size:
                export_batch(out,raw,ann,number); number+=1; raw=[]; ann=[]
    except KeyboardInterrupt:
        print('Interrupted by user; saving completed batch.',flush=True)
    except (RateLimitError, APIConnectionError, APIStatusError) as exc:
        print(f'API unavailable ({type(exc).__name__}); saving completed batch. Resume later.',flush=True)
        if isinstance(exc, RateLimitError):
            for k,v in exc.response.headers.items():
                if k.lower().startswith('x-ratelimit-') or k.lower()=='retry-after': print(f'{k}: {v}',flush=True)
    finally:
        export_batch(out,raw,ann,number)
        print(f'Successful: {success}/{total_approved}; failures this run: {failed}; outstanding: {total_approved-success}',flush=True)
        print(out)

if __name__=='__main__': main()
