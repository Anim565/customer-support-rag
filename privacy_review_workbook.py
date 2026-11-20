"""Create/review a LOCAL privacy audit workbook. Never commit workbook or message data."""
import argparse, csv, json, random
from collections import Counter
from pathlib import Path

HEADERS = ['sample_id','sampling_stratum','group_id','record_number','privacy_flags','anonymized_text',
           'original_checked_locally','original_contains_identifier','identifier_detected_by_pipeline',
           'identifier_remaining_in_anonymized_text','flag_appropriate','laboratory_meaning_preserved',
           'review_decision','reviewer_notes']
OPTIONS = {
    'original_checked_locally': ['Yes','No'],
    'original_contains_identifier': ['Yes','No','Uncertain'],
    'identifier_detected_by_pipeline': ['Yes','No','Partial','Not applicable','Uncertain'],
    'identifier_remaining_in_anonymized_text': ['Yes','No','Uncertain'],
    'flag_appropriate': ['Yes','No','Uncertain'],
    'laboratory_meaning_preserved': ['Yes','No','Uncertain'],
    'review_decision': ['Pass','Correct and recheck','Exclude','Uncertain'],
}

def read_records(folder):
    with (folder/'messages_anon.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    flags={}
    with (folder/'privacy_review.jsonl').open(encoding='utf-8') as f:
        for line in f:
            item=json.loads(line)
            reason=item.get('reason','')
            if reason.startswith('POSSIBLE_IDENTIFIER:'):
                flags[(item['group_id'],str(item['record_number']))]=reason.split(':',1)[1].split(',')
    return rows,flags

def create(folder,out,seed):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    rows,flags=read_records(folder)
    pools={'NAME_CUE_ANY':[], 'CAPITALIZED_ONLY':[], 'NEITHER':[]}
    for row in rows:
        fs=flags.get((row['group_id'],str(row['record_number'])),[])
        if 'NAME_CUE_UNRESOLVED' in fs: key='NAME_CUE_ANY'
        elif 'CAPITALIZED_PHRASE_REVIEW' in fs: key='CAPITALIZED_ONLY'
        else: key='NEITHER'
        pools[key].append((row,fs))
    rng=random.Random(seed)
    targets={'NAME_CUE_ANY':60,'CAPITALIZED_ONLY':60,'NEITHER':80}
    if any(len(pools[k])<n for k,n in targets.items()):
        raise ValueError('Insufficient rows in a sampling stratum: '+str({k:len(v) for k,v in pools.items()}))
    selected=[]
    for stratum,n in targets.items():
        selected.extend((stratum,r,f) for r,f in rng.sample(pools[stratum],n))
    rng.shuffle(selected)
    wb=Workbook(); ws=wb.active; ws.title='Review_200'
    ws.append(HEADERS)
    for i,(stratum,row,fs) in enumerate(selected,1):
        ws.append([f'S{i:03d}',stratum,row['group_id'],int(row['record_number']),','.join(fs),
                   row['text'],'No','','','','','','',''])
    ws.freeze_panes='G2'; ws.auto_filter.ref=f'A1:N{len(selected)+1}'
    widths={'A':12,'B':23,'C':15,'D':16,'E':33,'F':85,'G':25,'H':27,'I':29,'J':36,'K':23,'L':30,'M':24,'N':48}
    for col,width in widths.items(): ws.column_dimensions[col].width=width
    for cell in ws[1]:
        cell.fill=PatternFill('solid',fgColor='17324D');cell.font=Font(color='FFFFFF',bold=True)
        cell.alignment=Alignment(wrap_text=True,vertical='center')
    ws.row_dimensions[1].height=45
    for row in ws.iter_rows(min_row=2):
        for cell in row: cell.alignment=Alignment(vertical='top',wrap_text=True)
        for cell in row[6:]: cell.fill=PatternFill('solid',fgColor='FFF3D6')
        ws.row_dimensions[row[0].row].height=56
    for col,choices in OPTIONS.items():
        ix=HEADERS.index(col)+1
        letter=ws.cell(1,ix).column_letter
        dv=DataValidation(type='list',formula1='"'+','.join(choices)+'"',allow_blank=True)
        dv.error='Choose an option from the dropdown';dv.errorTitle='Invalid choice';dv.showErrorMessage=True
        ws.add_data_validation(dv);dv.add(f'{letter}2:{letter}{len(selected)+1}')
    guide=wb.create_sheet('Instructions')
    guidance=[
        ['LOCAL PRIVACY VALIDATION | 200 RECORDS',''],
        ['Purpose','Audit residual identifiers, detector flags, and preservation of enquiry meaning.'],
        ['Data handling','Confidential: do not upload, email, share publicly, or commit this workbook.'],
        ['Sample','60 NAME_CUE_ANY; 60 CAPITALIZED_ONLY (without name cue); 80 NEITHER. Seed: '+str(seed)],
        ['Original source check','Use group_id and record_number to find the original locally; do not paste original text into this workbook.'],
        ['Original contains identifier','Yes if original has identifiable patient, staff, phone, email, case number, etc.'],
        ['Identifier detected by pipeline','Yes if all relevant original identifiers were detected/redacted; Partial if some; No if missed.'],
        ['Identifier remaining','Yes if any identifying information remains in the anonymized text.'],
        ['Flag appropriate','Yes if the message warranted privacy review, even if successfully redacted.'],
        ['Meaning preserved','No if important laboratory enquiry meaning was lost or distorted.'],
        ['Review decision','Pass only if safe and meaning is preserved; otherwise correct/recheck or exclude.'],
        ['Important limitation','Original identifiers can be checked only by an authorized reviewer with access to original exports.'],
        ['Analysis','Run this script with --summarize after completing reviews; only aggregate metrics are printed.'],
        ['Privacy','Exact timestamps are omitted from this workbook, but clinical narratives can still be identifying.'],
    ]
    for r in guidance: guide.append(r)
    guide.column_dimensions['A'].width=31;guide.column_dimensions['B'].width=110
    for c in guide[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='17324D')
    for row in guide.iter_rows():
        for c in row:c.alignment=Alignment(wrap_text=True,vertical='top')
        guide.row_dimensions[row[0].row].height=32
    out.parent.mkdir(parents=True,exist_ok=True)
    wb.save(out)
    print(json.dumps({'workbook_created':str(out),'sample_size':len(selected),'strata':targets,
                      'source_messages':len(rows),'warning':'LOCAL CONFIDENTIAL DATA - DO NOT UPLOAD OR COMMIT'},indent=2))

def summarize(path):
    from openpyxl import load_workbook
    wb=load_workbook(path,read_only=True,data_only=True);ws=wb['Review_200']
    records=[dict(zip(HEADERS,row)) for row in ws.iter_rows(min_row=2,values_only=True)]
    reviewed=[r for r in records if r['original_checked_locally']=='Yes']
    complete=[r for r in reviewed if all(r[k] in OPTIONS[k] and r[k] not in ('Uncertain',) for k in
              ['original_contains_identifier','identifier_detected_by_pipeline','identifier_remaining_in_anonymized_text',
               'flag_appropriate','laboratory_meaning_preserved','review_decision'])]
    counts={k:dict(Counter(r[k] for r in complete)) for k in OPTIONS if k!='original_checked_locally'}
    flagged=[r for r in complete if r['sampling_stratum']!='NEITHER']
    precision_den=len(flagged)
    precision_num=sum(r['flag_appropriate']=='Yes' for r in flagged)
    identifier_cases=[r for r in complete if r['original_contains_identifier']=='Yes']
    recall_num=sum(r['identifier_detected_by_pipeline']=='Yes' for r in identifier_cases)
    print(json.dumps({'sample_size':len(records),'originals_checked':len(reviewed),'fully_completed':len(complete),
          'sample_strata':dict(Counter(r['sampling_stratum'] for r in records)),
          'flag_appropriateness_in_flagged_sample':{'yes':precision_num,'evaluated':precision_den},
          'complete_identifier_detection_among_identifier_cases':{'yes':recall_num,'evaluated':len(identifier_cases)},
          'review_field_counts':counts,
          'caution':'Stratified sample; percentages are not population estimates without weighting. Manual judgements are not a gold standard.'},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',default='data/processed/whatsapp_v2')
    p.add_argument('--output',default='data/processed/whatsapp_v2/validation/privacy_review_200.xlsx')
    p.add_argument('--seed',type=int,default=20261115);p.add_argument('--summarize',action='store_true')
    args=p.parse_args()
    if args.summarize:summarize(Path(args.output))
    else:create(Path(args.input),Path(args.output),args.seed)
