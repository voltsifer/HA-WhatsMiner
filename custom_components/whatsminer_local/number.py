"""Explicit, bounded target power commands."""
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import CONF_PASSWORD, PERCENTAGE, UnitOfPower
from homeassistant.exceptions import HomeAssistantError

from .api import APIError, WhatsminerError, validate_power
from .const import (
    CONF_ACCOUNT, CONF_CONTROL, CONF_MAX, CONF_MIN, CONF_PERCENT_MIN,
    CONF_PERCENT_MODE, DEFAULT_PERCENT_MIN, DOMAIN,
)
from .entity import WhatsminerEntity


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if coordinator.config.get(CONF_CONTROL):
        async_add_entities([WhatsminerPower(coordinator), WhatsminerPowerPercent(coordinator)])


class WhatsminerPower(WhatsminerEntity, NumberEntity):
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator):
        super().__init__(coordinator, "configured-power", "Установка мощности")
        self._attr_unique_id += "_control"
        self._attr_native_min_value = coordinator.config[CONF_MIN]
        self._attr_native_max_value = coordinator.config[CONF_MAX]

    @property
    def native_value(self):
        # Read actual configured target, never substitute measured consumption.
        return self.coordinator.data.get(self.key)

    async def async_set_native_value(self, value):
        config = self.coordinator.config
        try:
            watts = validate_power(value, config[CONF_MIN], config[CONF_MAX])
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        async with self.coordinator.command_lock:
            if not self.available:
                raise HomeAssistantError("Нет свежих данных о заданной мощности майнера")
            if self.native_value == watts:
                return  # Avoid unnecessary flash writes.
            try:
                await self.coordinator.client.set_power(watts, config[CONF_ACCOUNT], config[CONF_PASSWORD])
            except APIError as err:
                if err.code == -4:
                    raise HomeAssistantError("WhatsMiner отказал в доступе: проверьте API Write, учётную запись и пароль") from err
                raise HomeAssistantError(f"Команда мощности отклонена: код {err.code}") from err
            except WhatsminerError as err:
                raise HomeAssistantError("Ответ не получен. Команда могла выполниться; проверьте заданную мощность перед повтором") from err
            await self.coordinator.async_request_refresh()


class WhatsminerPowerPercent(WhatsminerEntity, NumberEntity):
    """A percentage of initial stable power, never a percentage of rated watts."""
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_step = 1
    _attr_native_max_value = 100
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:percent"

    def __init__(self, coordinator):
        super().__init__(coordinator, "power-percent", "Установка процента мощности")
        self._attr_unique_id += "_control"
        self._attr_native_min_value = coordinator.config.get(CONF_PERCENT_MIN, DEFAULT_PERCENT_MIN)

    @property
    def available(self):
        # A missing setting must not prevent sending an explicit percentage.
        # No automatic restore/reapply; settings may reset on device reboot.
        return self.coordinator.last_update_success

    @property
    def native_value(self):
        return self.coordinator.data.get(self.key)

    @property
    def extra_state_attributes(self):
        return {
            "adjustment_mode": self.coordinator.percent_mode,
            "volatile": True,
            "reference": "initial_stable_power",
        }

    async def async_set_native_value(self, value):
        try:
            percent = validate_power(value, int(self.native_min_value), 100)
        except ValueError as err:
            raise HomeAssistantError("Процент вне разрешённых границ или не является целым числом") from err
        config = self.coordinator.config
        async with self.coordinator.command_lock:
            if not self.available:
                raise HomeAssistantError("Нет связи с майнером")
            # Only block while explicitly reported as tuning. Some firmware omits the flag.
            if self.coordinator.data.get("up-freq-finish") == 0:
                raise HomeAssistantError("Дождитесь завершения подбора частот")
            if self.native_value == percent:
                return
            try:
                await self.coordinator.client.set_power_percent(
                    percent, self.coordinator.percent_mode, config[CONF_ACCOUNT], config[CONF_PASSWORD])
            except APIError as err:
                raise HomeAssistantError(f"Команда процента мощности отклонена: код {err.code}") from err
            except WhatsminerError as err:
                raise HomeAssistantError("Ответ не получен; проверьте настройку перед повтором команды") from err
            await self.coordinator.async_request_refresh()
