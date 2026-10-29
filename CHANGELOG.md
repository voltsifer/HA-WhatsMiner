# Changelog

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
