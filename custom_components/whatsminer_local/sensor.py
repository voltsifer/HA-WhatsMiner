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
    "power-realtime": ("Мощность", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "power-5min": ("Мощность за 5 минут", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "power-limit": ("Действующий лимит мощности", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "configured-power": ("Заданная мощность", UnitOfPower.WATT, SensorDeviceClass.POWER),
    "environment-temperature": ("Температура воздуха", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-min": ("Чипы минимум", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-avg": ("Чипы средняя", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-max": ("Чипы максимум", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "hash-average": ("Хешрейт средний", "TH/s", None),
    "hash-realtime": ("Хешрейт текущий", "TH/s", None),
    "hash-1min": ("Хешрейт за 1 минуту", "TH/s", None),
    "hash-15min": ("Хешрейт за 15 минут", "TH/s", None),
    "freq-avg": ("Частота средняя", "MHz", SensorDeviceClass.FREQUENCY),
    "fan-speed-in": ("Вентилятор вход", "rpm", None),
    "fan-speed-out": ("Вентилятор выход", "rpm", None),
    "elapsed": ("Время работы майнинга", UnitOfTime.SECONDS, SensorDeviceClass.DURATION),
    "power-rate": ("Энергоэффективность", "J/TH", None),
    "psu-vin": ("БП напряжение входа", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE),
    "psu-iin": ("БП ток входа", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT),
    "psu-temp0": ("БП температура", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "psu-fanspeed": ("БП вентилятор", "rpm", None),
    "error-count": ("Количество кодов ошибок", None, None),
    "power-percent": ("Процент мощности API", PERCENTAGE, None),
    "up-freq-finish": ("Подбор частоты завершён", None, None),
    "power-mode": ("Режим мощности", None, None),
    "chip-web-status": ("Получение чипов WEB", None, None),
}
BOARD_FIELDS = {
    "temperature": ("температура платы", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-min": ("чипы минимум", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-avg": ("чипы средняя", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "chip-temp-max": ("чипы максимум", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
    "hash-average": ("хешрейт", "TH/s", None),
    "freq": ("частота", "MHz", SensorDeviceClass.FREQUENCY),
    "effective-chips": ("активные чипы", None, None),
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
                    description = (f"Плата {slot} {name}", unit, device_class)
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
            f"Плата {slot} карта чипов WEB", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE))
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
            f"Плата {slot} чип {chip_id} WEB", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE))
