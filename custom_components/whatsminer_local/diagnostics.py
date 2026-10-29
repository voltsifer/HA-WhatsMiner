"""Allowlisted diagnostics: no credentials, salt, IP, MAC, serials or workers."""
from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    info = coordinator.snapshot.get('info', {})
    return {
        'integration_version': '0.5.4',
        'model': info.get('miner', {}).get('type'),
        'firmware': info.get('system', {}).get('fwversion'),
        'api_version': info.get('system', {}).get('api'),
        'last_update_success': coordinator.last_update_success,
        'telemetry': coordinator.data,
        'chip_boards': coordinator.chip_boards,
        'last_power_percent_command': coordinator.last_power_percent_command,
    }
