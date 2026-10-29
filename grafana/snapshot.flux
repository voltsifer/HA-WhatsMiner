// The right edge of the dashboard time range selects a historical moment.
// Only one bounded window is read, even when inspecting a date a year ago.
snapshotStart = time(v: int(v: v.timeRangeStop) - int(v: duration(v: "${lookback}")))
from(bucket: ${bucket:doublequote})
  |> range(start: snapshotStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "whatsminer_chip_snapshots" and r._field == "chip_snapshot_str" and r.domain == "sensor")
  |> filter(fn: (r) => r.entity_id =~ /^${boards:regex}$/)
  |> group(columns: ["entity_id"])
  |> sort(columns: ["_time"])
  |> last()
  |> keep(columns: ["_time", "_value", "entity_id"])
