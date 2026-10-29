"""Opt-in GET adapter for an observed WEB JSON endpoint, not guessed firmware URLs.

The actual firmware schema/auth flow is not known yet. This adapter accepts an
explicit normalized contract. Add a firmware-specific parser only after a real
response has been captured. No board min/avg/max may be expanded into chip values.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from yarl import URL

from .api import numeric

MAX_WEB_BYTES = 2 * 1024 * 1024
MAX_CHIPS = 4096


class ChipWebError(Exception):
    """Sanitized error reason; never embed URLs, cookies or response bodies."""


def validate_web_path(path: str) -> str:
    parsed = urlsplit(path)
    if not path.startswith("/") or path.startswith("//") or parsed.scheme or parsed.netloc or parsed.fragment:
        raise ValueError("Use a relative endpoint path starting with one slash")
    if any(ord(char) < 32 for char in path) or "\\" in path:
        raise ValueError("Invalid endpoint path")
    return path


def json_pointer(payload: Any, pointer: str) -> Any:
    if pointer == "":
        return payload
    if not pointer.startswith("/"):
        raise ChipWebError("invalid_json_pointer")
    try:
        for part in pointer[1:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            payload = payload[int(key)] if isinstance(payload, list) else payload[key]
    except (KeyError, ValueError, IndexError, TypeError):
        raise ChipWebError("json_pointer_not_found") from None
    return payload


def normalize_chips(payload: Any, pointer: str = "") -> list[dict[str, Any]]:
    """Contract: {boards:[{slot:int, chips:[{id:str, temperature:number|null}]}]}.

    Optional explicit row/column coordinates are carried through, never inferred.
    Missing readings remain null. IDs are required so values cannot be shifted
    onto another chip when a chip disappears from a response.
    """
    payload = json_pointer(payload, pointer)
    boards = payload.get("boards") if isinstance(payload, dict) else None
    if not isinstance(boards, list) or not boards or len(boards) > 32:
        raise ChipWebError("unsupported_web_schema")
    result = []
    slots = set()
    total = 0
    for board in boards:
        if not isinstance(board, dict):
            raise ChipWebError("unsupported_web_schema")
        slot, chips = board.get("slot"), board.get("chips")
        if type(slot) is not int or slot < 0 or slot > 31 or slot in slots or not isinstance(chips, list) or not chips:
            raise ChipWebError("invalid_board_identity")
        slots.add(slot)
        total += len(chips)
        if total > MAX_CHIPS:
            raise ChipWebError("too_many_chips")
        normalized = []
        ids = set()
        positions = set()
        for chip in chips:
            if not isinstance(chip, dict) or "temperature" not in chip:
                raise ChipWebError("unsupported_web_schema")
            chip_id = chip.get("id")
            if not isinstance(chip_id, (str, int)) or isinstance(chip_id, bool):
                raise ChipWebError("invalid_chip_identity")
            chip_id = str(chip_id)
            if not chip_id or len(chip_id) > 64 or chip_id in ids:
                raise ChipWebError("invalid_chip_identity")
            ids.add(chip_id)
            value = numeric(chip["temperature"])
            # A numeric string is fine; an invalid/absent temperature is missing,
            # never treated as zero or synthesized from board statistics.
            item = {"id": chip_id, "temperature": value}
            row, column = chip.get("row"), chip.get("column")
            if row is not None or column is not None:
                if type(row) is not int or type(column) is not int or not 0 <= row < 128 or not 0 <= column < 128:
                    raise ChipWebError("invalid_chip_position")
                if (row, column) in positions:
                    raise ChipWebError("duplicate_chip_position")
                positions.add((row, column))
                item.update(row=row, column=column)
            normalized.append(item)
        result.append({"slot": slot, "chips": normalized})
    return sorted(result, key=lambda board: board["slot"])


class ChipWebClient:
    def __init__(self, session, host, protocol, port, path, pointer="", auth_type="none",
                 username="", password="", cookie="", timeout=10):
        validate_web_path(path)
        self.session = session
        # Endpoint is restricted to the same host as the explicitly configured miner.
        self.url = URL.build(scheme=protocol, host=host, port=port).join(URL(path))
        self.pointer, self.auth_type = pointer, auth_type
        self.username, self.password, self.cookie, self.timeout = username, password, cookie, timeout

    async def read_chips(self):
        headers = {"Accept": "application/json"}
        auth = None
        if self.auth_type == "basic":
            auth = aiohttp.BasicAuth(self.username, self.password)
        elif self.auth_type == "cookie":
            headers["Cookie"] = self.cookie
        try:
            async with asyncio.timeout(self.timeout):
                async with self.session.get(self.url, auth=auth, headers=headers, allow_redirects=False) as response:
                    if response.status in (301, 302, 303, 307, 308, 401, 403):
                        raise ChipWebError("web_auth_required")
                    if response.status != 200:
                        raise ChipWebError("web_http_error")
                    chunks = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        chunks.extend(chunk)
                        if len(chunks) > MAX_WEB_BYTES:
                            raise ChipWebError("web_response_too_large")
            try:
                payload = json.loads(chunks)
            except (ValueError, UnicodeError):
                raise ChipWebError("web_response_not_json") from None
            return normalize_chips(payload, self.pointer)
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError):
            raise ChipWebError("web_connection_failed") from None
