"""WEB adapter tests use synthetic payloads; no firmware compatibility claim."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from aiohttp import BasicAuth, ClientSession, web
    from aiohttp.test_utils import TestServer
    from custom_components.whatsminer_local.chip_web import (
        ChipWebClient, ChipWebError, json_pointer, normalize_chips, parse_web_response,
        validate_web_path,
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
        with self.assertRaisesRegex(ChipWebError, '^web_syslog_not_found$'):
            await self.client().read_chips()


@unittest.skipUnless(HAS_DEPS, 'Home Assistant/aiohttp not installed')
class TestLuCIParsing(unittest.TestCase):
    def test_html_with_172_chips_in_each_slot(self):
        from html import escape
        lines = []
        for slot in (2, 0):
            lines.append(f'slot: {slot}, freq: 700, temp: 200, step: 1')
            lines.extend(f'C{i} freq:700 vol:1200 temp:{80 + slot + i / 100} nonce:123 err:0'
                         for i in range(172))
        body = ('<html><textarea class="log" readonly id="syslog">' +
                escape('\n'.join(lines)) + '</textarea></html>').encode()
        boards = parse_web_response(body)
        self.assertEqual([b['slot'] for b in boards], [0, 2])
        self.assertEqual([len(b['chips']) for b in boards], [172, 172])
        self.assertEqual(boards[0]['chips'][0], {'id': 'C0', 'temperature': 80})
        self.assertEqual(boards[0]['chips'][-1]['id'], 'C171')
        self.assertLess(boards[0]['chips'][-1]['temperature'], 200)

    def test_plain_log_and_missing_reading(self):
        boards = parse_web_response(b'slot: 0, temp: 70\nC0 freq: 700 temp: 0\nC1 freq:700 temp:N/A\nC2 freq:700\n')
        self.assertEqual([c['temperature'] for c in boards[0]['chips']], [0, None, None])

    def test_login_page_is_not_chip_data(self):
        with self.assertRaisesRegex(ChipWebError, '^web_auth_required$'):
            parse_web_response(b'<form><input name="luci_password" type="password"></form>')

    def test_duplicate_chip_identity_is_rejected(self):
        with self.assertRaisesRegex(ChipWebError, '^invalid_chip_identity$'):
            parse_web_response(b'slot: 0, temp: 70\nC0 freq:700 temp:90\nC0 freq:700 temp:91')

    def test_html_requires_empty_json_pointer(self):
        with self.assertRaisesRegex(ChipWebError, '^json_pointer_requires_json$'):
            parse_web_response(b'<textarea id="syslog">slot: 0\nC0 temp:90</textarea>', '/data')

    def test_truncated_html_is_not_used(self):
        with self.assertRaisesRegex(ChipWebError, '^web_syslog_not_found$'):
            parse_web_response(b'<textarea id="syslog">slot: 0\nC0 freq:700 temp:90')


@unittest.skipUnless(HAS_DEPS, 'Home Assistant/aiohttp not installed')
class TestLuCISession(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from aiohttp import CookieJar
        self.requests = []
        self.token = 'test-session-one'
        self.reject_password = False
        self.expired_as_html = False

        async def data(request):
            self.requests.append((request.method, request.path))
            if request.cookies.get('sysauth') != self.token:
                if self.expired_as_html:
                    return web.Response(text='<form><input name="luci_password"></form>')
                raise web.HTTPFound('/cgi-bin/luci')
            return web.Response(text='<textarea id="syslog">slot: 0, temp: 70\nC0 freq:700 temp:92.5</textarea>')

        async def login(request):
            self.requests.append((request.method, request.path))
            form = await request.post()
            self.assertEqual(form.get('luci_username'), 'tester')
            self.assertEqual(form.get('luci_password'), 'secret')
            if self.reject_password:
                return web.Response(text='<form><input name="luci_password"></form>')
            response = web.Response(status=302, headers={'Location': '/cgi-bin/luci/admin'})
            response.set_cookie('sysauth', self.token, path='/cgi-bin/luci', httponly=True)
            return response

        app = web.Application()
        app.router.add_get('/cgi-bin/luci/admin/status/btminerapi', data)
        app.router.add_post('/cgi-bin/luci', login)
        self.server = TestServer(app)
        await self.server.start_server()
        self.session = ClientSession(cookie_jar=CookieJar(unsafe=True))
        self.client = ChipWebClient(self.session, self.server.host, 'http', self.server.port,
            '/cgi-bin/luci/admin/status/btminerapi', auth_type='luci', username='tester', password='secret')

    async def asyncTearDown(self):
        await self.session.close()
        await self.server.close()

    async def test_login_then_reuse_ip_cookie(self):
        result = await self.client.read_chips()
        self.assertEqual(result[0]['chips'][0]['temperature'], 92.5)
        self.assertEqual([method for method, _ in self.requests], ['GET', 'POST', 'GET'])
        await self.client.read_chips()
        self.assertEqual([method for method, _ in self.requests].count('POST'), 1)
        self.assertTrue(all(path == '/cgi-bin/luci' for method, path in self.requests if method == 'POST'))

    async def test_expired_cookie_with_login_html_is_renewed_once(self):
        await self.client.read_chips()
        self.token = 'test-session-two'
        self.expired_as_html = True
        result = await self.client.read_chips()
        self.assertEqual(result[0]['chips'][0]['id'], 'C0')
        self.assertEqual([method for method, _ in self.requests].count('POST'), 2)

    async def test_wrong_password_is_not_retried(self):
        self.reject_password = True
        with self.assertRaisesRegex(ChipWebError, '^web_auth_required$'):
            await self.client.read_chips()
        self.assertEqual([method for method, _ in self.requests], ['GET', 'POST'])

    async def test_owned_session_is_closed(self):
        self.client.owns_session = True
        await self.client.async_close()
        self.assertTrue(self.session.closed)


@unittest.skipUnless(HAS_DEPS, 'Home Assistant/aiohttp not installed')
class TestHTTPS(unittest.IsolatedAsyncioTestCase):
    async def test_certificate_verification_requires_explicit_opt_out(self):
        import datetime
        import ipaddress
        import ssl
        import tempfile
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'test-miner')])
        now = datetime.datetime.now(datetime.UTC)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - datetime.timedelta(days=1))
                .not_valid_after(now + datetime.timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
                .sign(key, hashes.SHA256()))
        with tempfile.TemporaryDirectory() as directory:
            cert_path, key_path = Path(directory) / 'cert.pem', Path(directory) / 'key.pem'
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert_path, key_path)
            app = web.Application()
            async def handle(request):
                return web.Response(text='slot: 0\nC0 freq:700 temp:91.5')
            app.router.add_get('/data', handle)
            server = TestServer(app, scheme='https')
            await server.start_server(ssl=context)
            try:
                async with ClientSession() as session:
                    client = ChipWebClient(session, server.host, 'https', server.port, '/data')
                    with self.assertRaisesRegex(ChipWebError, '^web_tls_error$'):
                        await client.read_chips()
                    client.verify_ssl = False
                    self.assertEqual((await client.read_chips())[0]['chips'][0]['temperature'], 91.5)
            finally:
                await server.close()
