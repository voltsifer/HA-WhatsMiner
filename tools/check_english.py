#!/usr/bin/env python3
"""Reject Cyrillic text or removed language files in the current tracked project."""
from pathlib import Path
import subprocess
import sys
import unicodedata


def main():
    root = Path(__file__).resolve().parents[1]
    paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
    errors = []
    for name in paths:
        path = root / name
        if not name or not path.is_file():
            continue
        if name in ('README_RU.md', 'custom_components/whatsminer_local/translations/ru.json'):
            errors.append(f'{name}: removed language file is still present')
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for line, value in enumerate(text.splitlines(), 1):
            if any('CYRILLIC' in unicodedata.name(char, '') for char in value):
                errors.append(f'{name}:{line}: unexpected Cyrillic text')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('English-only source check passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
