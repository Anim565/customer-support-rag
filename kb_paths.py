"""Portable knowledge-base resolver for Windows and Linux Docker containers."""
import json
from pathlib import Path


def active_kb_folder(root='data/knowledge_base'):
    root = Path(root).resolve()
    current_file = root / 'current.json'
    manifest = json.loads(current_file.read_text(encoding='utf-8'))
    version = str(manifest['version'])
    if not version or Path(version).name != version or version in ('.', '..'):
        raise ValueError('Unsafe knowledge-base version in current.json')
    folder = root / 'versions' / version
    if not folder.is_dir():
        raise FileNotFoundError(f'Knowledge-base version directory missing: {folder}')
    for filename in ('documents.jsonl', 'catalogue.csv'):
        if not (folder / filename).is_file():
            raise FileNotFoundError(f'Required knowledge-base file missing: {folder / filename}')
    return folder


if __name__ == '__main__':
    print(active_kb_folder())
