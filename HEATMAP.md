# Chip heatmap card

The heatmap is a dashboard card; it does not automatically create a dashboard or appear as a full map on the miner device page. The card requires individual chip readings from the web adapter. API board minimum/average/maximum statistics are insufficient to reconstruct individual temperatures.

## Register the resource

The JavaScript is installed with the integration, including HACS installations. After installing and restarting Home Assistant:

1. Open the dashboard resource settings. Depending on HA version, use **Settings → Dashboards → menu ⋮ → Resources**. Advanced Mode in your profile may be needed.
2. Add **`/ha-whatsminer/ha-whatsminer-heatmap-card.js`**, type **JavaScript module**. Use this permanent URL without a version query parameter.
3. Reload the browser. After integration upgrades, restart Home Assistant and reload the dashboard page; the resource URL stays unchanged. If an old card remains cached, perform a hard refresh or clear the frontend cache. An already open page keeps its loaded JavaScript until it is reloaded.
4. Open your dashboard, select **Edit → Add card → Manual**, and use automatic discovery. Individual chip temperature sensors can remain disabled:

```yaml
type: custom:ha-whatsminer-heatmap-card
title: WhatsMiner chip temperatures
auto_discover: true
columns: 14
min_temperature: 70
max_temperature: 110
```

Automatic discovery finds enabled Board N web chip map sensors by their source/slot/chips attributes, including renamed entities. It discovers all available miners, not just the first miner or three fixed boards. Board friendly names identify the sources. A new board appears on the next HA state update; known sources that become unavailable display a data error rather than stale temperatures. No entities or settings are changed by discovery. `columns` controls the logical grid width, not physical board geometry. A board with 172 readings produces 172 chip cells, including cells whose readings are missing. The 70–110°C values define only the color scale, not recommended operating limits. The card picker also provides an automatic-discovery starter configuration without placeholder entity IDs.

If you previously registered a URL ending in `?v=...`, edit that existing resource once and remove the query parameter. Do not add a duplicate resource. The unversioned path is already supported by the integration; no new integration release is required for this URL change. The static resource is registered with Home Assistant's long-lived cache headers disabled.

## Explicit selection (optional)

If several miners are configured and a card should show only selected boards, omit `auto_discover` and specify the actual board map entity IDs:

```yaml
type: custom:ha-whatsminer-heatmap-card
entities:
  - sensor.replace_with_actual_board_map
columns: 14
```

This explicit example requires replacing its placeholder. Find the actual IDs under **Developer tools → States** or on the miner device page. A non-existent entity is reported as **entity does not exist**, with instructions to use real IDs or automatic discovery. Do not combine `auto_discover: true` with `entity` or `entities`. When neither is specified, discovery is enabled by default.

## Display

- Every source chip ID and temperature.
- Board minimum, average, maximum and available reading count.
- Selected chip details, including deviation from its board median and available frequency/voltage raw values, nonce/error/CRC/repeat snapshots, and both x/pct values. Hover or select a chip to inspect them; the color scale still represents temperature.
- A switch between absolute temperature and median deviation. The deviation scale is fixed at −15 to +15°C.
- Gray hatching for missing measurements.
- Last successful update time. A source error replaces the old map with an unavailable message.

Raw voltage and frequency units/scales and x/pct meanings are unverified. Counters are snapshots; the card does not calculate error rates. Other telemetry remains selectable when chip temperature is missing.

The card does not infer missing temperatures from neighbors. A statistical temperature deviation alone does not prove a hardware fault.

All card labels and error messages are English. Existing Home Assistant entity IDs and customized names remain under HA's entity registry control.

## Exclude chip data from InfluxDB

HeatMap uses live Home Assistant states, so chip entities can remain enabled while their export to InfluxDB is excluded. Merge these filters into your existing `influxdb:` section in `configuration.yaml`; do not add a second section or replace your connection settings:

```yaml
influxdb:
  exclude:
    entity_globs:
      - sensor.*_chip_*_web_temperature
      - sensor.*_web_chip_map
```

These patterns target the default individual chip and board-map entity IDs. Check the actual IDs under **Developer tools → States**. For renamed entities that no longer match, add their actual IDs to `exclude.entities`.

Existing `include.entities` entries and matching `include.entity_globs` take priority over these exclusion globs. Remove or narrow conflicting include rules. The integration's Recorder `_unrecorded_attributes` setting is separate and does not act as an InfluxDB entity filter.

Validate the Home Assistant configuration, then restart Home Assistant to apply the YAML changes. Verify that HeatMap still updates and that no new points arrive for the excluded entities. Previously stored InfluxDB data is unaffected. See the official [InfluxDB configuration and filter documentation](https://www.home-assistant.io/integrations/influxdb/).

## Physical layout

Without verified geometry, the card explicitly labels its arrangement as a **logical grid**. Response order does not establish a chip's physical location.

### M60VK2A preset

Version 0.5.3 adds an optional, photo-based reconstruction for an **M60VK2A board with 172 chips**. Select it explicitly:

```yaml
type: custom:ha-whatsminer-heatmap-card
title: M60VK2A chip temperatures
auto_discover: true
layout: m60vk2a
min_temperature: 60
max_temperature: 100
```

A ready-to-copy configuration is also available in [examples/m60vk2a-heatmap.yaml](examples/m60vk2a-heatmap.yaml). The preset supplies its own 22-column arrangement; `columns` is not needed for it. It creates no additional entities and uses the existing web board maps.

The orientation follows the supplied board photographs: **power contacts on the left, signal connector on the right**. There are eight chip rows, with an upper block of 84 positions and a lower block of 88 positions, separated by a central gap. Visible PCB labels support the alternating direction of the four-chip columns. Partly covered positions and endpoints are reconstructed from that pattern; horizontal alignment and spacing are schematic rather than a measurement of the PCB.

**The mapping from WEB IDs `C0…C171` to PCB labels `U1…U172` is unverified.** The preset currently assumes `Cn → U(n+1)`. It keeps a visible warning, and any PCB labels it shows are assumed labels. The temperature and other telemetry still come from the source `C…` records; the assumption affects their placement. Verify this correspondence before using a cell to locate a physical chip.

This is not a manufacturer schematic or an automatically detected board profile. No supplied photographs or board serial numbers are distributed with the preset. Selecting `layout: m60vk2a` applies it to all board maps in that card. If automatic discovery would include miners with different board models, use explicit entity selection instead.

An unknown `layout` value is rejected. Do not combine the named `layout` option with the manual `layouts` option below.

### Manual layout

After checking the labels against a photo or documentation for the actual hashboard, provide a layout indexed by slot. This is a syntax example, not a model-specific board diagram:

```yaml
layouts:
  "0":
    - [C0, C1, C2]
    - [C5, C4, C3]
```

Use the actual IDs returned by your source. LuCI logs commonly use `C0` and subsequent zero-based IDs. A normalized JSON source can use other explicit IDs; the integration preserves them.

`null` entries leave empty physical positions. Chips omitted from a configured layout remain visible in a separate section. A layout position whose chip is absent from the response shows a missing reading. If all source chips include explicit `row` and `column` fields, the card can use them, while still asking you to verify the mapping against the board.

Manual `layouts` continue to use the supplied source IDs without applying the preset's assumed PCB numbering. Each slot can have its own matrix. When several miners share the same slot numbers, restrict the card to the intended entities so a slot's matrix is not applied to unrelated boards.

`examples/heatmap-demo.html` demonstrates one logical board with 172 chips and synthetic data, without miner requests. Serve the project with `python -m http.server 8000` to open it locally.

## Troubleshooting

- **Custom element does not exist**: verify the JavaScript resource URL and module type, then reload the browser. Installing the integration through HACS does not automatically register this custom dashboard resource.
- **Entity does not exist**: the configuration points to an unknown ID, often an unchanged example. Remove `entity`/`entities` and use `auto_discover: true`, or select actual board map entities.
- **No web chip maps found**: no suitable source is visible yet. Enable web chip data and the board map sensors, then check Web chip data status.
- **No fresh chip data**: check that the selected entity is a Board N web chip map sensor, is enabled and available, and exposes a non-empty `chips` attribute. Check Web chip data status for a source/login/certificate failure.
- **No separate voltage/error entities**: optional chip metrics are attributes of each chip, not additional sensor entities. Select or hover a chip to inspect them. The map color scale remains temperature-only.
- **Unknown layout**: use the supported `layout: m60vk2a` value with card version 0.5.3 or later, then reload the browser after updating. Remove `layout` to return to the logical grid, or use a manual `layouts` matrix instead.
- **Both layout options specified**: keep either the named `layout` preset or manual `layouts`, not both.
- **M60VK2A mapping warning**: this is intentional. The preset's `Cn → U(n+1)` correspondence has not been verified; selecting the preset does not establish that correspondence or turn it into a manufacturer drawing.
