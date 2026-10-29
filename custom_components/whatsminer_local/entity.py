"""Shared entity identity."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class WhatsminerEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_name = name
        info = coordinator.snapshot.get("info", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title, manufacturer="MicroBT",
            model=info.get("miner", {}).get("type"),
            sw_version=info.get("system", {}).get("fwversion"),
        )

    @property
    def available(self):
        return super().available and self.coordinator.data.get(self.key) is not None
