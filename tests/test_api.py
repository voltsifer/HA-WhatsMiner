"""Protocol tests use real local TCP framing and no Home Assistant dependency."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import struct
import unittest

path = Path(__file__).resolve().parents[1] / 'custom_components/whatsminer_local/api.py'
spec = importlib.util.spec_from_file_location('api', path)
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

SNAPSHOT = {
    'info': {'miner': {'type': 'M60', 'power-limit-set': '3500'},
             'power': {'vin': 220.5, 'iin': 14.8, 'temp0': 41.3}, 'error-code': []},
    'status': {'summary': {'power-realtime': 3268, 'power-limit': 3400, 'board-temperature': [69.6, 70.1, 72.3],
                            'chip-temp-max': 100.3, 'hash-realtime': 101.847},
               'edevs': [{'slot': 2, 'chip-temp-max': 100.6}, {'slot': 0, 'chip-temp-max': 97.4}]},
    'setting': {'power': 3500, 'power-mode': 'normal'},
}


class TestValues(unittest.TestCase):
    def test_auth_official_vector(self):
        self.assertEqual(api.make_token('set.miner.pools', 'abcdefg', 'QbVy1Ou3', 2118015), 'mvmqClRR')

    def test_slot_mapping_and_distinct_power(self):
        values = api.flatten(SNAPSHOT)
        self.assertEqual(values['board-0-chip-temp-max'], 97.4)
        self.assertEqual(values['board-2-chip-temp-max'], 100.6)
        self.assertEqual(values['board-2-temperature'], 72.3)
        self.assertEqual(values['configured-power'], 3500)
        self.assertEqual(values['power-limit'], 3400)
        self.assertEqual(values['power-realtime'], 3268)

    def test_missing_is_not_zero(self):
        data = copy.deepcopy(SNAPSHOT)
        data['status']['summary'].clear()
        data['info'].pop('error-code')
        values = api.flatten(data)
        self.assertIsNone(values['power-realtime'])
        self.assertNotIn('error-count', values)

    def test_errors_and_fallback(self):
        data = copy.deepcopy(SNAPSHOT)
        data['info']['error-code'] = [{'531': 'date', 'reason': 'Slot missing'}, {'532': 'date'}]
        data['setting'].pop('power')
        values = api.flatten(data)
        self.assertEqual(values['configured-power'], 3500)
        self.assertEqual(values['error-codes'], ['531', '532'])
        self.assertEqual(values['error-count'], 2)

    def test_bounds_and_invalid_numbers(self):
        self.assertEqual(api.validate_power(2500.0, 1500, 3500), 2500)
        for value in (True, float('nan'), float('inf'), 'oops', None, 1499, 3501, 2500.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                api.validate_power(value, 1500, 3500)


class TestProtocol(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.tasks = set()
        self.connections = set()
        self.mode = 'normal'
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.client = api.WhatsminerClient('127.0.0.1', self.port, timeout=0.3)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        for writer in self.connections:
            writer.close()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.connections.add(writer)
        try:
            length = struct.unpack('<I', await reader.readexactly(4))[0]
            request = json.loads(await reader.readexactly(length))
            self.requests.append(request)
            cmd = request['cmd']
            if self.mode == 'timeout':
                await reader.read()
                return
            if self.mode == 'oversize':
                writer.write(struct.pack('<I', api.MAX_FRAME + 1))
                await writer.drain()
                return
            if self.mode == 'badjson':
                writer.write(struct.pack('<I', 1) + b'{')
                await writer.drain()
                return
            if self.mode == 'truncated':
                writer.write(struct.pack('<I', 99) + b'{')
                await writer.drain()
                return
            msg = {'get.device.info': SNAPSHOT['info'], 'get.miner.status': SNAPSHOT['status'],
                   'get.miner.setting': SNAPSHOT['setting']}.get(cmd, 'ok')
            if cmd == 'get.device.info' and request.get('param') == 'salt':
                msg = {'salt': 'QbVy1Ou3'}
            code = -4 if cmd.startswith('set.') and self.mode == 'denied' else 0
            if self.mode == 'old_setting' and cmd == 'get.miner.setting':
                code = -2
            response = {'code': code, 'when': 2118015, 'msg': msg, 'desc': cmd}
            if self.mode == 'wrongcmd':
                response['desc'] = 'other'
            payload = json.dumps(response).encode()
            # Heartbeat followed by fragmented header/body, keeping socket open.
            packet = b'\0\0\0\0' + struct.pack('<I', len(payload)) + payload
            for i in range(0, len(packet), 3):
                writer.write(packet[i:i+3])
                await writer.drain()
                await asyncio.sleep(0)
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()
            self.connections.discard(writer)
            self.tasks.discard(task)

    async def test_snapshot_and_no_write(self):
        data = await self.client.read_snapshot()
        self.assertEqual(data, SNAPSHOT)
        self.assertTrue(all(r['cmd'].startswith('get.') for r in self.requests))
        self.assertEqual(self.requests[1]['param'], 'summary+edevs')

    async def test_authenticated_write(self):
        await self.client.set_power(2500, 'super', 'abcdefg')
        write = self.requests[-1]
        self.assertEqual(write['param'], 2500)
        self.assertEqual(write['token'], api.make_token('set.miner.power', 'abcdefg', 'QbVy1Ou3', 2118015))
        self.assertNotIn('password', write)
        self.assertEqual(write['account'], 'super')

    async def test_authenticated_percent_write(self):
        await self.client.set_power_percent(89, 'normal', 'super', 'abcdefg')
        write = self.requests[-1]
        self.assertEqual(write['cmd'], 'set.miner.power_percent')
        self.assertEqual(write['param'], {'percent': 89, 'mode': 'normal'})
        self.assertEqual(write['token'], api.make_token('set.miner.power_percent', 'abcdefg', 'QbVy1Ou3', 2118015))
        with self.assertRaises(ValueError):
            await self.client.set_power_percent(101, 'fast', 'super', 'abcdefg')

    async def test_denied_not_retried(self):
        self.mode = 'denied'
        with self.assertRaises(api.APIError) as ctx:
            await self.client.set_power(2500, 'super', 'password')
        self.assertEqual(ctx.exception.code, -4)
        self.assertEqual(len(self.requests), 2)

    async def test_bad_responses(self):
        for mode in ('oversize', 'badjson', 'truncated', 'wrongcmd', 'timeout'):
            with self.subTest(mode=mode):
                self.mode = mode
                with self.assertRaises(api.WhatsminerError):
                    await self.client.read_snapshot()

    async def test_older_settings_command(self):
        self.mode = 'old_setting'
        data = await self.client.read_snapshot()
        self.assertEqual(data['setting'], {})
        self.assertEqual(api.flatten(data)['configured-power'], 3500)


if __name__ == '__main__':
    unittest.main()
