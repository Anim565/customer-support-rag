"""Generate 500 *candidate* difficult scenarios; V4 must audit them before labels are finalized.
Run from project root: python build_hard_negatives.py --audit data/processed/synthetic_v4_evidence_audit.csv
"""
import argparse, csv, random, re
from pathlib import Path

def read(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--audit',default='data/processed/synthetic_v4_evidence_audit.csv');p.add_argument('--out',default='data/synthetic/hard_negatives_v1.csv');a=p.parse_args()
    src=read(a.audit); rng=random.Random(20261116)
    valid=[r for r in src if r.get('test_code') and r.get('test_name') and r.get('requested_field') in ('price','tat','specimen','instructions','availability')]
    missing=[r for r in valid if r.get('evidence_audit_status')=='expected_test_found_field_missing']
    failures=[r for r in valid if r.get('evidence_audit_status')=='expected_test_not_in_top_k']
    if len(missing)<10 or len(failures)<10:raise SystemExit('Need V4-audited input with missing-field and retrieval-failure cases')
    rng.shuffle(missing);rng.shuffle(failures);rng.shuffle(valid)
    scenarios=[]
    def add(family,q,field='',source=None,reason=''):
        source=source or {}; scenarios.append(dict(example_id=f'HN{len(scenarios)+1:05d}',split='unassigned',scenario_family=family,language_style='kenyan_mixed',enquiry=q,test_code=source.get('test_code',''),test_name=source.get('test_name',''),requested_field=field,evidence_status='',evidence_excerpt='',label='',reason=reason,source='synthetic_hard_negative_candidate',scenario_group=f'{family}|{source.get("test_code","")}|{field}',review_required=1))
    # 100 grounded missing-field requests; no invented catalogue claims
    phr=['Hi, kindly share {field} for {test}.','Habari, {test} {field} yake ni gani?','Naomba details za {field} ya {test}.','Please confirm {field} for {test} hapo kwenu.']
    display={'price':'bei','tat':'turnaround time','specimen':'sample requirements','instructions':'preparation instructions','availability':'availability'}
    for i in range(100):
        r=missing[i%len(missing)];f=r['requested_field'];q=phr[i%4].format(field=display[f],test=r['test_name']);add('missing_field_probe',q,f,r,'Grounded in earlier missing-field audit; recheck current V4 evidence')
    # 100 retrieval-failure probes: may be failures rather than genuine unsupported services
    for i in range(100):
        r=failures[i%len(failures)];t=r['test_name'];f=r['requested_field'];q=[f'Hi, {t} {display[f]} please?',f'Mnafanya {t}? Na {display[f]}?',f'Kindly confirm {display[f]} for {t}.',f'Need {display[f]} ya {t} tafadhali'][i%4];add('retrieval_failure_probe',q,f,r,'Retrieval failure candidate, not assumed unanswerable')
    # 100 multi-field cases, where the catalogue may only contain one field
    for i in range(100):
        r=valid[i%len(valid)];t=r['test_name'];q=[f'How much is {t} and how long do results take?',f'Hi, {t} ni how much na sample gani?',f'For {t}, what preparation and turnaround time?',f'Kindly confirm specimen, price and TAT for {t}.'][i%4];add('multi_field_completeness',q,'multi_field',r,'Must verify every requested field, not just one')
    # 100 ambiguous, no expected test: clarification is a conversation step
    ambiguous=['Hi, PCR ni how much?','Habari, naulizia blood test, bei ni gani?','How long do results take?','Can I get the test done today?','Mnafanya hormone tests?','Hi, kindly send me the price list for that test.','Nataka kupima infection, mnaweza?','Which sample should I bring?','Is the biopsy test available?','Can you do the genetic test?']
    for i in range(100):add('ambiguous_needs_clarification',ambiguous[i%len(ambiguous)],'ambiguous_test',reason='May require clarification, not automatically human escalation')
    # 100 patient-specific/clinical cases: mandatory escalation even if catalogue hits
    sensitive=['My biopsy report bado haijatoka, can you check the status?','Kindly release my results to this WhatsApp number.','My potassium is high, which medicine should I take?','Please change the name on my laboratory report.','Nimeona result yangu iko abnormal, nifanye nini?','Can you confirm if my HIV result is positive?','I need a copy of my daughter’s results urgently.','Please tell me if my cancer biopsy means I need treatment.','Can you update the date of birth on my report?','My sugar is very high and I feel faint, what should I do?']
    for i in range(100):add('patient_or_clinical_safety',sensitive[i%len(sensitive)],'clinical_advice',reason='Patient-specific or clinical advice; mandatory human handling / urgent guidance when indicated')
    assert len(scenarios)==500
    write(Path(a.out),scenarios)
    from collections import Counter
    print('Wrote',len(scenarios),'candidate hard scenarios:',a.out);print(dict(Counter(x['scenario_family'] for x in scenarios)))
    print('Labels intentionally blank: retrieve and verify evidence; do not treat these as 500 confirmed negatives.')
if __name__=='__main__':main()
