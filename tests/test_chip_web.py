"""WEB adapter tests use synthetic payloads; no firmware compatibility claim."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from aiohttp import BasicAuth, ClientSession, web
    from aiohttp.test_utils import TestServer
    from custom_components.whatsminer_local.chip_web import (
        ChipWebClient, ChipWebError, json_pointer, normalize_chips, validate_web_path,
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

CHIPS = {'boards': [{'slot': 0, 'chips': [
    {'id': 'U1', 'temperature': 91.3, 'row': 0, 'column': 0},
    {'id': 'U2', 'temperature': None, 'row': 0, 'column': 1},
]}]}


@unittest.skipUnless(HAS_DEPS, 'Home Assistant/aiohttp not installed')
class TestSchema(unittest.TestCase):
    def test_172_chips_per_board(self):
        payload = {'boards': [
            {'slot': slot, 'chips': [{'id': f'U{i+1}', 'temperature': 80 + slot + i / 100}
                                    for i in range(172)]}
            for slot in (0, 1)
        ]}
        boards = normalize_chips(payload)
        self.assertEqual([len(board['chips']) for board in boards], [172, 172])
        self.assertEqual(boards[0]['chips'][-1]['id'], 'U172')
        self.assertNotEqual(boards[0]['chips'][-1]['temperature'], boards[1]['chips'][-1]['temperature'])

    def test_explicit_ids_and_missing_values(self):
        boards = normalize_chips(CHIPS)
        self.assertEqual(boards[0]['chips'][0]['temperature'], 91.3)
        self.assertIsNone(boards[0]['chips'][1]['temperature'])
        self.assertEqual(boards[0]['chips'][0]['id'], 'U1')

    def test_aggregate_never_expanded_to_chips(self):
        with self.assertRaises(ChipWebError):
            normalize_chips({'boards': [{'slot': 0, 'chip-temp-min': 80, 'chip-temp-max': 100}]})
        with self.assertRaises(ChipWebError):
            normalize_chips({'boards': [{'slot': 0, 'chips': [90, 91, 92]}]})

    def test_duplicate_identity_rejected(self):
        with self.assertRaises(ChipWebError):
            normalize_chips({'boards': [{'slot': 0, 'chips': [{'id': 'U1', 'temperature': 80}, {'id': 'U1', 'temperature': 90}]}]})

    def test_json_pointer(self):
        self.assertEqual(json_pointer({'data': [CHIPS]}, '/data/0'), CHIPS)
        self.assertEqual(json_pointer({'a/b': {'~': 5}}, '/a~1b/~0'), 5)
        with self.assertRaises(ChipWebError):
            json_pointer({}, '/absent')

    def test_endpoint_same_origin(self):
        self.assertEqual(validate_web_path('/observed/endpoint?slot=0'), '/observed/endpoint?slot=0')
        for path in ('http://other/', '//other/', '/\\other', '/data\r\nCookie: secret'):
            with self.assertRaises(ValueError):
                validate_web_path(path)


@unittest.skipUnless(HAS_DEPS, 'Home Assistant/aiohttp not installed')
class TestWebTransport(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.mode = 'normal'
        async def handle(request):
            self.requests.append(request)
            if self.mode == 'redirect':
                raise web.HTTPFound('/login')
            if self.mode == 'html':
                return web.Response(text='<html>secret login page</html>')
            return web.json_response(CHIPS)
        app = web.Application()
        app.router.add_get('/observed', handle)
        app.router.add_get('/login', handle)
        self.server = TestServer(app)
        await self.server.start_server()
        self.session = ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.server.close()

    def client(self, **kwargs):
        return ChipWebClient(self.session, self.server.host, 'http', self.server.port, '/observed', **kwargs)

    async def test_basic_get_and_cookie(self):
        result = await self.client(auth_type='basic', username='tester', password='secret').read_chips()
        self.assertEqual(result, CHIPS['boards'])
        self.assertEqual(self.requests[-1].method, 'GET')
        self.assertEqual(self.requests[-1].headers['Authorization'], BasicAuth('tester', 'secret').encode())
        await self.client(auth_type='cookie', cookie='session=opaque').read_chips()
        self.assertEqual(self.requests[-1].headers['Cookie'], 'session=opaque')

    async def test_expired_auth_no_redirect_followed(self):
        self.mode = 'redirect'
        with self.assertRaisesRegex(ChipWebError, '^web_auth_required$'):
            await self.client(auth_type='cookie', cookie='secret').read_chips()
        self.assertEqual(len(self.requests), 1)

    async def test_login_html_not_data(self):
        self.mode = 'html'
        with self.assertRaisesRegex(ChipWebError, '^web_response_not_json$'):
            await self.client().read_chips()
