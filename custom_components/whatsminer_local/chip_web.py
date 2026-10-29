"""Read-only chip data from normalized JSON or the LuCI btminerapi syslog page."""
from __future__ import annotations

import asyncio
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from yarl import URL

from .api import numeric

MAX_WEB_BYTES = 2 * 1024 * 1024
MAX_CHIPS = 4096
SLOT_HEADER = re.compile(r"^\s*slot\s*:\s*(\d+)\s*(?:,|$)", re.IGNORECASE)
CHIP_RECORD = re.compile(r"^\s*(C\d+)\b(.*)$")
RECORD_FIELD = re.compile(r"(?<!\S)([a-z][a-z0-9_-]*)\s*:\s*([^\s,]+)", re.IGNORECASE)


class ChipWebError(Exception):
    """Sanitized error reason; never embed URLs, cookies or response bodies."""


class _LuCIPage(HTMLParser):
    """Extract only the syslog textarea; never execute or scrape page scripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.is_login = False
        self._capturing = False
        self._parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") in ("luci_username", "luci_password"):
            self.is_login = True
        if tag == "textarea" and attrs.get("id") == "syslog":
            self._capturing = True
            self._parts = []

    def handle_data(self, data):
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag == "textarea" and self._capturing:
            self.blocks.append("".join(self._parts))
            self._capturing = False


def parse_btminer_log(text: str) -> list[dict[str, Any]]:
    """Read explicit C<n> temp fields within slot blocks; retain source IDs."""
    boards = []
    current = None
    count = 0
    for line in text.splitlines():
        if match := SLOT_HEADER.match(line):
            current = {"slot": int(match[1]), "chips": []}
            boards.append(current)
            if len(boards) > 32:
                raise ChipWebError("too_many_boards")
            continue
        if line.lstrip().lower().startswith("slot:"):
            raise ChipWebError("invalid_board_identity")
        match = CHIP_RECORD.match(line)
        if not match:
            continue
        fields = {name.lower(): value for name, value in RECORD_FIELD.findall(match[2])}
        if "freq" not in fields and "temp" not in fields:
            continue
        if current is None:
            raise ChipWebError("chip_without_slot")
        count += 1
        if count > MAX_CHIPS:
            raise ChipWebError("too_many_chips")
        value = fields.get("temp")
        if value is not None:
            value = value.removesuffix("°C").removesuffix("C")
        current["chips"].append({"id": match[1], "temperature": numeric(value)})
    # Reuse identity, size and missing-value checks for both wire formats.
    return normalize_chips({"boards": boards})


def parse_web_response(body: bytes, pointer: str = "") -> list[dict[str, Any]]:
    if len(body) > MAX_WEB_BYTES:
        raise ChipWebError("web_response_too_large")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeError:
        raise ChipWebError("web_response_encoding_error") from None
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            payload = json.loads(text)
        except ValueError:
            raise ChipWebError("web_response_not_json") from None
        return normalize_chips(payload, pointer)
    if pointer:
        raise ChipWebError("json_pointer_requires_json")
    if stripped.startswith("<"):
        page = _LuCIPage()
        page.feed(text)
        page.close()
        if page.is_login:
            raise ChipWebError("web_auth_required")
        if len(page.blocks) != 1:
            raise ChipWebError("web_syslog_not_found")
        return parse_btminer_log(page.blocks[0])
    return parse_btminer_log(text)


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
                 username="", password="", cookie="", timeout=10, verify_ssl=True,
                 owns_session=False, detach_session=False):
        validate_web_path(path)
        self.session = session
        # Endpoint is restricted to the same host as the explicitly configured miner.
        self.url = URL.build(scheme=protocol, host=host, port=port).join(URL(path))
        self.pointer, self.auth_type = pointer, auth_type
        self.username, self.password, self.cookie, self.timeout = username, password, cookie, timeout
        self.verify_ssl = verify_ssl
        self.owns_session = owns_session
        self.detach_session = detach_session

    async def async_close(self):
        if self.detach_session:
            # HA owns the shared connector: close this session by detaching it.
            self.session.detach()
        elif self.owns_session:
            await self.session.close()

    async def _request_bytes(self, method, url, *, form=None):
        headers = {"Accept": "application/json, text/html, text/plain"}
        auth = None
        if self.auth_type == "basic":
            auth = aiohttp.BasicAuth(self.username, self.password)
        elif self.auth_type == "cookie":
            headers["Cookie"] = self.cookie
        async with self.session.request(
            method, url, auth=auth, headers=headers, data=form,
            allow_redirects=False, ssl=self.verify_ssl,
        ) as response:
            chunks = bytearray()
            async for chunk in response.content.iter_chunked(65536):
                chunks.extend(chunk)
                if len(chunks) > MAX_WEB_BYTES:
                    raise ChipWebError("web_response_too_large")
            return response.status, bytes(chunks)

    async def _read_data(self):
        status, body = await self._request_bytes("GET", self.url)
        if status in (301, 302, 303, 307, 308, 401, 403):
            raise ChipWebError("web_auth_required")
        if status != 200:
            raise ChipWebError("web_http_error")
        return await asyncio.to_thread(parse_web_response, body, self.pointer)

    async def _luci_login(self):
        # Credentials go only to this miner's standard LuCI login form.
        # An isolated CookieJar(unsafe=True) is required for cookies on IP hosts.
        self.session.cookie_jar.clear_domain(self.url.host)
        login_url = self.url.with_path("/cgi-bin/luci").with_query(None)
        status, _ = await self._request_bytes("POST", login_url, form={
            "luci_username": self.username, "luci_password": self.password,
        })
        cookies = self.session.cookie_jar.filter_cookies(self.url)
        if status not in (200, 302, 303) or not any(
            name.startswith("sysauth") and morsel.value for name, morsel in cookies.items()
        ):
            raise ChipWebError("web_auth_required")

    async def read_chips(self):
        try:
            async with asyncio.timeout(self.timeout):
                try:
                    return await self._read_data()
                except ChipWebError as err:
                    if self.auth_type != "luci" or str(err) != "web_auth_required":
                        raise
                # One login attempt and one read retry; never follow redirects.
                await self._luci_login()
                return await self._read_data()
        except (aiohttp.ClientConnectorCertificateError, aiohttp.ClientSSLError):
            raise ChipWebError("web_tls_error") from None
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError):
            raise ChipWebError("web_connection_failed") from None
