"""Batch extraction; separate cache, with V6.4 single-record fallback."""
import copy, csv, hashlib, json, time
from pathlib import Path
from llm_query_extractor_v64 import QueryExtractor as Single, PROMPT, SCHEMA, validate, normalize, RateLimitError, BadRequestError

BATCH_PROMPT = PROMPT.replace("Return a JSON object with exactly these keys:", "For each extraction object use exactly these keys:") + '\nFor this request, process each enquiry independently. Return an object with results, an array of objects containing id and extraction. Copy each input id exactly once. Never combine enquiries.'
BATCH_SCHEMA = {'type':'object','additionalProperties':False,'properties':{'results':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'id':{'type':'string'},'extraction':copy.deepcopy(SCHEMA)},'required':['id','extraction']}}},'required':['results']}

def parse_batch(content, questions):
    obj=json.loads(content)
    if not isinstance(obj,dict) or set(obj)!={'results'} or not isinstance(obj['results'],list): raise ValueError('Invalid batch envelope')
    found={}
    for item in obj['results']:
        if not isinstance(item,dict) or set(item)!={'id','extraction'}: raise ValueError('Invalid item')
        k=item['id']
        if not isinstance(k,str) or k not in questions or k in found: raise ValueError('Unknown or duplicate ID')
        found[k]=validate(normalize(item['extraction'],questions[k]))
    if set(found)!=set(questions): raise ValueError('Missing IDs')
    return found

class QueryExtractor(Single):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db.execute('CREATE TABLE IF NOT EXISTS batch_v7 (key TEXT PRIMARY KEY, result TEXT NOT NULL)')
    def extract_many(self, questions, *, privacy_approved=False, use_cache=True, fallback=True):
        if privacy_approved is not True: raise PermissionError('Approval required')
        if not 1<=len(questions)<=5 or any(not isinstance(q,str) or not q.strip() for q in questions): raise ValueError('Use 1–5 nonblank enquiries')
        keys=[hashlib.sha256(json.dumps(['v7',BATCH_PROMPT,BATCH_SCHEMA,self.model,q],sort_keys=True).encode()).hexdigest() for q in questions]
        results={}; pending={}
        for i,(q,key) in enumerate(zip(questions,keys)):
            row=self.db.execute('SELECT result FROM batch_v7 WHERE key=?',(key,)).fetchone() if use_cache else None
            if row: results[str(i)]=validate(json.loads(row[0]))
            else: pending[str(i)]=q
        if pending:
            models=list(dict.fromkeys([self.model,'openai/gpt-oss-120b']))
            for attempt in range(4):
                model=min(models,key=lambda m:max(0,self.cooldown.get(m,0)-time.monotonic()))
                delay=max(0,self.cooldown.get(model,0)-time.monotonic())
                if delay>60: raise RuntimeError('Long API cooldown; stop and resume later')
                if delay: time.sleep(delay)
                started=time.monotonic()
                try:
                    r=self.client.chat.completions.create(model=model,messages=[{'role':'system','content':BATCH_PROMPT},{'role':'user','content':json.dumps({'enquiries':[{'id':k,'enquiry':q} for k,q in pending.items()]},ensure_ascii=False)}],response_format={'type':'json_schema','json_schema':{'name':'lab_batch','strict':True,'schema':BATCH_SCHEMA}},temperature=0,reasoning_effort='low',max_completion_tokens=4096)
                    with Path('data/private/extraction_metrics_v7.csv').open('a',newline='',encoding='utf-8') as f:
                        w=csv.writer(f)
                        if f.tell()==0:w.writerow(['model','records','seconds','prompt_tokens','completion_tokens','total_tokens'])
                        w.writerow([model,len(pending),round(time.monotonic()-started,3),*[getattr(r.usage,k,None) for k in ('prompt_tokens','completion_tokens','total_tokens')]])
                    batch=parse_batch(r.choices[0].message.content,pending)
                    if use_cache:
                        self.db.executemany('INSERT OR REPLACE INTO batch_v7 VALUES (?,?)',[(keys[int(k)],json.dumps(v,ensure_ascii=False)) for k,v in batch.items()]);self.db.commit()
                    results.update(batch);break
                except RateLimitError as exc:
                    try: delay=max(5,float(exc.response.headers.get('retry-after','60')))
                    except ValueError: delay=60
                    self.cooldown[model]=time.monotonic()+delay
                    print(f'Batch rate limit: {model}, {delay:.0f}s',flush=True)
                    if attempt==3 or delay>300:raise
                except BadRequestError as exc:
                    body=exc.body if isinstance(exc.body,dict) else {}; error=body.get('error',body)
                    if error.get('code')!='json_validate_failed':raise
                    print(f"Batch server schema rejection: {model}", flush=True)
                    if attempt < 3:
                        models = models[1:] + models[:1]
                        continue
                    break
                except (ValueError,TypeError,KeyError) as exc:
                    print(f"Batch local validation: {type(exc).__name__}: {str(exc) if type(exc) is ValueError else 'invalid output'}", flush=True)
                    if attempt < 3:
                        models = models[1:] + models[:1]
                        continue
                    break
            if any(k not in results for k in pending):
                if not fallback:raise ValueError('Batch validation failed')
                print('Batch validation failed; single-record fallback',flush=True)
                for k,q in pending.items():
                    if k not in results:results[k]=self.extract(q,privacy_approved=True)
        return [results[str(i)] for i in range(len(questions))]
