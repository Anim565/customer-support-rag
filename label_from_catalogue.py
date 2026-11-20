"""Evidence-based DKL catalogue labeling. Standard library only.
Does not use synthetic labels, evidence_status, evidence_excerpt or triage decisions.
Requires actual catalogue CSV and V4 retrieval audit; does not re-run FAISS.
"""
import argparse,csv,json,re,collections,pathlib

def norm_code(x):
 s=str(x or '').strip()
 return s[:-2] if s.endswith('.0') else s

def nonempty(x):
 return str(x or '').strip().lower() not in ('','nan','none','null','n/a','not available','-')

def fields(row):
 f=row.get('requested_field','').lower(); q=row.get('enquiry','').lower()
 if f=='multi_field':
  found=[]
  if re.search(r'\b(price|cost|rate|charge|how much|bei)\b',q):found.append('price')
  if re.search(r'\b(tat|turnaround|turn around|how long|results take|report|ready)\b',q):found.append('tat')
  if re.search(r'\b(specimen|sample|samp|sample gani)\b',q):found.append('specimen')
  if re.search(r'\b(preparation|prepare|instructions|fasting)\b',q):found.append('instructions')
  return found
 return [f] if f in ('price','tat','specimen','instructions','availability') else []

def value_for(rec,field):
 if field=='price':
  v=rec.get('rate','')
  try:return v if float(v)>0 else ''
  except:return ''
 if field=='tat':return rec.get('reportDays','') # reportDate is not a substitute without validation
 if field=='specimen':return rec.get('specimenReqQuantity','')
 if field=='instructions':return rec.get('instructions','')
 if field=='availability':return 'Listed in public catalogue' # NOT live operational availability
 return ''

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input',required=True);p.add_argument('--catalogue',required=True);p.add_argument('--out',required=True)
 a=p.parse_args()
 with open(a.catalogue,encoding='utf-8-sig',newline='') as f:catalogue=list(csv.DictReader(f))
 bycode={norm_code(r.get('code')):r for r in catalogue if norm_code(r.get('code'))}
 out=[];count=collections.Counter(); flags=collections.Counter()
 with open(a.input,encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   q=r.get('enquiry',''); ftype=r.get('requested_field','').lower(); needed=fields(r)
   code=norm_code(r.get('test_code')); top=norm_code(r.get('top_match_code'))
   rec=bycode.get(code)
   ranktxt=r.get('expected_test_rank','').strip()
   try:rank=int(float(ranktxt))
   except:rank=0
   # Expected test in V4 top 5 is recorded by existing audit. Catalogue lookup verifies content.
   retrieved=bool(rec and 1<=rank<=5 and r.get('expected_test_in_top5','').strip() in ('1','True','true'))
   # Hard clinical/patient categories are defined in synthetic generation, not inferred from original labels.
   safety=ftype in ('clinical_advice','clinical_interpretation','patient_result_status','patient_report_release','report_correction') or r.get('scenario_family')=='patient_or_clinical_safety'
   ambiguous=ftype in ('missing_test','ambiguous_test') or r.get('scenario_family')=='ambiguous_needs_clarification'
   values={k:(value_for(rec,k) if rec and retrieved else '') for k in needed}
   missing=[k for k,v in values.items() if not nonempty(v)]
   if safety:
    decision='ESCALATE'; why='Patient-specific or clinical request: requires authorized human handling'; flags['safety']+=1
   elif ambiguous:
    decision='CLARIFY';why='Test identity is ambiguous; request clarification before binary classification';flags['clarify']+=1
   elif not needed:
    decision='REVIEW';why='Could not reliably identify all information requested';flags['unparsed']+=1
   elif not rec:
    decision='ESCALATE';why='Expected test code absent from active catalogue';flags['missing_catalogue_test']+=1
   elif not retrieved:
    decision='ESCALATE';why='Expected test not verified in V4 top-five retrieval';flags['retrieval_failure']+=1
   elif missing:
    decision='ESCALATE';why='Required catalogue field(s) missing: '+', '.join(missing);flags['missing_fields']+=1
   else:
    decision='ANSWER';why='Expected test found in V4 top five and all requested catalogue fields populated';flags['answer']+=1
   # Special safeguard: operational availability cannot be inferred from a listing.
   if decision=='ANSWER' and 'availability' in needed and re.search(r'\b(today|now|currently|in stock|reagent|running|operational|this weekend)\b',q.lower()):
    decision='ESCALATE';why='Live operational availability cannot be established from the catalogue';flags['live_availability']+=1
   # A retrieved rank > 1 should be checked for confusing alternatives before high-stakes deployment.
   caveat='Expected test is not top-ranked; inspect competing retrieved results' if retrieved and rank>1 else ''
   row=dict(r)
   row.update({'required_fields_verified':json.dumps(needed,ensure_ascii=False),
      'verified_catalogue_test':rec.get('name','') if rec else '',
      'verified_catalogue_code':code if rec else '',
      'v4_expected_test_rank':rank or '',
      'evidence_values':json.dumps(values,ensure_ascii=False),
      'missing_required_fields':'; '.join(missing),
      'evidence_decision':decision,'evidence_justification':why,
      'verification_caveat':caveat,
      'catalogue_evidence_version':str(pathlib.Path(a.catalogue).parent.name)})
   out.append(row);count[decision]+=1
 dest=pathlib.Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
 with open(dest,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0]) if out else [],extrasaction='ignore');w.writeheader();w.writerows(out)
 print('Wrote',len(out),'records to',dest)
 print('Evidence decisions:',dict(count));print('Reasons:',dict(flags))
 print('NOTE: Labels are based on existing V4 top-five audit plus actual catalogue fields, not a fresh retrieval run.')
 print('NOTE: Multi-field parsing, rank>1 matches, and safety categories warrant targeted review before real-world deployment.')
if __name__=='__main__':main()
