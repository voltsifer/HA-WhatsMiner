# Individual chip data from the web interface

Version **0.5.4** uses a built-in LuCI `btminerapi` profile. The parser accepts the HTML syslog page, the equivalent plain-text log, and normalized JSON. LuCI authentication and session renewal are implemented and tested against a local server. **A supplied device response has been parsed successfully: three boards, 172 chips per board, C0 through C171, with no missing temperature readings.** The user has confirmed live chip retrieval in HAOS on an M60VK2A; this development environment cannot independently reach the private miner.

## Known endpoint

The supplied endpoint path is:

```text
https://MINER_IP/cgi-bin/luci/admin/status/btminerapi
```

HTTPS, port 443, `/cgi-bin/luci/admin/status/btminerapi` and LuCI authentication are fixed by the integration. The host is taken from the configured miner. Web forms contain username, password, Verify HTTPS certificate and Chip data polling interval (seconds). Protocol, port, GET path, authentication method, JSON Pointer and a session cookie are not user settings.

On upgrade, obsolete web keys are removed from both saved data and options. The current web credentials and explicit certificate choice are preserved; a legacy custom endpoint/authentication choice is replaced with the built-in profile. The migration does not send device configuration or power commands.

This private device is not reachable from the development environment. The supplied HTML confirms the expected syslog format; network access and the authenticated session still have to be checked from Home Assistant.

## Independent polling interval

WEB chip data is read every **3600 seconds** by default, including existing entries without `web_scan_interval`. This covers temperatures and all optional chip metrics in the same request. API polling remains independent, normally every 30 seconds. The first WEB read after setup/reload is immediate; later reads occur on the first successful API poll at or after the chip deadline, so the actual interval can be slightly longer than configured.

Change **Chip data polling interval (seconds)** in the WEB step of the integration options to a value from 60 to 86400. Chip readings, metrics and `updated_at` are cached without changing their measurement time between WEB reads. A failed scheduled read invalidates the chip data and waits the configured chip interval before retrying; it does not retry on every API poll. Saving options or reloading the integration starts with a fresh read.

## Save the response for verification

On a computer that can reach the miner:

1. Sign in to the miner's web interface and open the `btminerapi` URL.
2. Press **F12 → Network**, select **All**, and reload the page.
3. Select the request named **btminerapi**. It may be a **Document**, not a Fetch/XHR request.
4. Open **Response**. Right-click the request and choose **Copy → Copy response**.
5. Save that text as `btminerapi.html` or `btminerapi.txt` and attach it for parser verification. If copying the response is inconvenient, save the page's original HTML source.
6. Include the miner model and firmware version. Do not include passwords, cookies, Authorization headers or session tokens. Do not export a full authenticated HAR.

The contents of the visible syslog text area are also sufficient if they contain complete `slot:` headers and chip records. Keep at least one complete board's records so the 172-chip count can be checked.

A screenshot helps with layout, but the actual text or HTML is needed to verify parsing. Captured device responses must be sanitized before being committed; repository tests use synthetic data only.

## Supported LuCI log shape

The HTML adapter extracts only **`textarea#syslog`**. Its contents, or a direct text response, contain records shaped like this synthetic example:

```text
slot: 0, freq: 700, temp: 70, step: 1
C0 freq:700 vol:1200 temp:91.3 nonce:123 err:0 crc:0 x:0 / 2 repeat:0 pct:99.3%/96.6%
C1 freq:700 vol:1200 temp:92.1 nonce:456 err:0
```

Each chip remains attached to its explicit slot. The parser preserves source IDs such as `C0`; it does not shift numbering to `U1`. Board `temp` values are not substituted for chip `temp` values. Missing or invalid chip measurements become missing readings, not zero. Duplicate chip identities or board slots are rejected.

### Additional per-chip fields

The same request collects these optional numeric fields; no additional miner polling is needed:

| Log field | Normalized key | Interpretation |
| --- | --- | --- |
| `freq` | `frequency_raw` | Raw firmware frequency value; unit/scale unverified |
| `vol` | `voltage_raw` | Raw firmware voltage value; unit/scale unverified; no conversion to V/mV |
| `nonce` | `nonce` | Non-negative integer snapshot |
| `err` | `errors` | Non-negative integer snapshot |
| `crc` | `crc_errors` | Non-negative integer snapshot |
| `x:a / b` | `x`, `x_secondary` | Both non-negative integer values, in source order |
| `repeat` | `repeat` | Non-negative integer snapshot |
| `pct:a%/b%` | `pct`, `pct_secondary` | Both displayed percentage values, in source order; values over 100 are preserved |

The firmware-specific meanings of x/pct, reference intervals and counter reset behavior are not inferred. Missing fields are omitted; invalid supplied values become null. Counter negatives/fractions and non-finite/boolean values are invalid. No totals, rates, fault classification or voltage conversions are synthesized. Unknown fields are discarded rather than exposing arbitrary log contents. A chip record can retain other measurements even when its temperature is missing.

The parser accepts whitespace variations and HTML-escaped textarea content. A login page, missing/truncated syslog textarea or unsupported response does not produce false temperatures. HTML and plain text use the root response without a JSON Pointer.

A public client using this same page and log format is documented [here](https://github.com/HashSource/whatsminer_chip_map/blob/master/src/api.rs). The Python adapter uses its own HTMLParser-based extraction and field validation; no third-party runtime code is bundled.

## Authentication and HTTPS

LuCI login automatically uses the configured web username/password credentials (the username defaults to admin). The client first reads the data page. If authentication is required, it posts the credentials to the same miner's `/cgi-bin/luci`, then retries the data read once. It uses an isolated cookie jar per miner that accepts cookies for IP-address hosts. An expired session is renewed on the next read; a failed login is not repeatedly retried in a loop.

HTTP Basic, manually supplied cookies, alternative paths/protocols and JSON Pointers are not exposed or used by the integration. Low-level parser/transport helpers retain compatibility for development tests. API and web passwords are separate. A blank web password in the options flow preserves the existing value; the API password is never reused automatically. The API super account password must not be assumed to equal the web admin account password.

HTTPS certificate verification is **enabled by default**. If the trusted local miner uses a self-signed certificate, explicitly uncheck **Verify HTTPS certificate** in the web options. An HTTPS certificate failure is reported as `web_tls_error`; the integration never disables verification automatically. Ordinary redirects are not followed, and login credentials are sent only to the configured miner.

Only data GET requests and the LuCI authentication POST are used. This web client does not send miner configuration or power commands. Digest, Bearer authentication, WebSocket data and arbitrary POST-based data endpoints are not implemented.

## Parser JSON contract (development)

The fallback JSON contract is an integration format; it is not claimed to be the firmware's native JSON schema:

```json
{
  "boards": [
    {
      "slot": 0,
      "chips": [
        {"id": "C0", "temperature": 91.3},
        {"id": "C1", "temperature": null}
      ]
    }
  ]
}
```

The parser helper supports nested responses with a JSON Pointer for development, but custom JSON endpoints and pointers are not configuration features. Optional zero-based integer `row` and `column` fields describe explicit positions, whose physical accuracy must be checked.

`tools/inspect_web_response.py response.json` summarizes a saved JSON schema without printing string values or authentication headers. It is a JSON inspection tool; use the saved HTML/text directly when inspecting LuCI.

## Entities and availability

After a successful response:

- **Board N web chip map** reports the maximum individual chip temperature. Its `chips` attribute contains IDs and measurements, with `updated_at` and `chip_count` metadata.
- Individual chip temperature sensors are created disabled by default. Their attributes expose the same optional chip metrics. Enable selected sensors for history or automations; no additional entity is created for every metric of every chip. Use a template sensor for a selected metric when separate metric history is required.
- **Web chip data status** reports `ok` or a sanitized failure reason.

A web failure invalidates chip entities and maps without dropping valid API telemetry. Chip arrays and update timestamps are excluded from Recorder attributes; enable specific chip sensors for individual history. Historical heatmap playback is not implemented.

Example template for a selected, enabled chip temperature sensor (replace the entity ID):

```yaml
template:
  - sensor:
      - name: "Selected chip errors"
        availability: >-
          {{ has_value('sensor.replace_with_chip_temperature') and
             is_number(state_attr('sensor.replace_with_chip_temperature', 'errors')) }}
        state: "{{ state_attr('sensor.replace_with_chip_temperature', 'errors') }}"
```

No `total_increasing` state class is assigned because firmware counter reset semantics have not been verified. This template is unavailable if that chip's temperature sensor is unavailable; the board's `chips` attribute can still retain other valid metrics when temperature is missing. Diagnostics include the normalized chip boards without raw HTML or credentials.

## Enable chip entities and inspect metrics

Individual chip temperature sensors are disabled by default by design. Upgrade/reload does not override entity choices previously made by the user. To enable all selected entities, open **Settings → Devices & services → Entities**, filter by **HA-WhatsMiner** (and the required miner device) and **Status: Disabled**, enter selection mode, select the entities, then choose **Action → Enable selected**. Wait for entity loading or reload the integration if requested by HA. Do not edit `.storage` manually.

The heatmap needs only the enabled **Board N web chip map** sensors, not all 516 individual temperature sensors. Reading the web page and collecting optional metrics also do not depend on those individual sensors being enabled.

To inspect additional metrics, open **Developer tools → States**, select a **Board N web chip map** sensor and inspect `chips`. Each item contains its ID, temperature and the available optional metric fields listed above. An enabled individual chip temperature sensor exposes those metrics as attributes. No separate per-chip voltage/frequency/error entities are created. If a firmware field is absent, it is omitted; invalid values are null. Missing source fields cannot be enabled into existence.
