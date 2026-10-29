#!/usr/bin/env python3
"""Read-only probe: python tools/probe.py 192.168.1.100 (Python 3.11+)."""
import argparse
import asyncio
import importlib.util
import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'custom_components/whatsminer_local/api.py'
spec = importlib.util.spec_from_file_location('whatsminer_probe_api', path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('host')
    parser.add_argument('--port', type=int, default=4433)
    args = parser.parse_args()
    try:
        snapshot = await api.WhatsminerClient(args.host, args.port).read_snapshot()
        info = snapshot['info']
        # Deliberately omit salt, network IDs, serial numbers, workers and passwords.
        print(json.dumps({'model': info.get('miner', {}).get('type'),
                          'firmware': info.get('system', {}).get('fwversion'),
                          'api': info.get('system', {}).get('api'),
                          'telemetry': api.flatten(snapshot)}, ensure_ascii=False, indent=2))
    except api.WhatsminerError as err:
        parser.exit(1, f'{err}\nCheck API 3.x, firmware, host and TCP port 4433.\n')


if __name__ == '__main__':
    asyncio.run(main())
