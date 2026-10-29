# Changelog

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
