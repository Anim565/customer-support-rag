"""Build versioned DKL retrieval documents, quality reports and FAISS index.
Usage: python build_knowledge_base.py --input data/raw/catalogue/catalogue_YYYYMMDDTHHMMSSZ.json
Requires: pip install sentence-transformers faiss-cpu numpy
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ['code','name','synonyms','specimenReqQuantity','instructions','description','testDetails','reportDays','reportDate','testDays','rate']
TEXT_FIELDS = ['name','synonyms','specimenReqQuantity','instructions','description','testDetails','reportDays','reportDate','testDays']
MODEL = 'sentence-transformers/all-MiniLM-L6-v2'

def clean(value):
    return re.sub(r'\s+', ' ', str(value)).strip() if value is not None else ''

def normalize(row):
    result = {k: clean(row.get(k)) for k in TEXT_FIELDS}
    result['code'] = clean(row.get('code'))
    result['id'] = row.get('id')
    result['rate'] = row.get('rate')
    result['isSpecial'] = row.get('isSpecial')
    result['displayCriteria'] = row.get('displayCriteria')
    return result

def document(row):
    labels = [('Test code','code'),('Test name','name'),('Also known as','synonyms'),('Specimen','specimenReqQuantity'),('Collection instructions','instructions'),('Description','description'),('Tests included','testDetails'),('Reported turnaround','reportDays'),('Report date','reportDate'),('Testing days','testDays')]
    parts = [f'{label}: {row[key]}' for label,key in labels if row.get(key)]
    if row.get('rate') is not None:
        parts.append(f'Standard price (KES): {row["rate"]}')
    return '\n'.join(parts)

def atomic_json(path, value):
    tmp = path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(tmp,path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',default='data/knowledge_base')
    parser.add_argument('--skip-index',action='store_true',help='Generate QC and documents without embedding dependencies')
    args = parser.parse_args()
    src = Path(args.input)
    if not src.is_file(): parser.error(f'Input file does not exist: {src}')
    raw = src.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
        parser.error('Expected a JSON object with data array')
    records = payload['data']
    if not records or not all(isinstance(r,dict) for r in records):
        parser.error('Catalogue data is empty or contains non-object records')
    if len(records)<1500:
        parser.error(f'Only {len(records)} records: below conservative safety floor of 1500; refusing publication')
    rows = [normalize(r) for r in records]
    codes = [r['code'] for r in rows]
    duplicates = sorted([c for c,n in Counter(codes).items() if n>1])
    if duplicates or any(not r['code'] or not r['name'] for r in rows):
        parser.error(f'Missing name/code or duplicate codes detected: {duplicates[:15]}; refusing publication')
    completeness = {k:{'present':sum(bool(r.get(k)) if k!='rate' else r.get(k) is not None for r in rows),'total':len(rows)} for k in FIELDS}
    issues=[]
    names=Counter(r['name'].casefold() for r in rows)
    for r in rows:
        flags=[]
        for k in ['synonyms','specimenReqQuantity','instructions','description','testDetails']:
            if not r.get(k): flags.append('missing_'+k)
        if names[r['name'].casefold()]>1: flags.append('duplicate_test_name')
        if re.search(r'\b(app testing|test record|dummy test)\b',r['name'],re.I): flags.append('possible_demo_record')
        if flags: issues.append({'code':r['code'],'name':r['name'],'flags':';'.join(flags)})
    entries=[{'code':r['code'],'name':r['name'],'text':document(r),'metadata':r} for r in rows]
    fingerprint=hashlib.sha256(raw).hexdigest()
    version=src.stem.replace('catalogue_','')
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    target=out/'versions'/version
    if target.exists():
        parser.error(f'Version already exists: {target}. Keep versions immutable; use a new extraction snapshot.')
    (out/'versions').mkdir(exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.build-',dir=out/'versions'))
    try:
        with (stage/'documents.jsonl').open('w',encoding='utf-8') as f:
            for e in entries: f.write(json.dumps(e,ensure_ascii=False)+'\n')
        with (stage/'catalogue.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=['id']+FIELDS+['isSpecial','displayCriteria'])
            writer.writeheader();writer.writerows([{k:r.get(k) for k in writer.fieldnames} for r in rows])
        with (stage/'quality_issues.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=['code','name','flags']);writer.writeheader();writer.writerows(issues)
        report={'source_file':str(src),'source_sha256':fingerprint,'record_count':len(rows),'unique_codes':len(set(codes)),'completeness':completeness,'duplicate_names':sum(n>1 for n in names.values()),'records_with_quality_flags':len(issues),'index_created':False}
        if not args.skip_index:
            try:
                import faiss
                import numpy as np
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError('Missing dependencies. Run: python -m pip install sentence-transformers faiss-cpu numpy; or use --skip-index') from exc
            print(f'Encoding {len(entries)} catalogue documents with {MODEL}...',flush=True)
            model=SentenceTransformer(MODEL)
            vectors=model.encode([e['text'] for e in entries],batch_size=32,show_progress_bar=True,normalize_embeddings=True,convert_to_numpy=True)
            vectors=np.ascontiguousarray(vectors,dtype='float32')
            index=faiss.IndexFlatIP(vectors.shape[1]);index.add(vectors)
            faiss.write_index(index,str(stage/'catalogue.faiss'))
            report['index_created']=True
            report['embedding_model']=MODEL
            report['index_size']=index.ntotal
        atomic_json(stage/'quality_report.json',report)
        stage.rename(target)
        # Publish only after all outputs have been written successfully.
        atomic_json(out/'current.json',{'version':version,'path':str(target.resolve()),'source_sha256':fingerprint,'index_created':report['index_created'],'published_utc':datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'version':version,'output':str(target),'records':len(rows),'index_created':report['index_created'],'issues_to_review':len(issues)},indent=2))
    except Exception:
        shutil.rmtree(stage,ignore_errors=True)
        raise

if __name__=='__main__': main()
