# HA-WhatsMiner 0.5.5 validation

Date: October 29, 2026.

**60 Python tests and 31 JavaScript tests pass: 91 automated tests in total.** The English-only source check also passes. Current remote CI results are available on the repository's **Actions** tab.

| Area | Coverage and limits |
| --- | --- |
| API 3.x TCP transport and authenticated writes | Local TCP emulator; framing, fragmented responses, heartbeats, timeouts, invalid/truncated/oversized responses and authentication vectors |
| Power controls | Watt and percentage commands, bounds, tuning guard, separate measured/configured power and no automatic write retry |
| Home Assistant integration | Core 2024.12.5 on Python 3.12; setup/unload, forms, number/select actions, dynamic discovery and availability |
| Low-level web helper compatibility | Local HTTP emulator; Basic/Cookie and JSON Pointer helper tests retained; these options are not part of the integration UI/profile |
| LuCI HTML/plain-text parsing | Synthetic syslog pages and text, 172 chips per board, preserved C0-based IDs, missing readings, duplicate IDs, login pages and truncated HTML |
| LuCI authentication | Local server; login form POST, IP-address cookies, session reuse, expired-cookie renewal and no repeated login loop after rejected credentials |
| HTTPS | Local self-signed TLS server; certificate verification fails by default and succeeds only after explicit opt-out |
| Session cleanup | Isolated per-miner cookie session is detached on unload without closing Home Assistant's shared connector |
| Heatmap calculations | Seven Node.js tests for values, color scales, mapping, missing data and reconstructed profile identities |
| Heatmap DOM | Sixteen happy-dom 21.0.4 tests for rendering, all 172 cells, interaction, unavailable data, HTML injection and explicit layouts |
| Grafana historical heatmap | Eight Node.js tests including real ECharts 5.5.1 SVG rendering/resizing, 516 cells, geometry parity, full metrics, missing/zero values, stale/future/malformed snapshots, source identity rejection, frame labels/vectors, HTML escaping, and bounded Flux/source embedding |
| Project language | English labels, documentation and regenerated artwork; CI rejects Cyrillic text and removed language files |
| Supplied device HTML | Parsed successfully: 3 boards × 172 chips, IDs C0–C171, no missing temperatures; raw private page is not included in the repository |
| Actual miner operations | The user reports live telemetry and HeatMap working in HAOS; power writes remain unconfirmed |
| Physical chip placement | M60VK2A profile reconstructed from photographed PCB labels; some positions, alignment and WEB Cn to PCB U(n+1) correspondence remain unverified |
| Installation in the user's HAOS | The user reports working installation; the development environment cannot independently access that HAOS instance |
| Full browser rendering | DOM checks performed; a complete Chromium visual test was unavailable in the environment |

API and web tests use local emulators or mocked device responses. They do not establish hardware operating limits or guarantee compatibility with every firmware revision.

The LuCI endpoint and log grammar are supported based on the supplied path and a public client using that format. The implementation extracts `textarea#syslog`, recognizes explicit slot and chip records, and never reconstructs individual temperatures from board minimum/average/maximum statistics. The supplied captured HTML has also been verified with the same parser. Additional firmware variants can still differ.

`examples/heatmap-demo.html` uses synthetic data for one 172-chip board. `examples/heatmap-demo.png` is a static illustration of the same concept, not a Home Assistant screenshot. Both use English labels and do not imply physical board geometry.

## Reproduce the checks

Use a disposable Python 3.12 environment with `homeassistant==2024.12.5` and `habluetooth==3.49.0`:

```bash
python tools/check_english.py
python tools/build_grafana_dashboard.py --check
python -m unittest discover -s tests -v
```

The TCP/API-only tests are independent of Home Assistant and require Python 3.11+:

```bash
python -m unittest discover -s tests -p test_api.py -v
```

JavaScript tests use Node.js 22+:

```bash
npm ci --ignore-scripts
npm test
```

The npm dependencies are only for development tests. The production card has no npm, CDN or external JavaScript dependency.

Version 0.3.1 added tests for preserved and redacted API failure reasons, no write retry, rejected percentage command context in diagnostics, offline credential/authentication editing for an unchanged endpoint, and continued validation of a changed host.

Version 0.4.0 added optional per-chip metrics, spaced x/pct pair parsing, numeric validation, no cross-chip carryover, chip/map/diagnostics propagation, missing-temperature availability, selected-chip DOM details and the fast-mode password-error hint. The supplied device HTML was rechecked: all 516 chip records include the expected additional fields.

Version 0.5.0 adds a three-field web form, fixed HTTPS:443 LuCI endpoint, automatic API port 4433 for new entries, and migration tests removing obsolete options while preserving API/web credentials, explicit TLS choice, entity identities and legacy API ports. Form, migration and reload operations issue no power commands. The API token and request algorithm are unchanged; super/admin credential guidance is based on the manufacturer operation guide.

Version 0.5.1 adds staged transport errors and a read-only telemetry refresh after an unacknowledged percentage write. Tests distinguish authentication preparation from a write timeout, truncated response or invalid JSON, and verify matching/different/unavailable read-back with exactly one write attempt.

Version 0.5.2 adds HeatMap discovery tests for three 172-chip boards without entity IDs, renamed/new/removed/unavailable sources, explicit selection across multiple miners, invalid mixed configuration, empty-state instructions and placeholder-free card picker defaults. Browser code uses only existing HA state data and sends no miner requests.

Version 0.5.3 adds M60VK2A tests for all 172 unique IDs, photographed numbering anchors, the two board sections and reserved central gap, preserved source values and metrics, missing chips, visible mapping uncertainty and assumed PCB references, incompatible/duplicate identity rejection and opt-in configuration. The reconstruction is independently derived from the supplied photographs; no third-party implementation or private photo/serial data is shipped. Tests validate layout completeness and behavior, not the unverified hardware identity correspondence.

Version 0.5.4 adds fake-clock integration tests for hourly WEB reads with continued API polling, preserved chip metrics/timestamps, failure spacing/recovery, interval validation and options reload. DOM tests cover 516 U-only cells across three compact boards, consolidated mapping notes, source C IDs and metrics in details, and the compact opt-out. Full-width 1080p placement is the intended desktop configuration; browser viewport fitting could not be visually verified because Chromium was unavailable.

Version 0.5.5 adds three-board atomic JSON snapshot/cache tests and the Grafana suite above. The generated importable dashboard is checked against its JavaScript and Flux sources. No live Grafana or InfluxDB instance is connected in this development environment; actual import, Flux execution and export permissions still require validation on the user installation. The archive begins only when the new snapshot attribute is exported and cannot backfill unsaved history.
