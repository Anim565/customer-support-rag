import argparse, json, hashlib, os, sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

API_MARKER = 'standardtestrates'

def records_of(payload):
    if isinstance(payload, list): return payload
    if isinstance(payload, dict):
        for k in ('data', 'results', 'items'):
            v=payload.get(k)
            if isinstance(v,list): return v
            if isinstance(v,dict):
                for key in ('data','results','items'):
                    if isinstance(v.get(key),list): return v[key]
    return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--page', required=True, help='Public website page displaying the test catalogue')
    p.add_argument('--output', default='data/raw/catalogue')
    p.add_argument('--wait-seconds',type=int,default=25)
    p.add_argument('--headed',action='store_true')
    args=p.parse_args()
    root=Path(args.output); root.mkdir(parents=True,exist_ok=True)
    captured=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=not args.headed)
        page=browser.new_page()
        def on_response(resp):
            if API_MARKER not in resp.url.lower() or resp.status!=200: return
            try:
                payload=resp.json(); rows=records_of(payload)
                if rows is not None: captured.append((payload,rows,resp.url))
            except Exception as exc: print('Catalogue response parsing failed:',str(exc),file=sys.stderr)
        page.on('response',on_response)
        print('Opening public catalogue page:',args.page)
        page.goto(args.page,wait_until='domcontentloaded',timeout=60000)
        page.wait_for_timeout(args.wait_seconds*1000)
        browser.close()
    if not captured:
        print('ERROR: No successful catalogue JSON response captured. Previous published snapshot left unchanged.',file=sys.stderr)
        sys.exit(2)
    payload,rows,url=max(captured,key=lambda x:len(x[1]))
    if not rows or not all(isinstance(r,dict) for r in rows):
        sys.exit('ERROR: Empty or unexpected catalogue format. No snapshot published.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    raw=json.dumps(payload,ensure_ascii=False,indent=2)
    digest=hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()
    prior_path=root/'latest_manifest.json'
    prior=json.loads(prior_path.read_text(encoding='utf-8')) if prior_path.exists() else None
    manifest={'extracted_utc':stamp,'source_page':args.page,'response_url':url,'record_count':len(rows),'sha256':digest,'previous_sha256':prior.get('sha256') if prior else None,'changed_since_previous':prior is None or prior.get('sha256')!=digest,'snapshot':f'catalogue_{stamp}.json'}
    (root/manifest['snapshot']).write_text(raw,encoding='utf-8')
    tmp=root/'latest_manifest.json.tmp';tmp.write_text(json.dumps(manifest,indent=2),encoding='utf-8');os.replace(tmp,prior_path)
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
