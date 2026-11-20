"""Local-only heuristic enquiry grouping and annotation sampling; no training approval."""
import argparse, csv, json, random
from collections import Counter, defaultdict
from pathlib import Path
from extract_enquiries import classify, load_jsonl

FIELDS = ['enquiry_id','group_id','start_record','end_record','speaker','message_count','message_record_numbers','enquiry_text_LOCAL_ONLY','preliminary_category','preliminary_decision','privacy_flags','privacy_status','training_eligible','review_is_customer_enquiry','review_boundary_correct','review_category','review_decision','review_privacy_cleared','review_notes_NO_IDENTIFIERS']
REVIEW_FIELDS = FIELDS + ['sampling_stratum','review_original_context_locally']

def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction='ignore');w.writeheader();w.writerows(rows)

def privacy_index(path):
    out=defaultdict(set)
    if path.exists():
        for r in load_jsonl(path):
            try: n=int(r.get('record_number',0))
            except (TypeError,ValueError): continue
            if n>0: out[(str(r.get('group_id','')),n)].add(str(r.get('reason','REVIEW')))
    return out

def is_candidate(text):
    return bool(classify(text)[3])

def build(source, output, max_gap=3, sample_size=150, seed=42):
    output.mkdir(parents=True,exist_ok=True)
    messages=list(load_jsonl(source/'messages_anon.jsonl'))
    flags=privacy_index(source/'privacy_review.jsonl')
    groups=defaultdict(list)
    for m in messages:
        groups[str(m.get('group_id',''))].append(m)
    enquiries=[]; negative=[]; stats=Counter(); ambiguous=0
    for group, msgs in sorted(groups.items()):
        msgs.sort(key=lambda x:int(x.get('record_number',0)))
        # Blocks are contiguous same-speaker runs. Do not infer thread links across speakers.
        runs=[]; current=[]
        for m in msgs:
            n=int(m.get('record_number',0))
            if current and (m.get('speaker')!=current[-1].get('speaker') or n-int(current[-1].get('record_number',0))>max_gap):
                runs.append(current); current=[]
            current.append(m)
        if current:runs.append(current)
        for run in runs:
            hits=[m for m in run if is_candidate(m.get('text',''))]
            if not hits:
                # Negative review samples: no content in aggregate report.
                for m in run:
                    negative.append({'group_id':group,'record_number':int(m.get('record_number',0)),'speaker':m.get('speaker',''),'text_LOCAL_ONLY':m.get('text',''),'sampling_stratum':'EXCLUDED_MESSAGE','review_is_customer_enquiry':'','review_privacy_cleared':'','review_notes_NO_IDENTIFIERS':''})
                continue
            # Split when multiple candidate messages are separated by a long gap of non-candidates.
            # Otherwise retain same-speaker messages together for human boundary review.
            chunks=[]; chunk=[]; last_hit_idx=None
            for idx,m in enumerate(run):
                if is_candidate(m.get('text','')) and last_hit_idx is not None and idx-last_hit_idx>3 and chunk:
                    chunks.append(chunk);chunk=[]
                chunk.append(m)
                if is_candidate(m.get('text','')):last_hit_idx=idx
            if chunk:chunks.append(chunk)
            for chunk in chunks:
                if not any(is_candidate(m.get('text','')) for m in chunk):continue
                classifications=[classify(m.get('text','')) for m in chunk]
                categories=[c[0] for c in classifications if c[3]]
                decisions=[c[1] for c in classifications if c[3]]
                # Escalation precedence; all labels remain preliminary.
                decision='ESCALATE' if 'ESCALATE' in decisions else ('REVIEW' if 'REVIEW' in decisions else 'ANSWER_CANDIDATE')
                category=next((x for x in ['PATIENT_CASE_FOLLOWUP','OPERATIONAL_REQUEST','SPECIMEN_PREPARATION','PRICING','TURNAROUND_TIME','TEST_AVAILABILITY','TEST_INFORMATION','POSSIBLE_INTERNAL','GENERAL_ENQUIRY'] if x in categories),'GENERAL_ENQUIRY')
                numbers=[int(m.get('record_number',0)) for m in chunk]
                flagged=sorted(set().union(*(flags.get((group,n),set()) for n in numbers)))
                enquiry={
                    'enquiry_id':f'ENQ2_{len(enquiries)+1:06d}', 'group_id':group,
                    'start_record':min(numbers),'end_record':max(numbers),
                    'speaker':chunk[0].get('speaker',''), 'message_count':len(chunk),
                    'message_record_numbers':';'.join(map(str,numbers)),
                    'enquiry_text_LOCAL_ONLY':'\n'.join(str(m.get('text','')) for m in chunk),
                    'preliminary_category':category,'preliminary_decision':decision,
                    'privacy_flags':';'.join(flagged),'privacy_status':'UNVALIDATED',
                    'training_eligible':'NO','review_is_customer_enquiry':'',
                    'review_boundary_correct':'','review_category':'','review_decision':'',
                    'review_privacy_cleared':'','review_notes_NO_IDENTIFIERS':''}
                enquiries.append(enquiry)
                stats['grouped_messages']+=len(chunk)
                if len(chunk)>1:stats['multi_message_groups']+=1
                if len(set(categories))>1:ambiguous+=1
    rng=random.Random(seed)
    # Stratify by preliminary category to avoid only sampling general enquiries.
    buckets=defaultdict(list)
    for e in enquiries:buckets[e['preliminary_category']].append(e)
    for values in buckets.values():rng.shuffle(values)
    chosen=[]
    while len(chosen)<min(sample_size,len(enquiries)) and any(buckets.values()):
        for category in sorted(buckets):
            if buckets[category] and len(chosen)<sample_size:
                chosen.append({**buckets[category].pop(),'sampling_stratum':'CANDIDATE_ENQUIRY','review_original_context_locally':'YES'})
    rng.shuffle(negative)
    neg_take=min(50,len(negative))
    write_csv(output/'enquiries_LOCAL_ONLY.csv',enquiries,FIELDS)
    write_csv(output/'annotation_sample_LOCAL_ONLY.csv',chosen,REVIEW_FIELDS)
    write_csv(output/'excluded_review_sample_LOCAL_ONLY.csv',negative[:neg_take],list(negative[0]) if negative else ['group_id','record_number','speaker','text_LOCAL_ONLY','sampling_stratum','review_is_customer_enquiry','review_privacy_cleared','review_notes_NO_IDENTIFIERS'])
    report={
      'source_messages':len(messages),'candidate_enquiry_groups_NOT_VERIFIED':len(enquiries),
      'grouped_messages_including_context':stats['grouped_messages'],
      'multi_message_groups':stats['multi_message_groups'],
      'groups_with_multiple_candidate_categories':ambiguous,
      'preliminary_categories':dict(Counter(e['preliminary_category'] for e in enquiries)),
      'preliminary_decisions':dict(Counter(e['preliminary_decision'] for e in enquiries)),
      'groups_with_privacy_flags':sum(bool(e['privacy_flags']) for e in enquiries),
      'annotation_sample':len(chosen),'excluded_message_review_sample':neg_take,
      'limitations':['Same-speaker adjacency is not proof of one enquiry; boundaries require review.',
      'Different speakers are never joined; responses and follow-ups may require manual linkage.',
      'Original timestamp information is not used; grouping relies on export record order.',
      'Candidate groups may contain non-enquiry context or multiple distinct requests.',
      'All message text remains LOCAL ONLY, UNVALIDATED and NOT TRAINING ELIGIBLE.',
      'Review excluded messages to estimate missed enquiries.']}
    (output/'reconstruction_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,default=Path('data/processed/whatsapp_v2'))
    p.add_argument('--output',type=Path,default=Path('data/processed/enquiries_v2'))
    p.add_argument('--max-gap',type=int,default=3)
    p.add_argument('--sample-size',type=int,default=150)
    a=p.parse_args()
    build(a.input,a.output,a.max_gap,a.sample_size)
