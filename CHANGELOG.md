# Changelog

## Grafana dashboard revision 2

- Keep measurements visible in short panel previews and after resizing: use larger inline U/value text when there is room, stacked text in tall cells, and value-first labels in narrow cells. Preserve full chip identity and telemetry in the tooltip.
- Use vector SVG rendering, contrasting black/white text and portable hexadecimal fill colors; reserve clearer space below board headers. Add a real ECharts regression for 400-pixel-high previews, narrow panels and repeated resizing with all 516 values present.
- Update only the generated Grafana dashboard and its readable sources. The integration remains at 0.5.5; existing panels can replace their chart function and select SVG without an HA restart.
- Pass 92 automated tests in total (60 existing Python tests, 32 JavaScript tests).

## 0.5.5

- Add a ready-to-import Grafana M60VK2A dashboard with source-preserving U labels, a selector for all normalized chip metrics, per-board read times and historical selection at the time range endpoint. Use the signed Business Charts plugin and existing InfluxDB 2.x / Flux data source.
- Cache one allowlisted JSON snapshot per board on the existing hourly WEB read and expose it on the board map. Keep snapshots unchanged between API polls, clear them on WEB failure, and exclude the bulk attribute from Recorder. No new entities, direct database credentials or miner requests are added.
- Provide InfluxDB export settings for three complete snapshots per hour, bounded historical queries, plugin installation and retention guidance. Preserve missing/stale/future handling and visible mapping uncertainty.
- Test actual ECharts SVG rendering/resizing and snapshot schema/cache propagation. Pass 91 automated tests (60 Python, 31 JavaScript).

## 0.5.4

- Read WEB chip data once per hour by default, independently of the existing API interval, including existing entries. Add a 60–86400-second chip polling option; keep the last measurement timestamp between reads and space retries after failures. Setup and reload still read immediately.
- Make M60VK2A cells fluid and compact by default, showing only U labels and temperatures. Preserve source C IDs and all telemetry in tooltips/details and keep a visible unverified mapping notice.
- Consolidate layout and telemetry notes, show the last chip measurement time and provide a full-width Panel view example for three boards on desktop monitors. Keep the permanent JavaScript URL.
- Pass 82 automated tests (59 Python, 23 JavaScript).

## 0.5.3

- Add the opt-in `layout: m60vk2a` HeatMap profile reconstructed from supplied PCB photographs: upper 4-by-21 and lower 4-by-22 sections with a central gap.
- Preserve WEB chip identities and telemetry; show assumed PCB references separately with a visible unverified C-to-U mapping notice and schematic orientation. Reject incompatible chip identities instead of silently assigning positions.
- Keep the default logical grid and manual layouts available, and preserve the permanent JavaScript URL. The profile adds no entities or device requests.
- Document InfluxDB chip-data exclusions separately from Recorder history.
- Pass 77 automated tests (56 Python, 21 JavaScript).

## 0.5.2

- Discover web board maps automatically without manual entity IDs, including renamed entities and dynamically appearing boards.
- Use automatic discovery in the card picker starter configuration and the main setup example. Preserve explicit entity selection for cards scoped to selected miners.
- Distinguish non-existent entity IDs from unavailable chip data and explain empty discovery results. Never create synthetic readings or reuse stale unavailable data.
- Keep the permanent JavaScript resource URL unchanged.
- Pass 72 automated tests (56 Python, 16 JavaScript).

## 0.5.1

- Distinguish salt-preparation failures from transport errors during power writes, including timeout, connection closure and invalid JSON.
- After an unacknowledged percentage write, refresh telemetry using GET commands and report the returned percentage when available. Never retry the write or claim an acknowledgement from read-back alone.
- Document bulk entity enabling, optional metrics in chip attributes, and manual HeatMap resource/card setup.
- Keep existing API timeout, token algorithm and user entity choices unchanged.
- Pass 67 automated tests (56 Python, 11 JavaScript).

## 0.5.0

- Simplify web setup to username, password and HTTPS certificate verification. Use HTTPS:443, the built-in btminerapi path and LuCI login automatically.
- Remove web protocol/port/path/authentication/JSON Pointer/cookie fields and the API port field from forms. New API connections use TCP 4433; existing custom API ports are preserved internally.
- Migrate existing entries to the fixed web profile while retaining separate API/web credentials, explicit TLS settings and entity identity. No device writes are issued during migration or reload.
- Explain that super and web admin are separate accounts with independently managed passwords, including the password-related rejection hint. Do not guess passwords, change token generation or retry writes automatically.
- Pass 63 automated tests (52 Python, 11 JavaScript), including simplified forms and configuration migration regressions.

## 0.4.0

- Preserve per-chip raw frequency/voltage, nonce/errors/CRC/repeat and both x/pct values from the existing LuCI request or normalized JSON.
- Show optional metrics in chip sensor attributes, board maps, diagnostics and selected heatmap chip details without creating thousands of additional entities.
- Retain zero/missing values and preserve other metrics when chip temperature is unavailable. Do not infer voltage units, error rates or firmware-specific x/pct meanings.
- Explain that Connection settings is the first options step, with API credentials and web authentication on subsequent forms.
- Add a specific API account/password hint when percentage commands return a password-related rejection, including fast mode. No token algorithm changes or automatic write retries.
- Pass 60 automated tests (49 Python, 11 JavaScript), including added parser, Home Assistant and card regressions.

## 0.3.1

- Preserve a bounded, sanitized firmware explanation for rejected API commands instead of showing only the numeric failure code.
- Include the requested percentage/mode and the latest command result in entity attributes and diagnostics, without credentials.
- Add guidance for generic percentage-command failures; never automatically switch mode or retry a failed write.
- Allow existing miner options to be saved without probing an unchanged host/API port, so credentials and web authentication can be repaired while offline.
- Document the existing Configure flow and separate API credentials from LuCI web credentials.
- Verify the supplied device HTML using the current parser: three boards with 172 chip readings each. The raw private page is not committed.

## 0.3.0

- Convert all current project documentation, configuration text, default entity names, errors, card labels and demo artwork to English.
- Remove the previous localized README and translation file; add an English-only source check to CI.
- Prefill the HTTPS LuCI path `/cgi-bin/luci/admin/status/btminerapi` for new web configurations.
- Parse individual chip temperatures from `textarea#syslog` and plain-text slot/chip records, preserving the source chip IDs.
- Add LuCI session login and renewal with isolated IP-address cookies.
- Keep HTTPS certificate verification enabled by default and expose an explicit local-device opt-out.
- Clean up per-miner web sessions without closing Home Assistant's shared connector.
- Keep normalized JSON support and separate API telemetry availability from web failures.

Existing entity IDs remain unchanged. Replace the component directory when upgrading manually so the removed translation file does not remain installed. Update the card resource URL to `?v=0.3.0` and refresh the browser.

The actual firmware response and physical layout of the user's board still require verification.

## 0.2.0

- Add power percentage control, adjustment mode selection, HACS repository structure and the chip heatmap card.
- Add an experimental normalized JSON web source and tests for 172 chips per board.

## 0.1.0

- Add API 3.x telemetry and bounded watt-based power control.
