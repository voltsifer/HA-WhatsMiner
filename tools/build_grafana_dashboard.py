#!/usr/bin/env python3
"""Build the importable dashboard from its readable chart and Flux sources."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "grafana/whatsminer-m60vk2a.json"
DATASOURCE = {"type": "influxdb", "uid": "${DS_INFLUXDB}"}


def build():
    """Return an ordinary Grafana classic dashboard, without credentials."""
    chart = (ROOT / "grafana/heatmap.js").read_text()
    flux = (ROOT / "grafana/snapshot.flux").read_text()
    board_query = '''import "influxdata/influxdb/schema"
schema.tagValues(bucket: ${bucket:doublequote}, tag: "entity_id",
  predicate: (r) => r._measurement == "whatsminer_chip_snapshots", start: -730d)'''
    metric_options = [
        ("Temperature", "temperature"), ("Voltage (raw)", "voltage_raw"),
        ("Frequency (raw)", "frequency_raw"), ("Errors", "errors"),
        ("CRC errors", "crc_errors"), ("Nonce", "nonce"), ("Repeat", "repeat"),
        ("x (first)", "x"), ("x (second)", "x_secondary"),
        ("pct (first, %)", "pct"), ("pct (second, %)", "pct_secondary"),
    ]
    options = [{"text": text, "value": value, "selected": index == 0}
               for index, (text, value) in enumerate(metric_options)]
    return {
        "id": None, "uid": "ha-whatsminer-m60vk2a", "title": "HA-WhatsMiner · M60VK2A history",
        "description": "Hourly board snapshots from InfluxDB 2 / Flux. WEB-to-PCB correspondence remains unverified. See GRAFANA.md.",
        "tags": ["HA-WhatsMiner", "M60VK2A"], "schemaVersion": 39, "version": 2,
        "editable": True, "timezone": "browser", "refresh": "5m",
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {"refresh_intervals": ["1m", "5m", "15m", "1h"]},
        "annotations": {"list": []}, "links": [],
        "templating": {"list": [
            {"name": "DS_INFLUXDB", "label": "InfluxDB / Flux", "type": "datasource",
             "query": "influxdb", "refresh": 1, "options": [], "current": {}},
            {"name": "bucket", "label": "Bucket", "type": "textbox", "query": "HAOS",
             "options": [{"text": "HAOS", "value": "HAOS", "selected": True}],
             "current": {"text": "HAOS", "value": "HAOS"}},
            {"name": "boards", "label": "Board maps (up to 3)", "type": "query",
             "datasource": DATASOURCE, "query": board_query, "definition": board_query,
             "refresh": 1, "sort": 1, "multi": True, "includeAll": True,
             "options": [], "current": {"text": "All", "value": "$__all", "selected": True}},
            {"name": "metric", "label": "Metric", "type": "custom", "multi": False,
             "includeAll": False, "query": ", ".join(f"{text.replace(',', '')} : {value}" for text, value in metric_options),
             "options": options, "current": options[0]},
            {"name": "lookback", "label": "Snapshot lookback", "type": "custom",
             "query": "1h,2h,6h,24h", "multi": False, "includeAll": False,
             "options": [{"text": value, "value": value, "selected": value == "2h"}
                         for value in ("1h", "2h", "6h", "24h")],
             "current": {"text": "2h", "value": "2h", "selected": True}},
        ]},
        "panels": [{
            "id": 1, "type": "volkovlabs-echarts-panel", "title": "M60VK2A chip snapshots",
            "description": "To selects the historical moment. Hover for all chip metrics. Timestamps are UTC. Missing readings are gray. U labels and some positions are assumed; see GRAFANA.md.",
            "datasource": DATASOURCE, "gridPos": {"x": 0, "y": 0, "w": 24, "h": 24},
            "transparent": False, "fieldConfig": {"defaults": {}, "overrides": []},
            "targets": [{"refId": "A", "datasource": DATASOURCE, "query": flux}],
            "options": {"editorMode": "code", "getOption": chart, "renderer": "svg", "map": "none",
                        "themeEditor": {"name": "default", "config": "{}"},
                        "editor": {"format": "auto"},
                        "visualEditor": {"dataset": [], "series": [], "code": ""},
                        "baidu": {"key": "", "callback": "bmapReady"},
                        "gaode": {"key": "", "plugin": "AMap.Scale,AMap.ToolBar"},
                        "google": {"key": "", "callback": "gmapReady"}},
        }],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the generated dashboard differs")
    args = parser.parse_args()
    content = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"
    if args.check:
        if not DESTINATION.exists() or DESTINATION.read_text() != content:
            parser.exit(1, "Grafana dashboard differs; run python tools/build_grafana_dashboard.py\n")
        print("Grafana dashboard matches its sources")
    else:
        DESTINATION.write_text(content)
        print(DESTINATION.relative_to(ROOT))


if __name__ == "__main__":
    main()
