#!/usr/bin/env python3
"""Summarize a saved WEB JSON response without printing string values or headers.

Use the browser Network / Response tab, save only JSON, never a HAR with secrets.
This is an inspection tool, not a firmware-specific temperature decoder.
"""
import argparse
import json
from pathlib import Path


def describe(value, path='', depth=0):
    if depth > 5:
        return
    if isinstance(value, dict):
        # Keys are schema, not string values. Cap output for large datasets.
        keys = list(value)[:30]
        print(f'{path or "/"}: object, keys={keys}')
        for key in keys:
            escaped = str(key).replace('~', '~0').replace('/', '~1')
            if isinstance(value[key], (dict, list)):
                describe(value[key], f'{path}/{escaped}', depth+1)
    elif isinstance(value, list):
        print(f'{path or "/"}: list, length={len(value)}')
        if value:
            describe(value[0], f'{path}/0', depth+1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('json_file', type=Path)
    args = parser.parse_args()
    if args.json_file.stat().st_size > 2*1024*1024:
        parser.error('Response exceeds 2 MiB')
    try:
        payload = json.loads(args.json_file.read_bytes())
    except ValueError:
        parser.error('Expected a JSON response, not HTML or a HAR export')
    if isinstance(payload, dict) and 'log' in payload:
        parser.error('HAR files may contain credentials; save only the endpoint JSON Response')
    describe(payload)


if __name__ == '__main__':
    main()
