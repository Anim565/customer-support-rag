"""V5 pilot and annotation pipeline. Requires prepare_annotation_dataset.py (V1)."""
import argparse, json, re
from collections import Counter
from pathlib import Path
from difflib import SequenceMatcher
import pandas as pd
import prepare_annotation_dataset as v1
from ranking_v4 import canonical, rank_lexical, field_aliases, STOP

CAT = {'PRICE','TAT','SPECIMEN','PREPARATION','AVAILABILITY','TEST_INFORMATION'}
EXTRA = {
 'PRICE': r'\b(pricing|lab rates|cheapest|bei)\b',
 'TAT': r'\b(reporting time|reporting period|ready in|results take|turnaround)\b',
 'PATIENT_SPECIFIC': r'\b(following up|follow up|pending case|updates? on (?:this|the) (?:this )?(?:case|patient)|waiting for .*results|release .*results|case number|case_no)\b',
 'LOGISTICS': r'\b(rider|parcel|delivered|delivery|receiv(?:ed|ing|e)|sending|pick(?:ed)? up|receipt|courier)\b',
 'ORDER_MANAGEMENT': r'\b(add .*to|confirm which to log|cancel .*test|register .*test|sending .*for|amend .*order)\b',
 'AVAILABILITY': r'\b(unable to find .*system|do you carry|is .*offered|mnafanya)\b',
 'CLINICAL': r'\b(check my hormones|which tests? (?:do i need|should)|what tests? (?:do i need|should))\b',
}

def intents(q):
    s=set(v1.detect_intents(q))
    s.update(k for k,p in EXTRA.items() if re.search(p,q,re.I|re.S))
    if 'LOGISTICS' in s and not re.search(r'which (?:sample|tube)|what (?:sample|specimen)|sample type|volume|how many ml|stability|requirements',q,re.I): s.discard('SPECIMEN')
    if 'PATIENT_SPECIFIC' in s and not re.search(r'\b(tat|turnaround|reporting time|how long does)\b',q,re.I): s.discard('TAT')
    if len(s)>1: s.discard('OTHER')
    return sorted(s)

# Catalogue terminology normalization, not test-code overrides.
NORMALIZE = [(r'\btriple testing\b','triple screen'),(r'\bquad screen\b','quadruple screen'),(r'\bigg\s+(?:to|against)\s+aspergillus(?:\s+fumigatus)?\b','aspergillus antibody igg'),(r'\bena panel\b','ena panel')]
GENERIC = v1.GENERIC_ALIASES | set('urgent fasting random basic extended advanced small large block antibody antibodies antigen automated qualitative quantitative igg iga igm ige ihc marker markers screen screening test normal positive negative blood testing edta'.split())

def normalize(q):
    q=re.sub(r'\[[A-Z_]+\]',' ',q)
    for p,r in NORMALIZE: q=re.sub(p,r,q,flags=re.I)
    return canonical(q)

def is_vet(d): return bool(set(canonical(d['name']).split()) & {'vet','veterinary','canine','feline'})

class Retriever:
    def __init__(self,docs,index,model):
        self.docs=docs; self.index=index; self.model=model
        self.alias={}; self.names={}
        for d in docs:
            name=canonical(d['name']); self.names[str(d['code'])]=name
            aliases=set(field_aliases(d))|{name}
            # Initial acronym in catalogue names (e.g. ESR).
            first=name.split()[0] if name else ''
            if 2<=len(first)<=6: aliases.add(first)
            for a in aliases:
                if a and a not in GENERIC and len(a)>=2 and re.search('[a-z]',a): self.alias.setdefault(a,[]).append(d)
        self.pattern=re.compile(r'\b(?:'+'|'.join(re.escape(a) for a in sorted(self.alias,key=len,reverse=True))+r')\b')

    def queries(self,q,ii):
        if not set(ii)&CAT:
            # Bare test names are potentially catalogue enquiries, unlike general conversation.
            if ii==['OTHER'] and normalize(q) in self.alias: pass
            else: return [],'NOT_APPLICABLE'
        # For mixed operational/catalogue messages use catalogue-request clauses only.
        parts=re.split(r'[\n;]+|(?<=[.!?])\s+',q)
        if set(ii)&{'PATIENT_SPECIFIC','LOGISTICS','ORDER_MANAGEMENT'}:
            relevant=[p for p in parts if set(intents(p))&CAT and not (set(intents(p))&{'PATIENT_SPECIFIC','LOGISTICS','ORDER_MANAGEMENT'} and not set(intents(p))&{'PRICE','PREPARATION','AVAILABILITY','TEST_INFORMATION'})]
            if relevant: q=' '.join(relevant)
        text=normalize(q)
        # Prefer a longer contextual phrase to an isolated immunoglobulin class.
        found=list(dict.fromkeys(m.group() for m in self.pattern.finditer(text)))
        if 'aspergillus antibody igg' in text: found=[a for a in found if a not in {'aspergillus','igg'}]; found.append('aspergillus antibody igg')
        if not found:
            for a in ('ige','igg','igm','iga'):
                if re.search(r'\b'+a+r'\b',text): found.append(a)
        if found: return list(dict.fromkeys(found)),'IDENTIFIED'
        cleaned=normalize(v1.clean_search_query(q))
        meaningful=[w for w in cleaned.split() if w not in STOP|GENERIC|{'results','ready','available','team','kindly','advise','report','you','patient','slot','book','check','lini','ngapi','bei'}]
        return ([' '.join(meaningful)],'FALLBACK_QUERY') if meaningful else ([], 'TEST_NOT_IDENTIFIED')

    def retrieve(self,query,vet=False):
        pool=[d for d in self.docs if vet or not is_vet(d)]
        q=canonical(query); qt=set(q.split())
        if q in {'ige','igg','igm','iga'}:
            total=[d for d in pool if q in self.names[str(d['code'])].split() and ('total' in self.names[str(d['code'])].split() or self.names[str(d['code'])] in {q,'immunoglobulin '+q})]
            if total: return [(d,'lexical',1000.) for d in total[:5]]
            return []
        hits=rank_lexical(q,pool,20)
        # Allow exact contiguous name phrases even when catalogue synonyms are incomplete.
        bycode={str(d['code']):(d,s) for d,s in hits}
        for d in pool:
            name=self.names[str(d['code'])]; nt=set(name.split())
            if qt and qt<=nt:
                score=300+200*len(qt)/len(nt)
                if name.startswith(q+' ') or name==q: score+=250
                if q in self.alias and d in self.alias[q]: score+=100
                if str(d['code']) not in bycode: bycode[str(d['code'])]=(d,score)
        # Prefer exact name content over broad synonyms and unrelated profiles.
        ranked=[]
        for d,s in bycode.values():
            n=self.names[str(d['code'])]; nt=set(n.split())
            if qt<=nt: s+=500
            if n==q: s+=500
            ranked.append((d,'lexical',float(s)))
        ranked.sort(key=lambda x:(-x[2],str(x[0]['code'])))
        if ranked:
            best=ranked[0][2]
            return [r for r in ranked if r[2]>=best*0.8][:5]
        # Semantic fallback only when lexical fails; require spelling/token evidence.
        vec=self.model.encode([query],normalize_embeddings=True,convert_to_numpy=True).astype('float32')
        scores,idx=self.index.search(vec,min(50,self.index.ntotal))
        out=[]
        for score,i in zip(scores[0],idx[0]):
            if i<0 or score<0.45: continue
            d=self.docs[int(i)]
            if not vet and is_vet(d): continue
            tokens=set(self.names[str(d['code'])].split())
            if not any(len(a)>=3 and any(SequenceMatcher(None,a,b).ratio()>=0.8 for b in tokens) for a in qt): continue
            out.append((d,'semantic',float(score)))
            if len(out)==5: break
        return out

def main():
    p=argparse.ArgumentParser();p.add_argument('--limit',type=int);p.add_argument('--seed',type=int,default=42);a=p.parse_args()
    df=pd.read_excel(v1.INPUT_FILE)[['question','source_type']].copy()
    if df.question.isna().any() or df.question.astype(str).str.strip().eq('').any(): raise ValueError('Blank questions')
    if df.question.str.casefold().str.replace(r'\s+',' ',regex=True).str.strip().duplicated().any(): raise ValueError('Duplicate questions')
    if a.limit: df=df.sample(n=min(a.limit,len(df)),random_state=a.seed)
    out=Path('data/processed/annotation_v5')/(f'pilot_{a.seed}' if a.limit else 'full');out.mkdir(parents=True,exist_ok=True)
    docs,index,model,version=v1.load_knowledge_base(); r=Retriever(docs,index,model); cache={}; raw=[]; ann=[]
    fields={'retrieved_test_name':'test_name','retrieved_test_code':'test_code','retrieved_price':'price','retrieved_tat':'tat','retrieved_specimen':'specimen','retrieved_instructions':'instructions','retrieved_description':'description','retrieved_test_details':'test_details'}
    for num,(q,source) in enumerate(df.itertuples(index=False,name=None),1):
        ii=intents(q); queries,status=r.queries(q,ii); candidates=[]; missing=[]
        vet=bool(set(normalize(q).split())&{'vet','veterinary','dog','cat','canine','feline'})
        for query in queries:
            key=(query,vet)
            if key not in cache: cache[key]=r.retrieve(query,vet)
            if not cache[key]: missing.append(query)
            for rank,(d,method,score) in enumerate(cache[key],1): candidates.append(v1.candidate_evidence(query,d,method,score,rank))
        if queries: status='MATCH_FOUND' if candidates and not missing else 'PARTIAL_MATCH' if candidates else 'NO_MATCH'
        tops=[c for c in candidates if c['rank']==1]
        raw.append(dict(question=q,source_type=source,intent_group=';'.join(ii),requested_fields=';'.join(v1.requested_fields(ii)),search_queries=';'.join(queries),retrieval_status=status,unmatched_queries=';'.join(missing),retrieved_test_name=';'.join(c['test_name'] for c in tops),retrieved_test_code=';'.join(c['test_code'] for c in tops),retrieval_method=';'.join(c['retrieval_method'] for c in tops),retrieval_score=';'.join(str(c['retrieval_score']) for c in tops),candidate_count=len(candidates),candidate_evidence_json=json.dumps(candidates,ensure_ascii=False),knowledge_base_version=version))
        row={'question':q};row.update({k:v1.evidence_for_annotation(candidates,v) for k,v in fields.items()});row.update(decision_label='',label_reason='');ann.append(row)
        if num%50==0: print(f'Processed {num}/{len(df)}',flush=True)
    raw=pd.DataFrame(raw);ann=pd.DataFrame(ann)
    raw.to_csv(out/'enquiries_retrieved.csv',index=False,encoding='utf-8-sig')
    audit=raw.drop(columns=['candidate_evidence_json']).copy();audit.to_excel(out/'pilot_diagnostics.xlsx',index=False)
    v1.create_annotation_workbook(ann.sample(frac=1,random_state=42),out/'annotation_workbook.xlsx')
    summary=dict(total_enquiries=len(raw),retrieval_status=raw.retrieval_status.value_counts().to_dict(),intent_distribution=dict(Counter(i for s in raw.intent_group for i in s.split(';'))),knowledge_base_version=version,automatic_decision_labels=False)
    (out/'intent_retrieval_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary,indent=2));print(out)

if __name__=='__main__': main()
