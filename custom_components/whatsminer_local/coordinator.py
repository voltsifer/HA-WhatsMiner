"""One shared polling coordinator per miner."""
import asyncio
from datetime import timedelta
import json
import logging
from time import monotonic

import aiohttp

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WhatsminerClient, WhatsminerError, flatten
from .chip_web import CHIP_METRICS, ChipWebClient, ChipWebError
from .const import (
    CONF_PERCENT_MODE, CONF_WEB_CHIPS, CONF_WEB_PASSWORD, CONF_WEB_USERNAME,
    CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_INTERVAL,
    CONF_WEB_VERIFY_SSL, DEFAULT_WEB_PATH, DEFAULT_WEB_PROTOCOL, DEFAULT_WEB_PORT,
    DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN,
)

LOGGER = logging.getLogger(__name__)


class WhatsminerCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self.client = WhatsminerClient(self.config[CONF_HOST], self.config.get(CONF_PORT, DEFAULT_PORT))
        self.snapshot = {}
        self.command_lock = asyncio.Lock()
        self.percent_mode = self.config.get(CONF_PERCENT_MODE, "normal")
        self.last_power_percent_command = None
        self.chip_boards = []
        self.chip_snapshots = {}
        self.chip_updated_at = None
        self.web_interval = self.config.get(CONF_WEB_SCAN_INTERVAL, DEFAULT_WEB_INTERVAL)
        self._web_next_poll = 0.0
        self._web_values = {}
        self.web_client = None
        if self.config.get(CONF_WEB_CHIPS):
            self.web_client = ChipWebClient(
                async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar(unsafe=True)),
                self.config[CONF_HOST],
                DEFAULT_WEB_PROTOCOL, DEFAULT_WEB_PORT, DEFAULT_WEB_PATH,
                auth_type="luci", username=self.config.get(CONF_WEB_USERNAME, "admin"),
                password=self.config.get(CONF_WEB_PASSWORD, ""),
                verify_ssl=self.config.get(CONF_WEB_VERIFY_SSL, True), detach_session=True)
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=timedelta(
            seconds=self.config.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL)))

    async def _async_update_data(self):
        try:
            snapshot = await self.client.read_snapshot()
            values = flatten(snapshot)
        except (WhatsminerError, TypeError, KeyError, AttributeError, ValueError) as err:
            raise UpdateFailed("Could not read WhatsMiner API 3.x telemetry") from err
        self.snapshot = snapshot
        if self.web_client is not None and monotonic() >= self._web_next_poll:
            # WEB failures invalidate only the chip readings, not API telemetry.
            self.chip_boards = []
            self.chip_snapshots = {}
            self.chip_updated_at = None
            self._web_values = {}
            try:
                self.chip_boards = await self.web_client.read_chips()
            except ChipWebError as err:
                self._web_values["chip-web-status"] = str(err)
            else:
                self.chip_updated_at = dt_util.utcnow().isoformat()
                self._web_values["chip-web-status"] = "ok"
                for board in self.chip_boards:
                    # InfluxDB stringifies attributes with str(), which is not JSON
                    # for nested arrays. Cache one explicit JSON snapshot per WEB read.
                    self.chip_snapshots[board["slot"]] = json.dumps({
                        "schema_version": 1,
                        "slot": board["slot"],
                        "updated_at": self.chip_updated_at,
                        "chips": [{key: chip[key] for key in (
                            "id", "temperature", *CHIP_METRICS, "row", "column"
                        ) if key in chip} for chip in board["chips"]],
                    }, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
                    temperatures = [c["temperature"] for c in board["chips"] if c["temperature"] is not None]
                    self._web_values[f"web-board-{board['slot']}-chip-max"] = max(temperatures) if temperatures else None
                    for chip in board["chips"]:
                        self._web_values[f"web-chip-{board['slot']}-{chip['id']}"] = chip["temperature"]
            finally:
                # Space attempts after failures too, including explicit API refreshes.
                self._web_next_poll = monotonic() + self.web_interval
        values.update(self._web_values)
        return values
