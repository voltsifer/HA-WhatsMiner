# Historical chip heatmap in Grafana

The Grafana dashboard displays M60VK2A chip snapshots from InfluxDB 2.x. It uses the same photo-based placement as the Home Assistant card and shows U labels on the cells. The original WEB C IDs and all available chip metrics remain in the snapshot and tooltips. **WEB Cn to PCB U(n+1) is an unverified correspondence.** Some positions and alignment are reconstructed; this is not a manufacturer schematic.

The dashboard reads archived data only. It does not contact the miner, send commands or create Home Assistant entities. It cannot recreate measurements that were never stored or have expired from InfluxDB.

## Files

| File | Purpose |
| --- | --- |
| [grafana/whatsminer-m60vk2a.json](grafana/whatsminer-m60vk2a.json) | Dashboard to import into Grafana |
| [grafana/heatmap.js](grafana/heatmap.js) | Source of the Business Charts function embedded in the dashboard |
| [grafana/snapshot.flux](grafana/snapshot.flux) | Snapshot query used by the dashboard |
| [examples/grafana-influxdb.yaml](examples/grafana-influxdb.yaml) | Home Assistant export settings for the existing InfluxDB connection |

Use the matching integration and dashboard files from the same repository revision.

## Requirements

- HA-WhatsMiner with the `chip_snapshot` board-map attribute, WEB chip data enabled and the required **Board N web chip map** sensors enabled. The 516 individual chip sensors may remain disabled.
- A working Home Assistant InfluxDB 2.x integration. Installing the InfluxDB2 server app alone does not configure Home Assistant to export states.
- An InfluxDB 2.x data source in Grafana configured for the **Flux** query language, with read access to the bucket that receives Home Assistant data.
- The signed **Business Charts** panel, plugin ID `volkovlabs-echarts-panel`. The current catalog release, **7.2.5**, requires **Grafana 12.3.0 or newer**. Older plugin releases have different requirements; check the catalog metadata for the selected version. The older 6.x series uses the same context-based chart API and targets Grafana 10/11, but this dashboard has not been tested against every historical plugin release.

The panel is implemented with Business Charts rather than a manually maintained Canvas containing 516 separate data bindings. Business Charts reads each complete board JSON snapshot and renders the selected metric at the chip positions.

## 1. Export board snapshots from Home Assistant

These settings belong in **`/config/configuration.yaml`**, not in the InfluxDB2 app's Options editor and not in Grafana. Connection settings can remain in the Home Assistant integration UI.

Merge [examples/grafana-influxdb.yaml](examples/grafana-influxdb.yaml) into the existing top-level `influxdb:` section. If that section does not exist, add it. Do not create a second `influxdb:` section or replace existing connection settings, unrelated filters or measurement overrides.

```yaml
influxdb:
  exclude:
    entity_globs:
      - "sensor.*_chip_*_web_temperature"
  component_config_glob:
    "sensor.*_web_chip_map":
      override_measurement: whatsminer_chip_snapshots
      ignore_attributes:
        - chips
        - updated_at
        - slot
        - source
        - chip_count
        - friendly_name
        - device_class
        - state_class
        - unit_of_measurement
```

**Remove the earlier `sensor.*_web_chip_map` exclusion if you added it.** Keep the individual chip exclusion if you want to avoid storing 516 separate entity series. A board map excluded by another entity/domain/glob filter will not be exported. If an existing include list restricts export, add the actual board maps to that list while preserving other entries. Explicit entity includes and matching include globs can override individual chip exclusion globs; check conflicting rules.

The glob above matches default board-map IDs. If you renamed a map so that its ID no longer ends in `_web_chip_map`, use its actual entity ID under `component_config` with the same `override_measurement` and `ignore_attributes` settings. Remove that actual ID from exclusion lists as well. Find IDs under **Developer tools → States**; display names and entity IDs are different.

Do not add `chip_snapshot` to `ignore_attributes` or `tags_attributes`. It must remain a string field. If it appears in an existing global ignore list, remove it there; per-entity settings cannot undo a global ignore rule.

Validate the configuration, then restart Home Assistant. The first WEB read after integration setup/reload is immediate. Later WEB reads use **Chip data polling interval (seconds)**, normally **3600**. API power, fans and other telemetry retain their separate polling interval.

### Snapshot contract

Each enabled board map exposes `chip_snapshot`, an actual JSON string containing:

```json
{
  "schema_version": 1,
  "slot": 0,
  "updated_at": "2026-10-29T13:00:00+00:00",
  "chips": [
    {"id": "C0", "temperature": 73, "voltage_raw": 275, "errors": 0}
  ]
}
```

This example contains one chip only to illustrate the format; a normal M60VK2A snapshot contains 172 records per board. Each record preserves the original source ID and normalized available metrics. Missing measurements remain null or absent.

Home Assistant's InfluxDB integration stores a nonnumeric string attribute with a `_str` suffix, so this becomes field **`chip_snapshot_str`** in measurement **`whatsminer_chip_snapshots`**. The `entity_id` tag contains the Home Assistant object ID **without** `sensor.`. The JSON carries the completion time of the successful WEB read, using the Home Assistant clock; it does not claim to be a firmware-side sampling timestamp. The InfluxDB point timestamp represents the state event/export time and is not used as a substitute measurement time.

The existing `chips` array is deliberately ignored for InfluxDB: its automatic string conversion is a Python representation, not a stable JSON contract. Both `chips` and `chip_snapshot` remain excluded from Recorder attributes. Recorder exclusions do not automatically exclude them from InfluxDB.

A new successful WEB read changes the embedded timestamp even if the temperatures are unchanged, allowing the board state event to carry a complete new snapshot. Between WEB reads the timestamp remains unchanged; API polling does not fabricate new chip measurements.

Home Assistant's InfluxDB integration skips states that are `unknown` or `unavailable`. Therefore a board whose temperatures are all missing may have other metrics in live HA attributes but will not produce a new archived snapshot through this temperature-state export. WEB/API outages also leave gaps. A previously stored snapshot does not prove that the miner remained healthy until the next snapshot.

## 2. Install Business Charts

For the **Home Assistant Community Grafana app**, open the app configuration and add the plugin ID to its existing `plugins` list:

```yaml
plugins:
  - volkovlabs-echarts-panel
```

Keep any plugins already in that list and preserve the other app settings. Save and restart the **Grafana app**. Plugin installation can make this restart take longer. This is a signed catalog plugin; the dashboard does not require enabling unsigned plugins or installing a custom URL.

For standalone Grafana, use its plugin catalog or the supported Grafana CLI. Verify that the selected plugin version supports the installed Grafana version before installation. The app's `plugins` option normally installs a catalog version; update Grafana first if it is too old for that version.

## 3. Import and configure the dashboard

1. Download [grafana/whatsminer-m60vk2a.json](grafana/whatsminer-m60vk2a.json) from the repository.
2. In Grafana, open the dashboard import dialog and upload the JSON file.
3. In the dashboard toolbar, select the existing **InfluxDB / Flux** data source. It must use Flux; an InfluxQL data source cannot run this dashboard.
4. Set **Bucket** to the actual bucket receiving Home Assistant data. `HAOS` is the initial example value, not an automatically discovered setting.
5. Select the intended board-map series. Do not mix boards from different miners unless that is intentional. The series identifiers use the actual exported entity object IDs, so renamed entities can also be selected after their first snapshot is stored.
6. Start with **Temperature** and a **2h** snapshot lookback. Save the dashboard after choosing the intended data source, bucket and boards.

The chart displays snapshot times in **UTC**, explicitly marked in its labels. The Grafana time picker uses the dashboard/browser timezone; both refer to the same instant. Select up to three boards; selecting more shows an instruction instead of silently omitting boards.

The metric selector includes temperature, raw frequency and voltage, nonce/errors/CRC/repeat counters, both x values and both pct values. Voltage/frequency scales and x/pct meanings remain unverified. Counter values are snapshots, not calculated rates. Missing selected metrics are shown as missing readings rather than zero.

## 4. Choose a historical moment

Use Grafana's time picker and set the **To** value to the date and time to inspect. The map represents that endpoint, not an average over the dashboard's entire From–To range. Each board query returns its latest archived snapshot within the selected lookback ending at **To**. The bounded query avoids loading an entire year of snapshots just to draw one map.

The map shows each snapshot's real `updated_at` time. It rejects future or excessively old measurements rather than carrying old values indefinitely. The default lookback is two hours for hourly collection; increase it only when a longer gap or intentionally slower polling is acceptable. Selected boards may have different snapshot times, so compare the displayed times before treating them as simultaneous measurements.

For a moment a year ago, those measurements must already exist in the selected bucket. Starting collection today creates future history; changing Grafana's time range cannot restore missing history. An hourly interval provides hourly samples and does not capture changes between samples.

## Retention and storage

For year-old snapshots, configure a retention period longer than a year, for example **730 days**, on the receiving InfluxDB bucket. In InfluxDB 2.x, open **Load Data → Buckets → Settings** for the bucket and edit its retention period. Increasing retention does not recover points already deleted.

Three boards sampled hourly produce `3 × 24 × 365 = 26,280` board snapshots per 365-day year, containing `3 × 172 × 24 × 365 = 4,520,160` chip observations before gaps or extra reload samples. Each board snapshot carries all available metrics in one JSON field. Disk usage depends on payload size and compression; these counts are not a disk-space guarantee.

## Check the installation

- In **Developer tools → States**, a board-map sensor has a nonempty `chip_snapshot` string, the expected slot, and a plausible measurement time. Never paste passwords, tokens or authenticated page captures into the dashboard JSON.
- In the InfluxDB Data Explorer, the receiving bucket contains measurement `whatsminer_chip_snapshots`, field `chip_snapshot_str`, and one series per exported board map.
- In Grafana, the first live view matches the Home Assistant map for a snapshot with the same timestamp. Hover a chip and compare its source C ID, assumed U label and raw metric values.
- Move **To** to before collection began: the dashboard should show no snapshot. Return **To** to now and confirm it recovers.
- After the next hourly read, confirm a newer measurement timestamp is archived. Refreshing Grafana alone must not change the measurement timestamp.

## Troubleshooting and rollback

| Symptom | Check |
| --- | --- |
| Panel plugin not found | Install `volkovlabs-echarts-panel`, verify Grafana compatibility and restart the Grafana app |
| No board series | Verify bucket/data source, enabled WEB map entities, snapshot field export, default/renamed entity IDs and include/exclude rules |
| Map has no snapshot at the selected time | Collection may not have started, data may have expired, or no valid snapshot exists within the lookback |
| Snapshot field missing but other sensor data exists | Check the measurement override, remove `chip_snapshot` from ignore lists, keep it out of tags, and confirm the integration exposes the new attribute |
| Missing voltage or error readings | The firmware may not provide that field, or it may be invalid; changing the selected metric cannot create missing data |
| Old snapshot after a miner outage | Check the displayed measurement time; a bounded previous snapshot is historical evidence, not a current health indication |
| Unexpected boards | Select only the required board-map series; slots alone are not unique across miners |

To remove the visualization, delete its Grafana dashboard. To stop archiving board snapshots, restore the board-map InfluxDB exclusions or remove their export configuration and restart Home Assistant. Keep unrelated InfluxDB settings. Neither rollback deletes points already stored, changes the miner, nor removes the HA HeatMap card.

## Maintain the generated dashboard

After editing `grafana/heatmap.js` or `grafana/snapshot.flux`, run `python tools/build_grafana_dashboard.py`. Run it with `--check` to verify that the importable JSON matches its readable sources. Development tests exercise the chart with real ECharts 5.5.1 SVG rendering and resize; the user installation still needs import/Flux validation against its actual data source.

## Primary references

- [Home Assistant InfluxDB filters, measurement overrides and attribute handling](https://www.home-assistant.io/integrations/influxdb/)
- [Home Assistant InfluxDB exporter implementation](https://github.com/home-assistant/core/blob/dev/homeassistant/components/influxdb/__init__.py)
- [Business Charts catalog and current plugin compatibility](https://grafana.com/grafana/plugins/volkovlabs-echarts-panel/)
- [Business Charts data frames and context API](https://grafana.com/docs/plugins/volkovlabs-echarts-panel/latest/features/data-sources/)
- [Home Assistant Community Grafana app plugin configuration](https://github.com/hassio-addons/app-grafana/blob/main/grafana/DOCS.md)
- [Grafana time controls](https://grafana.com/docs/grafana/latest/visualizations/dashboards/use-dashboards/)
- [InfluxDB bucket retention settings](https://docs.influxdata.com/influxdb/v2/admin/buckets/update-bucket/)
- [Flux last selector](https://docs.influxdata.com/flux/v0/stdlib/universe/last/)
