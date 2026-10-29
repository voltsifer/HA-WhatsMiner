# HA-WhatsMiner

Local Home Assistant / HAOS integration for WhatsMiner. Version **0.4.0**.

Connect directly to the official API 3.x over TCP port 4433. No MQTT, Node-RED or cloud service is required. All project documentation, default entity names, configuration forms, errors and heatmap labels are in **English**.

Power control and API telemetry are implemented. Individual chip temperatures can be read from a LuCI `btminerapi` HTML page, its plain-text log, or a normalized JSON endpoint. The parser has also been checked against a supplied device HTML response: three boards with 172 chips each were read successfully. Live login, power commands and installation on the user's hardware still require device-side validation.

![Synthetic heatmap example: one board with 172 chips](examples/heatmap-demo.png)

## Features

- Board temperatures and chip minimum/average/maximum temperatures, globally and per board.
- Hash rates, frequencies, effective chip counts, fans, PSU telemetry and error codes.
- Separate measured power, configured power and effective power limit sensors.
- Explicit power control in watts with user-defined bounds.
- `set.miner.power_percent` control and a local `normal` / `fast` adjustment-mode selector.
- Chip frequency/voltage raw values, nonce/error/CRC/repeat snapshots, and both x/pct values in map attributes and chip details.
- Individual chip readings from the LuCI `btminerapi` syslog page, plain text or normalized JSON.
- Optional LuCI session login and renewal, HTTP Basic authentication or an existing session cookie.
- A heatmap card with chip IDs, temperatures, statistics, median deviations and explicit board layouts.
- One independently identifiable temperature sensor per chip, disabled by default in the entity registry. The card does not require these sensors to be enabled.
- Multiple miners and dynamic board/chip discovery. Tested with **172 chips per board**; no fixed board count is assumed.

## Install through HACS

Repository: **https://github.com/voltsifer/HA-WhatsMiner**.

1. Open **HACS → menu ⋮ → Custom repositories**.
2. Add `https://github.com/voltsifer/HA-WhatsMiner`, category **Integration**.
3. Download **HA-WhatsMiner** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → HA-WhatsMiner**.
5. Enter the miner host, API port **4433** and polling interval, normally **30 seconds**.

Start with power control and web chip data disabled, then compare API telemetry with the miner's interface. HACS installs the heatmap JavaScript with the integration; a second dashboard repository is unnecessary. See [HEATMAP.md](HEATMAP.md) for resource registration.

### Manual installation and upgrades

Place `custom_components/whatsminer_local` at `/config/custom_components/whatsminer_local`, then restart Home Assistant. Replace the integration directory when upgrading manually so removed translation files are not left behind. The internal domain remains `whatsminer_local` to preserve integration identity.

Existing entity IDs and user-customized names are maintained by Home Assistant. Renaming a default display label does not intentionally rename an entity ID or rewrite automations.

## Edit an existing miner

Open **Settings → Devices & services → HA-WhatsMiner → Configure** (the options/gear control on the existing integration entry). Do not add a duplicate miner to change credentials.

**The first screen is only Connection settings. Select Submit to continue; it does not finish the options flow when power control or web data is enabled.** Submit the connection form, then edit the API power-control form when enabled, and finally the web form when web chip data is enabled. A blank password or cookie field preserves its previous value.

- The **API password** and account are used for TCP power commands.
- The **Web username/password** and **Web authentication** are used for chip data. Select **luci** for the supplied LuCI login page; Basic is a different HTTP authentication scheme.
- Updating stored connection credentials does not change the account password on the miner itself. Device account passwords are managed on the miner or through WhatsminerTool.
- When the host and API port remain unchanged, option changes can be saved while the miner is unreachable. A changed host or port is still checked to avoid accidentally attaching an existing entry to another miner.
- Saving options reloads the integration without issuing power commands.

## Power control

Enable power control in the integration options. Enable API Write in WhatsminerTool. The manufacturer also requires changing the default `admin` password; API `account` accepts **`super`, `user1`, `user2`, `user3`**, rather than `admin`.

Provide the matching API password and watt limits appropriate for your exact miner and PSU. Hardware limits are not inferred.

| Entity | Behavior |
| --- | --- |
| Set power | Sends `set.miner.power` with an integer watt value within your configured bounds |
| Set power percentage | Sends `set.miner.power_percent` with an integer percentage of initial stable power |
| Power percentage adjustment mode | Selects `normal` or `fast` for the next explicit percentage command; selecting it does not write to the miner |
| Reported power percentage | Shows the firmware's `get.miner.setting → power-percent`, without treating 0 as 100% |

The percentage refers to **initial stable power after frequency tuning**, not rated power or current measured consumption. For example, an initial stable power of 3500 W at 80% gives an approximate target of `3500 × 80 / 100 = 2800 W`; actual consumption can differ.

- The API permits 0–100%. The integration's default lower bound is 50%, configurable in options. That bound is a command restriction, not a guarantee of stable operation.
- `normal` takes several minutes and is the manufacturer's preferred mode for frequent adjustments. On air-cooled miners it is available in Normal/Low Power modes; liquid-cooled miners do not have this restriction.
- `fast` takes approximately one second, with greater performance loss and lower stability.
- Percentage control is effective after frequency tuning. The integration blocks it while the API explicitly reports `up-freq-finish = 0`. If this field is absent, the firmware decides whether to accept the command.
- The miner does **not persist the percentage after reboot**. The integration does not automatically restore it.
- `set.miner.power` persists its watt setting on API 3.0.3+. During tuning, that command may take effect only after the next miner start.
- Reloading the integration resets the local mode selector to the configured default.

Setup, polling, mode selection, bound changes and HA restarts do not issue power commands. Commands are sent only when explicitly setting a number entity. A value already confirmed by telemetry is skipped. A timed-out write is not retried automatically, and an `ok` response does not replace measured telemetry with an optimistic value.

Example action; replace the entity ID with yours:

```yaml
action: number.set_value
target:
  entity_id: number.replace_with_actual_percent_control
data:
  value: 80
```

### Investigate a rejected power percentage command

If the miner reports **invalid json or password is wrong**, first check the password for the selected **API account** in **Configure → submit Connection settings → Power control**. This firmware message is ambiguous; it does not prove that the password alone is wrong. The request object and SHA256/Base64 token follow the documented API 3.x format and are tested against a reference vector. Changing Basic/LuCI web authentication does not fix TCP authentication. API Write must also be enabled in WhatsminerTool. Setup deliberately does not validate credentials by sending a power command.

API code **-1** is a generic miner failure, not a diagnosis. The integration sends the documented object `{percent, mode}` and does not automatically fall back to another mode or retry the write.

The action error now includes the requested percentage/mode and a sanitized firmware explanation when one is returned. The percentage number entity exposes `last_command`, also included in downloaded diagnostics: requested value, adjustment mode, reported miner work mode, tuning flag, status and API failure code. It contains no configured credentials or authentication token.

For `normal` adjustment, check that tuning has finished and that an air-cooled miner is in Normal/Low Power mode. `fast` is an explicitly selected alternative with different stability/performance behavior; it is never selected automatically after a failure. Check active miner protection errors and verify API Write/account permissions as appropriate. Web Basic/LuCI authentication does not control TCP API power-command authentication.

## Individual chip temperatures

The default web profile uses:

```text
Protocol: https
Port: 443
Path: /cgi-bin/luci/admin/status/btminerapi
Authentication: luci
JSON Pointer: leave blank for HTML or text
```

The integration reads `C<n>` chip records inside `slot:` blocks from the page's `textarea#syslog`. It preserves the source IDs, including zero-based IDs such as `C0`; it does not rename them to `U1` or infer temperatures from board statistics.

Each map chip also carries the available `frequency_raw`, `voltage_raw`, `nonce`, `errors`, `crc_errors`, `x`, `x_secondary`, `repeat`, `pct` and `pct_secondary` fields. The card shows them when selecting a chip. They are also attributes of individual chip temperature sensors, which remain disabled by default. Voltage and frequency scales/units are unverified for this log, so raw readings are not converted to volts or assigned MHz. The two x/pct values retain source order without assigning undocumented meanings. Counters are snapshots, not calculated rates.

LuCI credentials are separate from API credentials. Certificate verification is enabled by default. For a trusted local miner with a self-signed certificate, you can explicitly disable **Verify HTTPS certificate** in the web options. This affects only that miner's web requests.

The supplied path is known, but the private device cannot be reached from this development environment. A supplied page response has been successfully parsed as three 172-chip boards. Live retrieval from this private device has not been verified. See [WEB_CHIPS.md](WEB_CHIPS.md) for capture instructions, supported formats and authentication behavior.

## Heatmap

See [HEATMAP.md](HEATMAP.md). The live card uses actual individual chip data. Without confirmed coordinates it displays a clearly labelled **logical grid**, which does not imply physical adjacency on the board.

Run the synthetic 172-chip demo locally:

```bash
python -m http.server 8000
```

Open `http://localhost:8000/examples/heatmap-demo.html`. The demo does not connect to a miner. Its PNG preview is a static illustration, not a screenshot of a running Home Assistant dashboard.

## Diagnostics and availability

From a computer on the miner's network, with Python 3.11+:

```powershell
py tools\probe.py 192.168.1.100
```

The probe performs API reads only and prints model, firmware, API version and selected telemetry. It excludes salts, MAC addresses, serial numbers and pool credentials. API 2.x on port 4028 is not supported.

An API failure makes API entities unavailable. A web failure invalidates individual chip data and heatmaps without discarding otherwise valid API readings. The LuCI session is isolated per miner and closed when the integration unloads. Diagnostic downloads exclude configured credentials, cookies and endpoint URLs.

## Uninstall

Remove the integration entry under **Devices & services**, then remove its HACS installation or custom component directory if desired. Previously commanded power is not automatically restored; restore it explicitly on the miner when necessary. Removing the integration does not change API Write on the miner.

## Validation and references

See [VALIDATION.md](VALIDATION.md) for test coverage and remaining hardware limitations.

- [Official WhatsMiner API](https://apidoc.whatsminer.com/)
- [HACS integration requirements](https://www.hacs.xyz/docs/publish/integration/)
- [HACS custom repositories](https://www.hacs.xyz/docs/faq/custom_repositories/)
- [Public client demonstrating the LuCI btminerapi log format](https://github.com/HashSource/whatsminer_chip_map/blob/master/src/api.rs)

MIT License. This is not an official MicroBT integration.
