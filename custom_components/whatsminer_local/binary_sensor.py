"""Device-reported error presence."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import WhatsminerEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([WhatsminerProblem(hass.data[DOMAIN][entry.entry_id])])


class WhatsminerProblem(WhatsminerEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator):
        super().__init__(coordinator, "error-count", "Miner errors")
        self._attr_unique_id += "_problem"

    @property
    def is_on(self):
        value = self.coordinator.data.get("error-count")
        return value > 0 if value is not None else None
