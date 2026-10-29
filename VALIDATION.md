# HA-WhatsMiner 0.3.1 validation

Date: October 29, 2026.

**44 Python tests and 9 JavaScript tests pass: 53 automated tests in total.** The English-only source check also passes. Current remote CI results are available on the repository's **Actions** tab.

| Area | Coverage and limits |
| --- | --- |
| API 3.x TCP transport and authenticated writes | Local TCP emulator; framing, fragmented responses, heartbeats, timeouts, invalid/truncated/oversized responses and authentication vectors |
| Power controls | Watt and percentage commands, bounds, tuning guard, separate measured/configured power and no automatic write retry |
| Home Assistant integration | Core 2024.12.5 on Python 3.12; setup/unload, forms, number/select actions, dynamic discovery and availability |
| Web JSON transport | Local HTTP emulator; Basic/Cookie authentication, JSON Pointer, identity checks and redirect rejection |
| LuCI HTML/plain-text parsing | Synthetic syslog pages and text, 172 chips per board, preserved C0-based IDs, missing readings, duplicate IDs, login pages and truncated HTML |
| LuCI authentication | Local server; login form POST, IP-address cookies, session reuse, expired-cookie renewal and no repeated login loop after rejected credentials |
| HTTPS | Local self-signed TLS server; certificate verification fails by default and succeeds only after explicit opt-out |
| Session cleanup | Isolated per-miner cookie session is detached on unload without closing Home Assistant's shared connector |
| Heatmap calculations | Four Node.js tests for values, color scales, mapping and missing data |
| Heatmap DOM | Five happy-dom 21.0.4 tests for rendering, all 172 cells, interaction, unavailable data, HTML injection and explicit layouts |
| Project language | English labels, documentation and regenerated artwork; CI rejects Cyrillic text and removed language files |
| Supplied device HTML | Parsed successfully: 3 boards × 172 chips, IDs C0–C171, no missing temperatures; raw private page is not included in the repository |
| Actual miner operations | Live login, retrieval and power commands remain unverified on the user's private network |
| Physical chip placement | Not verified; the demo grid is logical, not a model-specific board diagram |
| Installation in the user's HAOS | Not verified; source is prepared for HACS custom repository installation |
| Full browser rendering | DOM checks performed; a complete Chromium visual test was unavailable in the environment |

API and web tests use local emulators or mocked device responses. They do not establish hardware operating limits or guarantee compatibility with every firmware revision.

The LuCI endpoint and log grammar are supported based on the supplied path and a public client using that format. The implementation extracts `textarea#syslog`, recognizes explicit slot and chip records, and never reconstructs individual temperatures from board minimum/average/maximum statistics. The supplied captured HTML has also been verified with the same parser. Additional firmware variants can still differ.

`examples/heatmap-demo.html` uses synthetic data for one 172-chip board. `examples/heatmap-demo.png` is a static illustration of the same concept, not a Home Assistant screenshot. Both use English labels and do not imply physical board geometry.

## Reproduce the checks

Use a disposable Python 3.12 environment with `homeassistant==2024.12.5` and `habluetooth==3.49.0`:

```bash
python tools/check_english.py
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

Version 0.3.1 adds tests for preserved and redacted API failure reasons, no write retry, rejected percentage command context in diagnostics, offline credential/authentication editing for an unchanged endpoint, and continued validation of a changed host.
