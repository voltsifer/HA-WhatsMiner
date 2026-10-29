#!/usr/bin/env python3
"""Fill HACS repository identity after the real GitHub owner is known. No network."""
import argparse
import json
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', help='Exact OWNER/HA-WhatsMiner slug')
    parser.add_argument('--maintainer', help='GitHub username responsible for issues (default: owner)')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/HA-WhatsMiner', args.repository):
        parser.error('Use the real OWNER/HA-WhatsMiner slug')
    owner = args.repository.split('/')[0]
    maintainer = args.maintainer or owner
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', maintainer):
        parser.error('Invalid maintainer username')
    path = args.root / 'custom_components/whatsminer_local/manifest.json'
    manifest = json.loads(path.read_text())
    manifest['documentation'] = f'https://github.com/{args.repository}'
    manifest['issue_tracker'] = f'https://github.com/{args.repository}/issues'
    manifest['codeowners'] = [f'@{maintainer}']
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Updated local manifest for {args.repository}. No repository created or published.')


if __name__ == '__main__':
    main()
