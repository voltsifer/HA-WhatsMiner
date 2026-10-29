"""Telemetry sensors, including boards discovered after a restart."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE, UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfPower,
    UnitOfTemperature, UnitOfTime,
)

from .const import DOMAIN
from .entity import WhatsminerEntity

# key -> (display name, unit, device class)
DESCRIPTIONS = {
    "power-realtime": ("Power", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "power-5min": ("Power 5-minute average", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "power-limit": ("Effective power limit", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "configured-power": ("Configured power", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "environment-temperature": ("Ambient temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-min": ("Chip temperature minimum", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-avg": ("Chip temperature average", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-max": ("Chip temperature maximum", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "hash-average": ("Hash rate average", "TH/s", None),
    "hash-realtime": ("Hash rate realtime", "TH/s", None),
    "hash-1min": ("Hash rate 1-minute average", "TH/s", None),
    "hash-15min": ("Hash rate 15-minute average", "TH/s", None),
    "freq-avg": ("Frequency average", "MHz", SensorDeviceClass.FREQUENCY),
    "fan-speed-in": ("Intake fan", "rpm", None),
    "fan-speed-out": ("Exhaust fan", "rpm", None),
    "elapsed": ("Mining uptime", UnitOfTime.SECONDS, SensorDeviceClass.DURATION),
    "power-rate": ("Power efficiency", "J/TH", None),
    "psu-vin": ("PSU input voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    "psu-iin": ("PSU input current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT),
    "psu-temp0": ("PSU temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "psu-fanspeed": ("PSU fan", "rpm", None),
    "error-count": ("Error code count", None, None),
    "power-percent": ("Reported power percentage", PERCENTAGE, None),
    "up-freq-finish": ("Frequency tuning finished", None, None),
    "power-mode": ("Power mode", None, None),
    "chip-web-status": ("Web chip data status", None, None),
}
BOARD_FIELDS = {
    "temperature": ("board temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-min": ("chip temperature minimum", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-avg": ("chip temperature average", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-max": ("chip temperature maximum", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "hash-average": ("hash rate", "TH/s", None),
    "freq": ("frequency", "MHz", SensorDeviceClass.FREQUENCY),
    "effective-chips": ("effective chips", None, None),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    seen = set()

    def discover():
        entities = []
        for key in coordinator.data:
            if key in seen or key == "error-codes":
                continue
            description = DESCRIPTIONS.get(key)
            if key.startswith("web-board-"):
                slot = int(key.split("-")[2])
                entities.append(WhatsminerWebBoardSensor(coordinator, key, slot))
                seen.add(key)
                continue
            if key.startswith("web-chip-"):
                _, _, slot, chip_id = key.split("-", 3)
                entities.append(WhatsminerChipSensor(coordinator, key, slot, chip_id))
                seen.add(key)
                continue
            if key.startswith("board-"):
                _, slot, field = key.split("-", 2)
                if field in BOARD_FIELDS:
                    name, unit, device_class = BOARD_FIELDS[field]
                    description = (f"Board {slot} {name}", unit, device_class)
            if description is not None:
                entities.append(WhatsminerSensor(coordinator, key, description))
                seen.add(key)
        if entities:
            async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class WhatsminerSensor(WhatsminerEntity, SensorEntity):
    def __init__(self, coordinator, key, description):
        name, unit, device_class = description
        super().__init__(coordinator, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if key not in ("power-mode", "chip-web-status"):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)

    @property
    def extra_state_attributes(self):
        if self.key == "error-count":
            return {"codes": self.coordinator.data.get("error-codes", [])}
        return None


class WhatsminerWebBoardSensor(WhatsminerSensor):
    """One state per board; card gets all chip values from unrecorded attributes."""
    _unrecorded_attributes = frozenset({"chips", "updated_at"})

    def __init__(self, coordinator, key, slot):
        super().__init__(coordinator, key, (
            f"Board {slot} web chip map", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE))
        self.slot = slot

    @property
    def extra_state_attributes(self):
        chips = next((b["chips"] for b in self.coordinator.chip_boards if b["slot"] == self.slot), [])
        return {"slot": self.slot, "chips": chips, "updated_at": self.coordinator.chip_updated_at,
                "source": "web", "chip_count": len(chips)}


class WhatsminerChipSensor(WhatsminerSensor):
    # Enable selected chips in the entity registry if individual history is wanted.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, key, slot, chip_id):
        super().__init__(coordinator, key, (
            f"Board {slot} chip {chip_id} web temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE))
