"""Conservative evidence triage of combined V4 audits; NOT automatic ground-truth labels."""
import argparse,csv,re
from pathlib import Path
from collections import Counter

def read(path):
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def nonempty(v):return str(v or '').strip().lower() not in ('','nan','none','null','n/a')
def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',default='data/processed/synthetic_evidence_triage.csv');a=p.parse_args()
    rows=read(a.input);out=[]
    for r in rows:
        family=r.get('scenario_family','');field=r.get('requested_field','');status=r.get('evidence_audit_status','');value=r.get('retrieved_field_value','')
        safety=family=='patient_or_clinical_safety' or field in ('clinical_advice','clinical_interpretation','patient_result_status','patient_report_release','report_correction')
        ambiguous=family=='ambiguous_needs_clarification' or field in ('missing_test','ambiguous_test')
        if safety: decision='ESCALATE';why='Patient-specific or clinical safety policy; independent review required';review='yes'
        elif ambiguous:decision='CLARIFY_WORKFLOW';why='Insufficient test identity; ask follow-up before binary decision';review='yes'
        elif family=='multi_field_completeness':decision='REVIEW';why='V4 audit checks only single fields; multi-field evidence not verified';review='yes'
        elif status=='expected_test_and_field_retrieved' and nonempty(value):decision='PROVISIONAL_ANSWER';why='Expected test and one requested field retrieved; verify relevance and sufficiency';review='yes'
        elif status in ('expected_test_not_in_top_k','expected_test_found_field_missing'):decision='PROVISIONAL_ESCALATE';why='V4 did not provide expected evidence; could be retrieval failure or KB gap';review='yes'
        else:decision='REVIEW';why='Unknown field, unexpected evidence or unsupported scenario';review='yes'
        r=dict(r);r.update(proposed_handling=decision,triage_reason=why,expert_review_required=review,final_verified_label='',scenario_group=r.get('scenario_group') or f"{family}|{r.get('test_code','')}|{field}")
        out.append(r)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(out[0]),extrasaction='ignore');w.writeheader();w.writerows(out)
    print('Wrote',len(out),'rows to',path);print('Triage:',dict(Counter(r['proposed_handling'] for r in out)))
    print('No verified labels produced. Do not train directly on provisional triage labels.')
if __name__=='__main__':main()
