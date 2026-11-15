import zipfile
from src.data_preparation.pipeline import reconstruct, classify, scrub, process

def test_multiline_and_system():
    chat = '15/11/2026, 09:30 - Client: CBC\nHbA1c\n15/11/2026, 09:31 - Client joined using this group\'s invite link'
    records, orphan = reconstruct(chat)
    assert len(records) == 2 and not orphan
    assert classify(records[0])[2] == 'CBC\nHbA1c'
    assert classify(records[1])[0] == 'SYSTEM_EVENT'

def test_scrubbing_preserves_tests():
    msg = scrub('Jane Doe: HbA1c case 1234567, call 0712345678', extra_names=['Jane Doe'])
    assert '[PERSON]' in msg and '[PHONE]' in msg and 'HbA1c' in msg and '1234567' not in msg

def test_end_to_end_zip(tmp_path):
    source = tmp_path / 'input'; source.mkdir()
    with zipfile.ZipFile(source / 'chat.zip', 'w') as z:
        z.writestr('_chat.txt', '15/11/2026, 09:30 - Client: CBC test?\n15/11/2026, 09:31 - Lab: Yes')
    result = process(source, tmp_path / 'output')
    assert result['retained_messages'] == 2
    assert (tmp_path / 'output/messages_anon.csv').exists()

def test_iphone():
    assert classify('[15/11/2026, 09:32:00] Client: What is TAT?')[0] == 'USER_MESSAGE'

def test_unknown_preserved_for_review(tmp_path):
    source = tmp_path / 'input'; source.mkdir()
    (source / 'chat.txt').write_text('15/11/2026, 09:30 - Client requested results')
    result = process(source, tmp_path / 'output')
    assert result['UNRECOGNIZED'] == 1
    assert result['review_records'] == 1
