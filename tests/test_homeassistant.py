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
        self.patch.stop()
        self.flow_patch.stop()
        self.network_patch.stop()
        await self.hass.async_stop()
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
            'host': '192.0.2.10', 'port': 4433, 'scan_interval': 30, 'enable_control': True})
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
            'host': '192.0.2.10', 'port': 4433, 'scan_interval': 60, 'enable_control': True})
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
        await coordinator.async_refresh()
        await self.hass.async_block_till_done()
        self.assertEqual(coordinator.data['power-realtime'], 3268)
        self.assertEqual(coordinator.data['chip-web-status'], 'web_auth_required')
        self.assertEqual(self.hass.states.get(maps[0].entity_id).state, 'unavailable')
        self.assertEqual(coordinator.chip_boards, [])

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
