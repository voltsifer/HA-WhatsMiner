"""Explicit, bounded target power commands."""
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import CONF_PASSWORD, PERCENTAGE, UnitOfPower
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

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
        super().__init__(coordinator, "configured-power", "Set power")
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
                raise HomeAssistantError("No fresh configured power reading is available")
            if self.native_value == watts:
                return  # Avoid unnecessary flash writes.
            try:
                await self.coordinator.client.set_power(watts, config[CONF_ACCOUNT], config[CONF_PASSWORD])
            except APIError as err:
                if err.code == -4:
                    raise HomeAssistantError("WhatsMiner denied access: check API Write, account and password") from err
                explanation = f". Miner reported: {err.reason}" if err.reason else ""
                raise HomeAssistantError(f"Power command rejected: code {err.code}{explanation}") from err
            except WhatsminerError as err:
                raise HomeAssistantError("No response received. The command may have succeeded; check configured power before retrying") from err
            await self.coordinator.async_request_refresh()


class WhatsminerPowerPercent(WhatsminerEntity, NumberEntity):
    """A percentage of initial stable power, never a percentage of rated watts."""
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_step = 1
    _attr_native_max_value = 100
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:percent"
    _unrecorded_attributes = frozenset({"last_command"})

    def __init__(self, coordinator):
        super().__init__(coordinator, "power-percent", "Set power percentage")
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
            "last_command": self.coordinator.last_power_percent_command,
        }

    async def async_set_native_value(self, value):
        try:
            percent = validate_power(value, int(self.native_min_value), 100)
        except ValueError as err:
            raise HomeAssistantError("Power percentage must be an integer within the configured limits") from err
        config = self.coordinator.config
        async with self.coordinator.command_lock:
            if not self.available:
                raise HomeAssistantError("The miner is unavailable")
            # Only block while explicitly reported as tuning. Some firmware omits the flag.
            if self.coordinator.data.get("up-freq-finish") == 0:
                raise HomeAssistantError("Wait until frequency tuning has finished")
            if self.native_value == percent:
                return
            mode = self.coordinator.percent_mode
            command = {
                "percent": percent, "mode": mode,
                "power_mode": self.coordinator.data.get("power-mode"),
                "tuning_finished": self.coordinator.data.get("up-freq-finish"),
                "requested_at": dt_util.utcnow().isoformat(), "status": "sending",
            }
            self.coordinator.last_power_percent_command = command
            try:
                await self.coordinator.client.set_power_percent(
                    percent, mode, config[CONF_ACCOUNT], config[CONF_PASSWORD])
            except APIError as err:
                command.update(status="rejected", api_code=err.code, reason=err.reason)
                self.async_write_ha_state()
                explanation = f" Miner reported: {err.reason}." if err.reason else ""
                hint = ""
                if err.reason and "password" in err.reason.lower():
                    hint = (" Check the password for the selected API account (super or user1-user3)"
                            " in Configure: submit Connection settings, then edit Power control."
                            " Web credentials for admin do not establish the password for super."
                            " Manage the selected account password in WhatsminerTool > Password."
                            " The firmware message does not distinguish malformed JSON from a wrong password.")
                elif err.code == -4:
                    hint = " Check API Write, the API account and API password; web authentication is separate."
                elif err.code == -1 and mode == "normal":
                    hint = (" The API returned a generic failure. Normal adjustment requires completed tuning"
                            " and Normal/Low Power mode on air-cooled devices. Check the miner work mode"
                            " and any active protection errors; select fast explicitly if appropriate.")
                raise HomeAssistantError(
                    f"Power percentage command rejected: code {err.code}, percent {percent}, mode {mode}."
                    + explanation + hint) from err
            except WhatsminerError as err:
                command.update(status="unknown", reason="No response received; the command may have succeeded")
                self.async_write_ha_state()
                raise HomeAssistantError("No response received; check the setting before retrying the command") from err
            command.update(status="accepted")
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()
