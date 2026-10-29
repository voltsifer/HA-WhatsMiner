"""UI setup and options. Connection validation performs only GET commands."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import WhatsminerClient, WhatsminerError
from .chip_web import validate_web_path
from .const import (
    ACCOUNTS, CONF_ACCOUNT, CONF_CONTROL, CONF_MAX, CONF_MIN,
    DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN, CONF_PERCENT_MIN, CONF_PERCENT_MODE,
    DEFAULT_PERCENT_MIN, CONF_WEB_CHIPS, CONF_WEB_PROTOCOL, CONF_WEB_PORT, CONF_WEB_PATH,
    CONF_WEB_POINTER, CONF_WEB_AUTH, CONF_WEB_USERNAME, CONF_WEB_PASSWORD, CONF_WEB_COOKIE,
    CONF_WEB_VERIFY_SSL, DEFAULT_WEB_PATH, DEFAULT_WEB_PROTOCOL, DEFAULT_WEB_PORT,
)


def connection_schema(values):
    return vol.Schema({
        vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
        vol.Required(CONF_PORT, default=values.get(CONF_PORT, DEFAULT_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_SCAN_INTERVAL, default=values.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
        vol.Required(CONF_CONTROL, default=values.get(CONF_CONTROL, False)): bool,
        vol.Required(CONF_WEB_CHIPS, default=values.get(CONF_WEB_CHIPS, False)): bool,
    })


def control_schema(values):
    fields = {
        vol.Required(CONF_ACCOUNT, default=values.get(CONF_ACCOUNT, "super")): vol.In(ACCOUNTS),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    }
    fields[vol.Required(CONF_PERCENT_MIN, default=values.get(CONF_PERCENT_MIN, DEFAULT_PERCENT_MIN))] = vol.All(vol.Coerce(int), vol.Range(min=0, max=99))
    fields[vol.Required(CONF_PERCENT_MODE, default=values.get(CONF_PERCENT_MODE, "normal"))] = vol.In(("normal", "fast"))
    # No invented model-dependent power limits.
    for key in (CONF_MIN, CONF_MAX):
        marker = vol.Required(key, default=values[key]) if key in values else vol.Required(key)
        fields[marker] = vol.All(vol.Coerce(int), vol.Range(min=1, max=100000))
    return vol.Schema(fields)


async def probe(values):
    values[CONF_HOST] = values[CONF_HOST].strip().lower()
    return await WhatsminerClient(values[CONF_HOST], values[CONF_PORT]).read_snapshot()


def control_error(values):
    if not values.get(CONF_PASSWORD):
        return "password_required"
    if values[CONF_MIN] >= values[CONF_MAX]:
        return "invalid_limits"
    return None


def web_schema(values):
    fields = {
        vol.Required(CONF_WEB_PROTOCOL, default=values.get(CONF_WEB_PROTOCOL, DEFAULT_WEB_PROTOCOL)): vol.In(("http", "https")),
        vol.Required(CONF_WEB_PORT, default=values.get(CONF_WEB_PORT, DEFAULT_WEB_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_WEB_PATH, default=values.get(CONF_WEB_PATH, DEFAULT_WEB_PATH)): str,
        vol.Optional(CONF_WEB_POINTER, default=values.get(CONF_WEB_POINTER, "")): str,
        vol.Required(CONF_WEB_AUTH, default=values.get(CONF_WEB_AUTH, "luci")): vol.In(("none", "basic", "cookie", "luci")),
        vol.Optional(CONF_WEB_USERNAME, default=values.get(CONF_WEB_USERNAME, "")): str,
        vol.Required(CONF_WEB_VERIFY_SSL, default=values.get(CONF_WEB_VERIFY_SSL, True)): bool,
    }
    for key in (CONF_WEB_PASSWORD, CONF_WEB_COOKIE):
        fields[vol.Optional(key)] = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
    return vol.Schema(fields)


class WebFlowMixin:
    async def _finish(self):
        if self._pending.get(CONF_WEB_CHIPS):
            return await self.async_step_web()
        return self.async_create_entry(title=getattr(self, "_title", ""), data=self._pending)

    async def async_step_web(self, user_input=None):
        errors = {}
        if user_input is not None:
            combined = {**self._pending, **user_input}
            for key in (CONF_WEB_PASSWORD, CONF_WEB_COOKIE):
                if not user_input.get(key):
                    combined[key] = self._pending.get(key, "")
            try:
                validate_web_path(combined[CONF_WEB_PATH])
                pointer = combined.get(CONF_WEB_POINTER, "")
                if pointer and not pointer.startswith("/"):
                    raise ValueError("Invalid JSON pointer")
            except ValueError:
                errors["base"] = "invalid_web_endpoint"
            if combined[CONF_WEB_AUTH] in ("basic", "luci") and not (combined.get(CONF_WEB_USERNAME) and combined.get(CONF_WEB_PASSWORD)):
                errors["base"] = "web_credentials_required"
            if combined[CONF_WEB_AUTH] == "cookie" and not combined.get(CONF_WEB_COOKIE):
                errors["base"] = "web_credentials_required"
            if not errors:
                return self.async_create_entry(title=getattr(self, "_title", ""), data=combined)
        return self.async_show_form(step_id="web", data_schema=web_schema({**self._pending, **(user_input or {})}), errors=errors)


class WhatsminerConfigFlow(WebFlowMixin, config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WhatsminerOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                snapshot = await probe(user_input)
            except (WhatsminerError, AttributeError, KeyError, TypeError):
                errors["base"] = "cannot_connect"
            else:
                info = snapshot["info"]
                identifier = info.get("network", {}).get("mac") or f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                await self.async_set_unique_id(str(identifier).lower())
                self._abort_if_unique_id_configured()
                self._pending = user_input
                self._title = f"HA-WhatsMiner {user_input[CONF_HOST]}"
                if user_input[CONF_CONTROL]:
                    return await self.async_step_control()
                return await self._finish()
        return self.async_show_form(step_id="user", data_schema=connection_schema(user_input or {}), errors=errors)

    async def async_step_control(self, user_input=None):
        errors = {}
        if user_input is not None:
            combined = {**self._pending, **user_input}
            if error := control_error(combined):
                errors["base"] = error
            else:
                self._pending = combined
                return await self._finish()
        return self.async_show_form(step_id="control", data_schema=control_schema(user_input or {}), errors=errors)


class WhatsminerOptionsFlow(WebFlowMixin, config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        current = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            try:
                snapshot = await probe(user_input)
                old = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                old_mac = old.snapshot.get("info", {}).get("network", {}).get("mac") if old else None
                new_mac = snapshot["info"].get("network", {}).get("mac")
                if old_mac and new_mac and old_mac.lower() != new_mac.lower():
                    errors["base"] = "different_device"
            except (WhatsminerError, AttributeError, KeyError, TypeError):
                errors["base"] = "cannot_connect"
            if not errors:
                self._pending = {**current, **user_input}
                if user_input[CONF_CONTROL]:
                    return await self.async_step_control()
                # Overwrite old password so disabling control does not preserve it in options.
                self._pending[CONF_PASSWORD] = ""
                return await self._finish()
        return self.async_show_form(step_id="init", data_schema=connection_schema(user_input or current), errors=errors)

    async def async_step_control(self, user_input=None):
        errors = {}
        if user_input is not None:
            combined = {**self._pending, **user_input}
            if not user_input.get(CONF_PASSWORD):
                combined[CONF_PASSWORD] = self._pending.get(CONF_PASSWORD, "")
            if error := control_error(combined):
                errors["base"] = error
            else:
                self._pending = combined
                return await self._finish()
        return self.async_show_form(step_id="control", data_schema=control_schema({**self._pending, **(user_input or {})}), errors=errors)
