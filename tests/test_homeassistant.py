"""HA integration checks. Requires Home Assistant; run in a disposable venv."""
import asyncio
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from homeassistant import loader
    from homeassistant.auth import auth_manager_from_config
    from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
    from homeassistant.core import HomeAssistant
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.setup import async_setup_component
    from homeassistant.helpers import entity_registry, device_registry, area_registry
    from custom_components.whatsminer_local.api import APIError
    from custom_components.whatsminer_local.const import DOMAIN
    from custom_components.whatsminer_local.diagnostics import async_get_config_entry_diagnostics
    from test_api import SNAPSHOT
    HAS_HA = True
except ImportError:
    HAS_HA = False


@unittest.skipUnless(HAS_HA, 'Home Assistant is not installed')
class TestHomeAssistant(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        shutil.copytree(Path(__file__).resolve().parents[1] / 'custom_components', Path(self.tmp.name) / 'custom_components')
        self.hass = HomeAssistant(self.tmp.name)
        self.hass.config_entries = ConfigEntries(self.hass, {})
        self.network_patch = patch('homeassistant.components.http.async_get_source_ip', new=AsyncMock(return_value='127.0.0.1'))
        self.network_patch.start()
        loader.async_setup(self.hass)
        await area_registry.async_load(self.hass)
        await device_registry.async_load(self.hass)
        await entity_registry.async_load(self.hass)
        self.hass.auth = await auth_manager_from_config(self.hass, [{"type": "homeassistant"}], [])
        self.patch = patch('custom_components.whatsminer_local.coordinator.WhatsminerClient', autospec=True)
        self.client = self.patch.start().return_value
        self.client.read_snapshot = AsyncMock(return_value=SNAPSHOT)
        self.client.set_power = AsyncMock()
        self.flow_patch = patch('custom_components.whatsminer_local.config_flow.WhatsminerClient', return_value=self.client)
        self.flow_patch.start()
        await async_setup_component(self.hass, 'homeassistant', {})

    async def asyncTearDown(self):
        await self.hass.async_block_till_done()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.state == ConfigEntryState.LOADED:
                await self.hass.config_entries.async_unload(entry.entry_id)
        await self.hass.async_stop()
        self.patch.stop()
        self.flow_patch.stop()
        self.network_patch.stop()
        self.tmp.cleanup()

    async def add_entry(self, control=False, extra=None):
        entry = ConfigEntry(version=1, minor_version=1, domain=DOMAIN, title='Test miner',
            data={'host':'192.0.2.10','port':4433,'scan_interval':30,'enable_control':control,
                  'min_power':1500,'max_power':3500,'account':'super','password':'secret', **(extra or {})},
            options={}, source='user', unique_id='test_mac', discovery_keys={})
        await self.hass.config_entries.async_add(entry)
        await self.hass.async_block_till_done()
        self.assertEqual(entry.state, ConfigEntryState.LOADED)
        return entry

    async def test_readonly_lifecycle(self):
        entry = await self.add_entry()
        self.assertGreater(len(self.hass.states.async_all('sensor')), 20)
        self.assertEqual(len(self.hass.states.async_all('number')), 0)
        self.assertEqual(len(self.hass.states.async_all('binary_sensor')), 1)
        self.client.set_power.assert_not_awaited()
        self.assertTrue(await self.hass.config_entries.async_unload(entry.entry_id))
        self.assertNotIn(entry.entry_id, self.hass.data[DOMAIN])

    async def test_number_bounds_command_and_diagnostics(self):
        entry = await self.add_entry(control=True)
        numbers = self.hass.states.async_all('number')
        self.assertEqual(len(numbers), 2)
        watts_state = next(state for state in numbers if state.attributes.get("unit_of_measurement") == "W")
        entity_id = watts_state.entity_id
        self.assertEqual(watts_state.state, '3500.0')
        self.client.set_power.assert_not_awaited()
        with self.assertRaises(HomeAssistantError):
            await self.hass.services.async_call('number', 'set_value', {'entity_id': entity_id, 'value': 3501}, blocking=True)
        self.client.set_power.assert_not_awaited()
        await self.hass.services.async_call('number', 'set_value', {'entity_id': entity_id, 'value': 2500}, blocking=True)
        self.client.set_power.assert_awaited_once_with(2500, 'super', 'secret')
        # Emulator remains at 3500: do not report optimistic success as a reading.
        self.assertEqual(self.hass.states.get(entity_id).state, '3500.0')
        diag = await async_get_config_entry_diagnostics(self.hass, entry)
        self.assertNotIn('secret', str(diag))
        self.assertNotIn('192.0.2.10', str(diag))
        self.client.set_power.side_effect = APIError(-4)
        with self.assertRaises(HomeAssistantError):
            await self.hass.services.async_call('number', 'set_value', {'entity_id': entity_id, 'value': 2400}, blocking=True)

    async def test_unavailable_and_dynamic_boards(self):
        entry = await self.add_entry()
        coordinator = self.hass.data[DOMAIN][entry.entry_id]
        states = self.hass.states.async_all('sensor')
        initial = len(states)
        values = {**coordinator.data, 'board-4-chip-temp-max': 99.2}
        coordinator.async_set_updated_data(values)
        await self.hass.async_block_till_done()
        self.assertEqual(len(self.hass.states.async_all('sensor')), initial + 1)
        coordinator.async_set_update_error(APIError(-1))
        await self.hass.async_block_till_done()
        self.assertTrue(all(s.state == 'unavailable' for s in self.hass.states.async_all('sensor')))
        coordinator.async_set_updated_data(values)
        await self.hass.async_block_till_done()
        self.assertTrue(any(s.state != 'unavailable' for s in self.hass.states.async_all('sensor')))

    async def test_config_and_options_flow(self):
        flow = await self.hass.config_entries.flow.async_init(DOMAIN, context={'source': 'user'})
        self.assertEqual(flow['step_id'], 'user')
        flow = await self.hass.config_entries.flow.async_configure(flow['flow_id'], {
            'host': '192.0.2.10', 'scan_interval': 30, 'enable_control': True})
        self.assertEqual(flow['step_id'], 'control')
        flow = await self.hass.config_entries.flow.async_configure(flow['flow_id'], {
            'account': 'super', 'password': 'secret', 'min_power': 3500, 'max_power': 1500})
        self.assertEqual(flow['errors']['base'], 'invalid_limits')
        flow = await self.hass.config_entries.flow.async_configure(flow['flow_id'], {
            'account': 'super', 'password': 'secret', 'min_power': 1500, 'max_power': 3500})
        self.assertEqual(flow['type'], 'create_entry')
        await self.hass.async_block_till_done()
        entry = flow['result']
        self.client.set_power.assert_not_awaited()

        options = await self.hass.config_entries.options.async_init(entry.entry_id)
        self.assertEqual(options['step_id'], 'init')
        options = await self.hass.config_entries.options.async_configure(options['flow_id'], {
            'host': '192.0.2.10', 'scan_interval': 60, 'enable_control': True})
        self.assertEqual(options['step_id'], 'control')
        options = await self.hass.config_entries.options.async_configure(options['flow_id'], {
            'account': 'super', 'min_power': 1600, 'max_power': 3400})
        self.assertEqual(options['type'], 'create_entry')
        self.assertEqual(entry.options['password'], 'secret')
        self.assertEqual(entry.options['scan_interval'], 60)
        await self.hass.async_block_till_done()
        self.client.set_power.assert_not_awaited()

    async def test_power_percent_and_local_mode_selection(self):
        entry = await self.add_entry(control=True)
        percent = next(state for state in self.hass.states.async_all('number') if state.attributes.get('unit_of_measurement') == '%')
        mode = self.hass.states.async_all('select')[0]
        await self.hass.services.async_call('select', 'select_option', {'entity_id': mode.entity_id, 'option': 'fast'}, blocking=True)
        self.client.set_power.assert_not_awaited()
        self.client.set_power_percent.assert_not_awaited()
        await self.hass.services.async_call('number', 'set_value', {'entity_id': percent.entity_id, 'value': 89}, blocking=True)
        self.client.set_power_percent.assert_awaited_once_with(89, 'fast', 'super', 'secret')
        coordinator = self.hass.data[DOMAIN][entry.entry_id]
        coordinator.async_set_updated_data({**coordinator.data, 'up-freq-finish': 0})
        await self.hass.async_block_till_done()
        with self.assertRaises(HomeAssistantError):
            await self.hass.services.async_call('number', 'set_value', {'entity_id': percent.entity_id, 'value': 88}, blocking=True)
        self.assertEqual(self.client.set_power_percent.await_count, 1)

    async def test_web_failure_does_not_break_api(self):
        from custom_components.whatsminer_local.chip_web import ChipWebError
        entry = await self.add_entry()
        coordinator = self.hass.data[DOMAIN][entry.entry_id]
        coordinator.web_client = AsyncMock()
        coordinator.web_client.read_chips.return_value = [{'slot': 0, 'chips': [{'id': 'U1', 'temperature': 92}]}]
        await coordinator.async_refresh()
        await self.hass.async_block_till_done()
        self.assertEqual(coordinator.data['web-chip-0-U1'], 92)
        maps = [state for state in self.hass.states.async_all('sensor') if state.attributes.get('source') == 'web']
        self.assertEqual(len(maps), 1)
        self.assertEqual(maps[0].attributes['chips'][0]['id'], 'U1')
        coordinator.web_client.read_chips.side_effect = ChipWebError('web_auth_required')
        coordinator._web_next_poll = 0
        await coordinator.async_refresh()
        await self.hass.async_block_till_done()
        self.assertEqual(coordinator.data['power-realtime'], 3268)
        self.assertEqual(coordinator.data['chip-web-status'], 'web_auth_required')
        self.assertEqual(self.hass.states.get(maps[0].entity_id).state, 'unavailable')
        self.assertEqual(coordinator.chip_boards, [])

    async def test_chip_polling_is_hourly_while_api_and_cached_metrics_continue(self):
        import copy
        clock = [100.0]
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 73,
                                         'voltage_raw': 275, 'errors': 3}]}]
        with patch('custom_components.whatsminer_local.coordinator.monotonic', side_effect=lambda: clock[0]), \
             patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips',
                   new=AsyncMock(return_value=readings)) as read_chips:
            entry = await self.add_entry(extra={'web_chips': True})
            coordinator = self.hass.data[DOMAIN][entry.entry_id]
            self.assertEqual(coordinator.web_interval, 3600)
            self.assertEqual(coordinator.update_interval.total_seconds(), 30)
            read_chips.assert_awaited_once()
            first_update = coordinator.chip_updated_at
            self.assertIsNotNone(first_update)
            initial_api_reads = self.client.read_snapshot.await_count
            board = next(s for s in self.hass.states.async_all('sensor')
                         if s.attributes.get('source') == 'web')
            snapshot = copy.deepcopy(SNAPSHOT)
            snapshot['status']['summary']['power-realtime'] = 2800
            self.client.read_snapshot.return_value = snapshot
            read_chips.return_value = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 79,
                                                            'voltage_raw': 281, 'errors': 4}]}]
            for elapsed in (30, 1800, 3599):
                clock[0] = 100 + elapsed
                await coordinator.async_refresh()
                await self.hass.async_block_till_done()
                self.assertEqual(coordinator.data['power-realtime'], 2800)
                self.assertEqual(coordinator.data['web-chip-0-C0'], 73)
                self.assertEqual(coordinator.chip_updated_at, first_update)
                state = self.hass.states.get(board.entity_id)
                self.assertEqual(state.attributes['updated_at'], first_update)
                self.assertEqual(dict(state.attributes['chips'][0]), readings[0]['chips'][0])
                read_chips.assert_awaited_once()
            self.assertEqual(self.client.read_snapshot.await_count, initial_api_reads + 3)
            clock[0] = 3700
            await coordinator.async_refresh()
            await self.hass.async_block_till_done()
            self.assertEqual(read_chips.await_count, 2)
            self.assertEqual(coordinator.data['web-chip-0-C0'], 79)
            self.assertEqual(self.hass.states.get(board.entity_id).attributes['chips'][0]['errors'], 4)
            self.assertNotEqual(coordinator.chip_updated_at, first_update)

    async def test_failed_hourly_chip_poll_waits_before_retry_and_recovers(self):
        from custom_components.whatsminer_local.chip_web import ChipWebError
        clock = [100.0]
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 73}]}]
        with patch('custom_components.whatsminer_local.coordinator.monotonic', side_effect=lambda: clock[0]), \
             patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips',
                   new=AsyncMock(return_value=readings)) as read_chips:
            entry = await self.add_entry(extra={'web_chips': True})
            coordinator = self.hass.data[DOMAIN][entry.entry_id]
            clock[0] = 3700
            read_chips.side_effect = ChipWebError('web_auth_required')
            await coordinator.async_refresh()
            self.assertEqual(read_chips.await_count, 2)
            self.assertTrue(coordinator.last_update_success)
            self.assertEqual(coordinator.data['chip-web-status'], 'web_auth_required')
            self.assertNotIn('web-chip-0-C0', coordinator.data)
            self.assertEqual(coordinator.chip_boards, [])
            self.assertIsNone(coordinator.chip_updated_at)
            read_chips.side_effect = None
            clock[0] = 7299
            await coordinator.async_refresh()
            self.assertEqual(read_chips.await_count, 2)
            self.assertEqual(coordinator.data['chip-web-status'], 'web_auth_required')
            self.assertEqual(coordinator.data['power-realtime'], 3268)
            clock[0] = 7300
            await coordinator.async_refresh()
            self.assertEqual(read_chips.await_count, 3)
            self.assertEqual(coordinator.data['chip-web-status'], 'ok')
            self.assertEqual(coordinator.data['web-chip-0-C0'], 73)
            self.assertIsNotNone(coordinator.chip_updated_at)

    async def test_chip_interval_option_is_validated_and_does_not_change_api_interval(self):
        import voluptuous as vol
        from custom_components.whatsminer_local.config_flow import web_schema
        credentials = {'web_username': 'admin', 'web_password': 'web-secret'}
        self.assertEqual(web_schema({})(credentials)['web_scan_interval'], 3600)
        for value in (59, 86401):
            with self.assertRaises(vol.Invalid):
                web_schema({})({**credentials, 'web_scan_interval': value})
        with patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips',
                   new=AsyncMock(return_value=[])):
            entry = await self.add_entry(extra={'web_chips': True, 'web_scan_interval': 60})
            coordinator = self.hass.data[DOMAIN][entry.entry_id]
            self.assertEqual(coordinator.web_interval, 60)
            self.assertEqual(coordinator.update_interval.total_seconds(), 30)

    async def test_web_session_is_isolated_and_closed_on_unload(self):
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        from yarl import URL
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 92}]}]
        with patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips', new=AsyncMock(return_value=readings)):
            entry = await self.add_entry(extra={'web_chips': True, 'web_auth': 'luci',
                'web_username': 'tester', 'web_password': 'web-secret'})
        client = self.hass.data[DOMAIN][entry.entry_id].web_client
        self.assertEqual(client.url.path, '/cgi-bin/luci/admin/status/btminerapi')
        self.assertEqual(client.url.scheme, 'https')
        self.assertTrue(client.verify_ssl)
        shared = async_get_clientsession(self.hass)
        self.assertIsNot(client.session, shared)
        url = URL('https://192.0.2.10/cgi-bin/luci')
        client.session.cookie_jar.update_cookies({'sysauth': 'test-token'}, response_url=url)
        self.assertIn('sysauth', client.session.cookie_jar.filter_cookies(url))
        await self.hass.config_entries.async_unload(entry.entry_id)
        self.assertTrue(client.session.closed)
        self.assertFalse(shared.closed)
        self.assertFalse(shared.connector.closed)

    async def test_existing_options_edit_passwords_without_probe(self):
        from custom_components.whatsminer_local.api import WhatsminerError
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 92}]}]
        with patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips', new=AsyncMock(return_value=readings)):
            entry = await self.add_entry(control=True, extra={
                'web_chips': True, 'web_protocol': 'https', 'web_port': 443,
                'web_path': '/cgi-bin/luci/admin/status/btminerapi', 'web_auth': 'basic',
                'web_username': 'old-user', 'web_password': 'old-web-password',
            })
            before = self.client.read_snapshot.await_count
            self.client.read_snapshot.side_effect = WhatsminerError('offline')
            flow = await self.hass.config_entries.options.async_init(entry.entry_id)
            flow = await self.hass.config_entries.options.async_configure(flow['flow_id'], {
                'host': '192.0.2.10', 'scan_interval': 30,
                'enable_control': True, 'web_chips': True,
            })
            self.assertEqual(flow['step_id'], 'control')
            flow = await self.hass.config_entries.options.async_configure(flow['flow_id'], {
                'account': 'super', 'password': 'new-api-password', 'min_power': 1500, 'max_power': 3500,
            })
            self.assertEqual(flow['step_id'], 'web')
            self.assertEqual(self.client.read_snapshot.await_count, before)
            # The final save may reload the entry; restore the emulator for that reload.
            self.client.read_snapshot.side_effect = None
            flow = await self.hass.config_entries.options.async_configure(flow['flow_id'], {
                'web_username': 'new-user', 'web_password': 'new-web-password',
                'web_verify_ssl': False, 'web_scan_interval': 7200,
            })
            self.assertEqual(flow['type'], 'create_entry')
            self.assertEqual(entry.options['password'], 'new-api-password')
            self.assertEqual(entry.options['web_password'], 'new-web-password')
            self.assertEqual(entry.options['web_scan_interval'], 7200)
            self.assertNotIn('web_auth', entry.options)
            self.assertNotIn('web_cookie', entry.options)
            await self.hass.async_block_till_done()
            self.assertEqual(self.hass.data[DOMAIN][entry.entry_id].web_interval, 7200)
            self.client.set_power.assert_not_awaited()
            self.client.set_power_percent.assert_not_awaited()

    async def test_percentage_rejection_exposes_context_and_diagnostic(self):
        entry = await self.add_entry(control=True)
        entity = next(s for s in self.hass.states.async_all('number') if s.attributes.get('unit_of_measurement') == '%')
        self.client.set_power_percent.side_effect = APIError(-1, 'Normal adjustment unavailable')
        with self.assertRaisesRegex(HomeAssistantError, 'code -1, percent 80, mode normal'):
            await self.hass.services.async_call('number', 'set_value', {
                'entity_id': entity.entity_id, 'value': 80}, blocking=True)
        self.client.set_power_percent.assert_awaited_once_with(80, 'normal', 'super', 'secret')
        last = self.hass.states.get(entity.entity_id).attributes['last_command']
        self.assertEqual(last['status'], 'rejected')
        self.assertEqual(last['api_code'], -1)
        self.assertEqual(last['reason'], 'Normal adjustment unavailable')
        diagnostics = await async_get_config_entry_diagnostics(self.hass, entry)
        self.assertEqual(diagnostics['last_power_percent_command']['mode'], 'normal')
        self.assertNotIn('secret', str(diagnostics))

    async def test_options_still_validate_a_changed_host(self):
        from custom_components.whatsminer_local.api import WhatsminerError
        entry = await self.add_entry()
        self.client.read_snapshot.side_effect = WhatsminerError('offline')
        before = self.client.read_snapshot.await_count
        flow = await self.hass.config_entries.options.async_init(entry.entry_id)
        flow = await self.hass.config_entries.options.async_configure(flow['flow_id'], {
            'host': '192.0.2.11', 'scan_interval': 30,
            'enable_control': False, 'web_chips': False,
        })
        self.assertEqual(flow['errors']['base'], 'cannot_connect')
        self.assertEqual(self.client.read_snapshot.await_count, before + 1)
        self.assertEqual(entry.data['host'], '192.0.2.10')

    async def test_password_failure_hint_in_fast_mode_and_no_retry(self):
        entry = await self.add_entry(control=True, extra={'power_percent_mode': 'fast'})
        entity = next(s for s in self.hass.states.async_all('number') if s.attributes.get('unit_of_measurement') == '%')
        self.client.set_power_percent.side_effect = APIError(-1, 'invalid json or password is wrong')
        with self.assertRaisesRegex(HomeAssistantError, 'selected API account.*Configure.*Web credentials') as error:
            await self.hass.services.async_call('number', 'set_value', {
                'entity_id': entity.entity_id, 'value': 80}, blocking=True)
        self.assertIn('mode fast', str(error.exception))
        self.assertNotIn('requires completed tuning', str(error.exception))
        self.client.set_power_percent.assert_awaited_once_with(80, 'fast', 'super', 'secret')
        self.assertEqual(self.hass.states.get(entity.entity_id).attributes['last_command']['reason'],
                         'invalid json or password is wrong')

    async def test_chip_metrics_survive_to_maps_sensors_and_diagnostics(self):
        from custom_components.whatsminer_local.chip_web import ChipWebError
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 73,
            'frequency_raw': 480, 'voltage_raw': 275, 'nonce': 1234, 'errors': 3,
            'crc_errors': 0, 'x': 0, 'x_secondary': 2, 'repeat': 0,
            'pct': 99.3, 'pct_secondary': 96.6}]}]
        with patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips', new=AsyncMock(return_value=readings)):
            entry = await self.add_entry(extra={'web_chips': True})
            coordinator = self.hass.data[DOMAIN][entry.entry_id]
            board = next(s for s in self.hass.states.async_all('sensor') if s.attributes.get('source') == 'web')
            self.assertEqual(dict(board.attributes['chips'][0]), readings[0]['chips'][0])
            registry = entity_registry.async_get(self.hass)
            chip_entry = next(e for e in registry.entities.values() if e.unique_id.endswith('web-chip-0-C0'))
            self.assertIsNotNone(chip_entry.disabled_by)
            registry.async_update_entity(chip_entry.entity_id, disabled_by=None)
            await self.hass.config_entries.async_reload(entry.entry_id)
            await self.hass.async_block_till_done()
            chip = self.hass.states.get(chip_entry.entity_id)
            self.assertEqual(chip.attributes['voltage_raw'], 275)
            self.assertEqual(chip.attributes['crc_errors'], 0)
            self.assertEqual(chip.attributes['pct_secondary'], 96.6)
            diagnostics = await async_get_config_entry_diagnostics(self.hass, entry)
            self.assertEqual(diagnostics['chip_boards'], readings)
            self.assertNotIn('secret', str(diagnostics))
            # A valid non-temperature record is still available in the board map.
            readings[0]['chips'][0] = {'id': 'C0', 'temperature': None, 'errors': 0}
            coordinator = self.hass.data[DOMAIN][entry.entry_id]
            coordinator._web_next_poll = 0
            await coordinator.async_refresh()
            await self.hass.async_block_till_done()
            self.assertEqual(self.hass.states.get(board.entity_id).state, 'unknown')
            self.assertEqual(self.hass.states.get(board.entity_id).attributes['chips'][0]['errors'], 0)
            chip = self.hass.states.get(chip_entry.entity_id)
            self.assertNotIn('voltage_raw', chip.attributes)
            self.assertEqual(chip.state, 'unavailable')
            coordinator.web_client.read_chips = AsyncMock(side_effect=ChipWebError('web_auth_required'))
            coordinator._web_next_poll = 0
            await coordinator.async_refresh()
            await self.hass.async_block_till_done()
            self.assertEqual(self.hass.states.get(board.entity_id).state, 'unavailable')
            self.assertEqual(self.hass.states.get(board.entity_id).attributes.get('chips', []), [])

    async def test_simplified_forms_use_fixed_defaults_and_require_web_credentials(self):
        from custom_components.whatsminer_local.config_flow import connection_schema, web_schema
        self.assertNotIn('port', {str(key) for key in connection_schema({}).schema})
        self.assertEqual({str(key) for key in web_schema({}).schema},
                         {'web_username', 'web_password', 'web_verify_ssl', 'web_scan_interval'})
        flow = await self.hass.config_entries.flow.async_init(DOMAIN, context={'source': 'user'})
        flow = await self.hass.config_entries.flow.async_configure(flow['flow_id'], {
            'host': '192.0.2.10', 'scan_interval': 30, 'enable_control': False, 'web_chips': True})
        self.assertEqual(flow['step_id'], 'web')
        self.assertNotIn('web_auth', {str(key) for key in flow['data_schema'].schema})
        flow = await self.hass.config_entries.flow.async_configure(flow['flow_id'], {
            'web_username': 'admin', 'web_verify_ssl': False})
        self.assertEqual(flow['errors']['base'], 'web_credentials_required')
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 73}]}]
        with patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips', new=AsyncMock(return_value=readings)):
            flow = await self.hass.config_entries.flow.async_configure(flow['flow_id'], {
                'web_username': 'admin', 'web_password': 'web-only-secret', 'web_verify_ssl': False})
            self.assertEqual(flow['type'], 'create_entry')
            await self.hass.async_block_till_done()
            coordinator = self.hass.data[DOMAIN][flow['result'].entry_id]
            self.assertEqual(coordinator.client, self.client)
            client = coordinator.web_client
            self.assertEqual(str(client.url), 'https://192.0.2.10/cgi-bin/luci/admin/status/btminerapi')
            self.assertEqual(client.auth_type, 'luci')
            self.assertEqual(client.username, 'admin')
            self.assertEqual(client.password, 'web-only-secret')
            self.assertFalse(client.verify_ssl)
            self.assertNotIn('password', flow['result'].data)
            self.client.set_power.assert_not_awaited()
            self.client.set_power_percent.assert_not_awaited()

    async def test_upgrade_removes_legacy_web_settings_and_preserves_separate_credentials(self):
        readings = [{'slot': 0, 'chips': [{'id': 'C0', 'temperature': 73}]}]
        with patch('custom_components.whatsminer_local.chip_web.ChipWebClient.read_chips', new=AsyncMock(return_value=readings)):
            entry = await self.add_entry(control=True, extra={
                'web_chips': True, 'web_protocol': 'http', 'web_port': 80,
                'web_path': '/legacy', 'web_auth': 'basic', 'web_cookie': 'old-cookie',
                'web_json_pointer': '/data', 'web_username': 'admin',
                'web_password': 'different-web-password', 'web_verify_ssl': False,
            })
            self.assertEqual(entry.minor_version, 2)
            for key in ('web_protocol', 'web_port', 'web_path', 'web_auth', 'web_cookie', 'web_json_pointer'):
                self.assertNotIn(key, entry.data)
                self.assertNotIn(key, entry.options)
            self.assertEqual(entry.data['password'], 'secret')
            self.assertEqual(entry.data['web_password'], 'different-web-password')
            self.assertFalse(entry.data['web_verify_ssl'])
            self.assertEqual(entry.data['port'], 4433)
            client = self.hass.data[DOMAIN][entry.entry_id].web_client
            self.assertEqual(client.url.scheme, 'https')
            self.assertEqual(client.url.port, 443)
            self.assertEqual(client.url.path, '/cgi-bin/luci/admin/status/btminerapi')
            self.assertEqual(client.auth_type, 'luci')
            self.client.set_power.assert_not_awaited()
            self.client.set_power_percent.assert_not_awaited()

    async def test_migration_cleans_options_without_overwriting_secrets_or_api_port(self):
        from custom_components.whatsminer_local import async_migrate_entry
        entry = await self.add_entry()
        self.hass.config_entries.async_update_entry(entry, minor_version=1, options={
            'web_protocol': 'http', 'web_port': 8080, 'web_auth': 'cookie',
            'web_cookie': 'old-session', 'web_password': 'web-secret',
            'password': 'api-secret', 'port': 4444,
        })
        self.assertTrue(await async_migrate_entry(self.hass, entry))
        self.assertEqual(dict(entry.options), {'web_password': 'web-secret', 'password': 'api-secret', 'port': 4444})
        self.assertTrue(await async_migrate_entry(self.hass, entry))
        self.assertEqual(entry.minor_version, 2)
        await self.hass.async_block_till_done()

    async def test_authentication_transport_failure_does_not_claim_command_sent(self):
        from custom_components.whatsminer_local.api import CommandTransportError
        entry = await self.add_entry(control=True)
        entity = next(s for s in self.hass.states.async_all('number') if s.attributes.get('unit_of_measurement') == '%')
        before = self.client.read_snapshot.await_count
        self.client.set_power_percent.side_effect = CommandTransportError('authentication', 'Device did not return an authentication salt')
        with self.assertRaisesRegex(HomeAssistantError, 'was not sent: authentication preparation failed'):
            await self.hass.services.async_call('number', 'set_value', {'entity_id': entity.entity_id, 'value': 80}, blocking=True)
        last = self.hass.states.get(entity.entity_id).attributes['last_command']
        self.assertEqual(last['status'], 'not_sent')
        self.assertEqual(last['transport_stage'], 'authentication')
        self.assertEqual(self.client.read_snapshot.await_count, before)
        self.client.set_power_percent.assert_awaited_once()

    async def test_unacknowledged_write_is_read_back_without_retry(self):
        import copy
        from custom_components.whatsminer_local.api import CommandTransportError, WhatsminerError
        entry = await self.add_entry(control=True)
        coordinator = self.hass.data[DOMAIN][entry.entry_id]
        entity = next(s for s in self.hass.states.async_all('number') if s.attributes.get('unit_of_measurement') == '%')
        self.client.set_power_percent.side_effect = CommandTransportError('write', 'API closed the connection before a complete response was received')
        for reported, outcome in ((80, 'matches_request'), (95, 'different'), (None, 'unavailable')):
            with self.subTest(reported=reported):
                coordinator.async_set_updated_data({**coordinator.data, 'power-percent': None})
                self.client.set_power_percent.reset_mock()
                before = self.client.read_snapshot.await_count
                snapshot = copy.deepcopy(SNAPSHOT)
                snapshot['setting']['power-percent'] = reported
                self.client.read_snapshot.return_value = snapshot
                self.client.read_snapshot.side_effect = WhatsminerError('offline') if reported is None else None
                with self.assertRaisesRegex(HomeAssistantError, 'no confirmed acknowledgement.*closed the connection') as error:
                    await self.hass.services.async_call('number', 'set_value', {'entity_id': entity.entity_id, 'value': 80}, blocking=True)
                self.assertEqual(self.client.read_snapshot.await_count, before + 1)
                self.client.set_power_percent.assert_awaited_once_with(80, 'normal', 'super', 'secret')
                last = coordinator.last_power_percent_command
                self.assertEqual(last['status'], 'unknown')
                self.assertEqual(last['verification'], outcome)
                self.assertEqual(last['reported_percent_after_error'], reported)
                self.assertNotIn('secret', str(await async_get_config_entry_diagnostics(self.hass, entry)))
                if reported is not None:
                    self.assertIn(f'now reports {reported}%', str(error.exception))
                    self.assertEqual(self.hass.states.get(entity.entity_id).state, f'{reported}.0')
