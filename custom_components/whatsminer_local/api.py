"""Async WhatsMiner API 3.x client. No HA dependency; no automatic write retry."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import re
import struct
import time
from typing import Any

MAX_FRAME = 2 * 1024 * 1024


class WhatsminerError(Exception):
    """Transport, framing, or response error (never contains the raw payload)."""


class APIError(WhatsminerError):
    def __init__(self, code: int, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason
        super().__init__(f"WhatsMiner API error {code}" + (f": {reason}" if reason else ""))


class CommandTransportError(WhatsminerError):
    """A sanitized transport failure with its write-sequence stage."""

    def __init__(self, stage: str, reason: str) -> None:
        self.stage, self.reason = stage, reason
        super().__init__(reason)


def safe_api_reason(message: Any, secrets: tuple[str, ...] = ()) -> str | None:
    """Keep a bounded firmware explanation, never a raw response or credentials."""
    if isinstance(message, dict):
        message = next((message[key] for key in ("reason", "error", "message", "msg")
                        if isinstance(message.get(key), str)), None)
    if not isinstance(message, str):
        return None
    text = " ".join(message.split())
    if text.lower() in ("", "ok", "fail", "failed", "error"):
        return None
    for value in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(value, "[redacted]")
    text = re.sub(
        r'''(?i)\b(password|passwd|token|salt|cookie|authorization|luci_password)\b["']?\s*[:=]\s*(?:"[^"]*"|'[^']*'|\S+)''',
        r"\1=[redacted]", text,
    )
    return text[:300]


def make_token(command: str, password: str, salt: str, timestamp: int) -> str:
    digest = hashlib.sha256(f"{command}{password}{salt}{timestamp}".encode()).digest()
    return base64.b64encode(digest).decode("ascii")[:8]


class WhatsminerClient:
    def __init__(self, host: str, port: int = 4433, timeout: float = 10) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self._lock = asyncio.Lock()

    async def _request(self, payload: dict[str, Any], *, secrets: tuple[str, ...] = ()) -> dict[str, Any]:
        writer = None
        phase = "connecting"
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(self.host, self.port)
                phase = "sending the request"
                body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
                writer.write(struct.pack("<I", len(body)) + body)
                await writer.drain()
                phase = "waiting for the API response"
                while True:
                    length = struct.unpack("<I", await reader.readexactly(4))[0]
                    if length == 0:  # API heartbeat
                        continue
                    if length > MAX_FRAME:
                        raise WhatsminerError("Response frame exceeds limit")
                    response = json.loads(await reader.readexactly(length))
                    break
                if not isinstance(response, dict) or type(response.get("code")) is not int:
                    raise WhatsminerError("Invalid API response")
                if response["code"] != 0:
                    raise APIError(response["code"], safe_api_reason(response.get("msg"), secrets))
                if response.get("desc") not in (None, payload["cmd"]):
                    raise WhatsminerError("Unexpected response command")
                return response
        except TimeoutError as err:
            raise WhatsminerError(f"Timed out while {phase}") from err
        except asyncio.IncompleteReadError as err:
            raise WhatsminerError("API closed the connection before a complete response was received") from err
        except OSError as err:
            raise WhatsminerError(f"Connection failed while {phase}") from err
        except (ValueError, UnicodeError) as err:
            raise WhatsminerError("Invalid JSON response") from err
        finally:
            if writer is not None:
                writer.close()
                try:
                    async with asyncio.timeout(1):
                        await writer.wait_closed()
                except (TimeoutError, OSError):
                    pass

    async def read_snapshot(self) -> dict[str, Any]:
        async with self._lock:
            info = await self._request({"cmd": "get.device.info"})
            status = await self._request({"cmd": "get.miner.status", "param": "summary+edevs"})
            try:
                setting = await self._request({"cmd": "get.miner.setting"})
            except APIError as err:
                if err.code != -2:
                    raise
                setting = {"msg": {}}
            for response in (info, status, setting):
                if not isinstance(response.get("msg"), dict):
                    raise WhatsminerError("Expected an object in API response")
            result = {"info": info["msg"], "status": status["msg"], "setting": setting["msg"]}
            if not isinstance(result["status"].get("summary"), dict):
                raise WhatsminerError("Missing status summary; API 3.x required")
            return result

    async def set_power(self, watts: int, account: str, password: str) -> None:
        await self._write("set.miner.power", watts, account, password)

    async def set_power_percent(self, percent: int, mode: str, account: str, password: str) -> None:
        if type(percent) is not int or not 0 <= percent <= 100 or mode not in ("normal", "fast"):
            raise ValueError("Invalid power percentage or mode")
        await self._write("set.miner.power_percent", {"percent": percent, "mode": mode}, account, password)

    async def _write(self, command: str, param: Any, account: str, password: str) -> None:
        # Salt and timestamp are fetched immediately before each explicit write.
        # A timed-out write is ambiguous and MUST NOT be automatically retried.
        async with self._lock:
            try:
                response = await self._request({"cmd": "get.device.info", "param": "salt"}, secrets=(password,))
            except APIError:
                raise
            except WhatsminerError as err:
                raise CommandTransportError("authentication", str(err)) from err
            msg = response.get("msg")
            salt = msg.get("salt") if isinstance(msg, dict) else None
            if not isinstance(salt, str) or not salt:
                raise CommandTransportError("authentication", "Device did not return an authentication salt")
            timestamp = response.get("when")
            if type(timestamp) is not int:
                timestamp = int(time.time())
            token = make_token(command, password, salt, timestamp)
            try:
                await self._request({
                    "cmd": command, "ts": timestamp, "account": account,
                    "token": token, "param": param,
                }, secrets=(password, salt, token))
            except APIError:
                raise
            except WhatsminerError as err:
                raise CommandTransportError("write", str(err)) from err


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def flatten(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Expose documented fields only; missing values never become zero."""
    summary = snapshot["status"]["summary"]
    info = snapshot["info"]
    setting = snapshot["setting"]
    values: dict[str, Any] = {}
    for key in (
        "power-realtime", "power-5min", "power-limit", "environment-temperature",
        "chip-temp-min", "chip-temp-avg", "chip-temp-max", "hash-average",
        "hash-realtime", "hash-1min", "hash-15min", "freq-avg", "fan-speed-in",
        "fan-speed-out", "elapsed", "power-rate",
    ):
        values[key] = numeric(summary.get(key))
    values["configured-power"] = numeric(setting.get("power"))
    if values["configured-power"] is None:
        values["configured-power"] = numeric(info.get("miner", {}).get("power-limit-set"))
    values["power-percent"] = numeric(setting.get("power-percent"))
    values["up-freq-finish"] = numeric(summary.get("up-freq-finish"))
    values["power-mode"] = setting.get("power-mode")
    for key in ("vin", "iin", "temp0", "fanspeed"):
        values[f"psu-{key}"] = numeric(info.get("power", {}).get(key))
    temperatures = summary.get("board-temperature", [])
    if isinstance(temperatures, list):
        for slot, value in enumerate(temperatures):
            values[f"board-{slot}-temperature"] = numeric(value)
    boards = snapshot["status"].get("edevs", [])
    if isinstance(boards, list):
        for board in boards:
            if not isinstance(board, dict):
                continue
            slot = board.get("slot")
            if type(slot) is not int or slot < 0:
                continue
            for key in ("chip-temp-min", "chip-temp-avg", "chip-temp-max", "hash-average", "freq", "effective-chips"):
                values[f"board-{slot}-{key}"] = numeric(board.get(key))
    errors = info.get("error-code")
    if isinstance(errors, list):
        codes = sorted({str(k) for item in errors if isinstance(item, dict) for k in item if str(k).isdigit()})
        values["error-count"] = len(codes)
        values["error-codes"] = codes
    return values


def validate_power(value: Any, minimum: int, maximum: int) -> int:
    watts = numeric(value)
    if watts is None or not watts.is_integer() or not minimum <= watts <= maximum:
        raise ValueError(f"Power must be an integer within {minimum}–{maximum} W")
    return int(watts)
