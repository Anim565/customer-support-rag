"""Deterministic catalogue lexical ranker. No test-code-specific ranking overrides."""
import re
from functools import lru_cache

STOP = set('how much does do is are the a an of for what which where when can i we you need needed required require specimen sample collection instructions cost price pricing turnaround time take long test testing please tell me about to get my and with'.split())
ALIASES = {'full blood count':'fbc','complete blood count':'fbc','full haemogram':'fbc','total blood count':'fbc','cbc':'fbc','fhg':'fbc','tbc':'fbc','thyroid function test':'tft','erythrocyte sedimentation rate':'esr','c reactive protein':'crp','glycosylated hemoglobin':'hba1c','glycosylated haemoglobin':'hba1c','hemoglobin a1c':'hba1c','haemoglobin a1c':'hba1c','hba1c':'hba1c','a1c':'hba1c','high sensitivity':'hs','high sensitive':'hs','veterinary':'vet','reticulocytes':'retic','reticulocyte':'retic','peripheral blood film':'pbf','prolactin':'prolactin'}
# Match phrases before individual tokens; never rewrite substrings of another word.
def norm(s):
    s=str(s or '').casefold().replace('β','beta')
    s=re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])',' ',s) if False else s
    return re.sub(r'[^a-z0-9]+',' ',s).strip()
def canonical(s):
    s=' '+norm(s)+' '
    for phrase,alias in sorted(ALIASES.items(),key=lambda x:-len(x[0])):
        s=re.sub(r'\b'+re.escape(phrase)+r'\b',alias,s)
    return ' '.join(s.split())
def tokens(s):return set(canonical(s).split())
@lru_cache(maxsize=20000)
def _aliases(name,syn):
    parts=[name]+[p.strip() for p in re.split(r'[;|]',syn) if p.strip()]
    parts.extend(re.findall(r'\(([^()]{2,50})\)',name+';'+syn))
    return frozenset(canonical(p) for p in parts if canonical(p))
def field_aliases(record):
    m=record.get('metadata',{})
    name=str(record.get('name',''))
    syn=str(m.get('synonyms') or '')
    return _aliases(name,syn)

def rank_lexical(query,docs,k=5):
    q=canonical(query);qt=set(q.split())-STOP
    if not qt:return []
    core=' '.join(w for w in q.split() if w not in STOP)
    qset=set(core.split())
    vet='vet' in qset or bool(qset & {'animal','dog','cat'})
    modifiers={'esr','retic','pbf','poct','hs','receptor','antibody','pooled','serial','clearance','plus','profile','culture','urinalysis','viral','qualitative','quantitative','free','total','dihydroxy','troponin'}
    scored=[]
    for i,r in enumerate(docs):
        name=str(r.get('name','')); n=canonical(name);nt=set(n.split())
        aliases=field_aliases(r)
        syn_tokens=[set(a.split()) for a in aliases]
        code=str(r.get('code',''))
        if core==canonical(code):score=10000
        else:
            # Requiring every query concept to appear somewhere in the name or a synonym
            # avoids matching on irrelevant descriptive text.
            matching=[a for a in aliases if qset.issubset(set(a.split()))]
            if not matching:continue
            score=100
            if core==n:score+=1200
            if n.startswith(core+" "):score+=160
            if core in aliases:score+=900
            if qset.issubset(nt):score+=180
            # Prefer the shortest complete matching name or alias, not a large profile.
            score+=110*len(qset)/max(len(nt),1)
            score+=90*len(qset)/max(min(len(a.split()) for a in matching),1)
            extra=nt-qset-{'only'}
            # An unrequested modifier must not win merely because its name mentions the assay.
            score-=125*len(extra & modifiers)
            if 'hs' in nt and 'hs' not in qset:score-=220
            if 'no' in nt and ('urinalysis' in qset and 'urinalysis' in nt):score-=500
            if 'mycobacterial' in nt and 'mycobacterial' not in qset:score-=160
            score-=8*len(extra)
            if 'only' in nt and not (qset & modifiers):score+=100
            if ('+' in name or 'profile' in nt or 'package' in nt) and not(qset & {'profile','package','plus','esr','retic','pbf','antibody','urinalysis'}):score-=110
            if 'vet' in nt and not vet:score-=600
            if vet and 'vet' not in nt:score-=600
            if vet and 'vet' in nt:score+=130
            # Recognize 'with' and 'and' as joining components, not as stopword-only noise.
            # This is already captured by the required tokens in qset.
        scored.append((score,i))
    scored.sort(key=lambda x:(-x[0],str(docs[x[1]].get('code',''))))
    return [(docs[i],float(s)) for s,i in scored[:k]]
