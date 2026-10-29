# Individual chip data from the web interface

Version **0.4.0** supports the LuCI `btminerapi` HTML syslog page, the equivalent plain-text log, and normalized JSON. LuCI authentication and session renewal are implemented and tested against a local server. **A supplied device response has been parsed successfully: three boards, 172 chips per board, C0 through C171, with no missing temperature readings.** Live authentication and retrieval on the user's private network remain unverified.

## Known endpoint

The supplied endpoint path is:

```text
https://MINER_IP/cgi-bin/luci/admin/status/btminerapi
```

New web configuration forms prefill HTTPS, port 443 and `/cgi-bin/luci/admin/status/btminerapi`. The host is taken from the configured miner, rather than embedded in source. Existing explicitly configured protocol, port and path values are preserved.

This private device is not reachable from the development environment. The supplied HTML confirms the expected syslog format; network access and the authenticated session still have to be checked from Home Assistant.

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

The parser accepts whitespace variations and HTML-escaped textarea content. A login page, missing/truncated syslog textarea or unsupported response does not produce false temperatures. Leave **JSON Pointer blank** for HTML or plain text.

A public client using this same page and log format is documented [here](https://github.com/HashSource/whatsminer_chip_map/blob/master/src/api.rs). The Python adapter uses its own HTMLParser-based extraction and field validation; no third-party runtime code is bundled.

## Authentication and HTTPS

Select **luci** to use web username/password credentials. The client first reads the data page. If authentication is required, it posts the credentials to the same miner's `/cgi-bin/luci`, then retries the data read once. It uses an isolated cookie jar per miner that accepts cookies for IP-address hosts. An expired session is renewed on the next read; a failed login is not repeatedly retried in a loop.

Other supported choices are **none**, **basic** and **cookie**. The cookie option uses an explicitly supplied session cookie without automatic renewal. API and web passwords are separate. Blank secret fields in the options flow preserve existing values.

HTTPS certificate verification is **enabled by default**. If the trusted local miner uses a self-signed certificate, explicitly uncheck **Verify HTTPS certificate** in the web options. An HTTPS certificate failure is reported as `web_tls_error`; the integration never disables verification automatically. Ordinary redirects are not followed, and login credentials are sent only to the configured miner.

Only data GET requests and the LuCI authentication POST are used. This web client does not send miner configuration or power commands. Digest, Bearer authentication, WebSocket data and arbitrary POST-based data endpoints are not implemented.

## Normalized JSON

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

For a nested response, configure a JSON Pointer such as `/data` for `{"data":{"boards":[...]}}`. Optional zero-based integer `row` and `column` fields describe explicit positions, whose physical accuracy must be checked.

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
