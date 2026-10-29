# Individual chip data from the web interface

Version **0.3.0** supports the LuCI `btminerapi` HTML syslog page, the equivalent plain-text log, and normalized JSON. LuCI authentication and session renewal are implemented and tested against a local server. **The actual device response has not yet been captured or verified.**

## Known endpoint

The supplied endpoint path is:

```text
https://MINER_IP/cgi-bin/luci/admin/status/btminerapi
```

New web configuration forms prefill HTTPS, port 443 and `/cgi-bin/luci/admin/status/btminerapi`. The host is taken from the configured miner, rather than embedded in source. Existing explicitly configured protocol, port and path values are preserved.

This private device is not reachable from the development environment. A URL identifies where to request data, but does not supply the response body, session or firmware-specific format.

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
C0 freq:700 vol:1200 temp:91.3 nonce:123 err:0
C1 freq:700 vol:1200 temp:92.1 nonce:456 err:0
```

Each chip remains attached to its explicit slot. The parser preserves source IDs such as `C0`; it does not shift numbering to `U1`. Board `temp` values are not substituted for chip `temp` values. Missing or invalid chip measurements become missing readings, not zero. Duplicate chip identities or board slots are rejected.

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
- Individual chip sensors are created disabled by default. Enable selected sensors for history or automations.
- **Web chip data status** reports `ok` or a sanitized failure reason.

A web failure invalidates chip entities and maps without dropping valid API telemetry. Chip arrays and update timestamps are excluded from Recorder attributes; enable specific chip sensors for individual history. Historical heatmap playback is not implemented.
