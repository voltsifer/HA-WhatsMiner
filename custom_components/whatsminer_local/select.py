"""Local selection of mode for the next explicit power-percent command."""
from homeassistant.components.select import SelectEntity

from .const import CONF_CONTROL, DOMAIN
from .entity import WhatsminerEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.config.get(CONF_CONTROL):
        async_add_entities([WhatsminerPercentMode(coordinator)])


class WhatsminerPercentMode(WhatsminerEntity, SelectEntity):
    _attr_options = ["normal", "fast"]
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator):
        super().__init__(coordinator, "percent-adjustment-mode", "Power percentage adjustment mode")

    @property
    def available(self):
        return True

    @property
    def current_option(self):
        return self.coordinator.percent_mode

    async def async_select_option(self, option):
        if option not in self.options:
            raise ValueError("Unsupported adjustment mode")
        # This changes only HA's choice; it does NOT issue a miner command.
        self.coordinator.percent_mode = option
        # Deliberately session-local; after reload use configured default (normal).
        self.async_write_ha_state()
