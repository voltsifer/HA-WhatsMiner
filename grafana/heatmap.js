// HA-WhatsMiner 0.5.5 · Grafana dashboard revision 2 (not a browser module).
// This body is embedded verbatim in the generated Grafana dashboard.
const metrics = {
  temperature: "Temperature (°C)", voltage_raw: "Voltage (raw)",
  frequency_raw: "Frequency (raw)", errors: "Errors", crc_errors: "CRC errors",
  nonce: "Nonce", repeat: "Repeat", x: "x (first)", x_secondary: "x (second)",
  pct: "pct (first, %)", pct_secondary: "pct (second, %)",
};
const variable = name => context.grafana.replaceVariables(`\${${name}}`);
const metric = variable("metric");
const target = Number(variable("__to"));
const duration = /^(1|2|6|24)h$/.exec(variable("lookback"));
const lookback = duration ? Number(duration[1]) * 3600000 : NaN;
const textColor = context.grafana.theme?.isDark === false ? "#20252b" : "#e5e9f0";
const mutedColor = context.grafana.theme?.isDark === false ? "#536171" : "#a4b0c0";
const missingColor = "#596474";
const finite = value => typeof value === "number" && Number.isFinite(value) ? value : null;
const at = (values, index) => typeof values?.get === "function" ? values.get(index) : values?.[index];
const utc = value => new Date(value).toISOString().replace("T", " ").replace(/\.\d{3}Z$/, " UTC");
const message = text => ({ animation: false, graphic: [{ type: "text", left: 12, top: 16,
  style: { text, fill: textColor, font: "13px sans-serif", lineHeight: 20 } }] });
if (!Object.hasOwn(metrics, metric) || !Number.isFinite(target) || !Number.isFinite(lookback)) {
  return message("Select a supported Metric and Snapshot lookback, then refresh the dashboard.");
}

// Read both Flux table columns and tag labels used by Grafana's Flux data frames.
const records = new Map();
for (const frame of context.panel.data.series || []) {
  const fields = frame.fields || [];
  const value = fields.find(field => field.name === "_value" || field.name === "chip_snapshot_str" || field.name === "Value");
  const time = fields.find(field => field.type === "time" || field.name === "_time" || field.name === "Time");
  const entity = fields.find(field => field.name === "entity_id");
  if (!value || !time) continue;
  for (let index = 0; index < (value.values?.length || 0); index++) {
    const id = entity ? at(entity.values, index) : value.labels?.entity_id;
    const stampValue = at(time.values, index);
    const stamp = typeof stampValue === "number" ? stampValue : Date.parse(stampValue);
    if (typeof id !== "string" || !id || !Number.isFinite(stamp) || stamp > target || stamp < target - lookback) continue;
    if (!records.has(id) || records.get(id).stamp < stamp) records.set(id, { stamp, raw: at(value.values, index) });
  }
}
let selected;
try {
  const parsed = JSON.parse(variable("boards:json"));
  selected = (Array.isArray(parsed) ? parsed : [parsed]).filter(id => typeof id === "string" && id && !id.startsWith("$"));
} catch { selected = []; }
if (!selected.length) selected = [...records.keys()].sort();
selected = [...new Set(selected)];
if (!selected.length) return message("No archived board snapshots found.\nCheck Bucket, board selection and the chip_snapshot_str export.\nMove the time picker's To endpoint to a time after collection started.");
if (selected.length > 3) return message("Select up to three board-map series for this M60VK2A dashboard.\nBoard slots alone do not identify a miner.");

function readBoard(id) {
  const record = records.get(id);
  if (!record) return { id, status: "No snapshot within the selected lookback", chips: new Map() };
  try {
    if (typeof record.raw !== "string" || record.raw.length > 1048576) throw new Error();
    const payload = JSON.parse(record.raw);
    if (payload.schema_version !== 1 || !Number.isInteger(payload.slot) || payload.slot < 0 || payload.slot > 31 ||
        !Array.isArray(payload.chips) || !payload.chips.length || payload.chips.length > 172) throw new Error();
    const measured = typeof payload.updated_at === "string" ? Date.parse(payload.updated_at) : NaN;
    if (!Number.isFinite(measured) || measured > target || measured < target - lookback) {
      return { id, status: "Snapshot measurement time is invalid or outside the selected lookback", chips: new Map() };
    }
    const chips = new Map();
    for (const chip of payload.chips) {
      if (!chip || typeof chip.id !== "string" || !/^C(?:0|[1-9]\d*)$/.test(chip.id) ||
          Number(chip.id.slice(1)) > 171 || chips.has(chip.id)) throw new Error();
      chips.set(chip.id, chip);
    }
    return { id, slot: payload.slot, measured, chips,
      status: `${utc(measured)} · age ${Math.round((target - measured) / 60000)} min` };
  } catch {
    return { id, status: "Invalid snapshot: expected schema 1 and unique WEB IDs C0–C171", chips: new Map(), invalid: true };
  }
}
const boards = selected.map(readBoard);
function positions() {
  const result = [];
  for (let row = 0; row < 4; row++) {
    for (let column = 0; column < 21; column++) {
      const pcb = 89 + 4 * column + (column % 2 === 0 ? 3 - row : row);
      result.push({ id: `C${pcb - 1}`, label: `U${pcb}`, column, row });
    }
    for (let column = 0; column < 22; column++) {
      const domain = 21 - column;
      const pcb = 1 + 4 * domain + (domain % 2 === 0 ? row : 3 - row);
      result.push({ id: `C${pcb - 1}`, label: `U${pcb}`, column, row: row + 4.5 });
    }
  }
  return result;
}
const geometry = positions();
const observed = boards.flatMap(board => [...board.chips.values()].map(chip => finite(chip[metric]))).filter(value => value !== null);
let min = metric === "temperature" ? 60 : observed.length ? Math.min(...observed) : 0;
let max = metric === "temperature" ? 100 : observed.length ? Math.max(...observed) : 1;
if (min === max) max = min + Math.max(1, Math.abs(min) * 0.05);
const color = value => {
  if (value === null) return missingColor;
  const hue = 210 * (1 - Math.max(0, Math.min(1, (value - min) / (max - min)))) / 60;
  const chroma = 0.6336, offset = 0.1232;
  const secondary = chroma * (1 - Math.abs(hue % 2 - 1));
  const rgb = hue < 1 ? [chroma, secondary, 0] : hue < 2 ? [secondary, chroma, 0]
    : hue < 3 ? [0, chroma, secondary] : [0, secondary, chroma];
  return `#${rgb.map(channel => Math.round((channel + offset) * 255).toString(16).padStart(2, "0")).join("")}`;
};
const foreground = background => {
  const channels = [1, 3, 5].map(start => parseInt(background.slice(start, start + 2), 16) / 255)
    .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722 > 0.179 ? "#000000" : "#ffffff";
};
const number = value => value === null ? "—" : Number.isInteger(value) ? String(value) : value.toFixed(metric === "temperature" ? 1 : 2);
const suffix = metric === "temperature" ? "°" : "";
const textWidth = (text, font) => context.echarts?.format?.getTextRect
  ? context.echarts.format.getTextRect(text, font).width
  : text.length * Number(/\d+/.exec(font)?.[0] || 10) * 0.65;
const grid = [], xAxis = [], yAxis = [], series = [], title = [];
const boardShare = 90 / boards.length;
boards.forEach((board, boardIndex) => {
  const top = 6 + boardIndex * boardShare;
  const cells = geometry.map(position => {
    const chip = board.chips.get(position.id);
    return { ...position, chip, reading: finite(chip?.[metric]),
      value: [position.column, position.row] };
  });
  const values = cells.map(cell => cell.reading).filter(value => value !== null);
  const stats = values.length ? `min ${number(Math.min(...values))} · avg ${number(values.reduce((a, b) => a + b, 0) / values.length)} · max ${number(Math.max(...values))} · ${values.length}/172` : "No readings";
  title.push({ text: board.slot === undefined ? board.id : `Board ${board.slot} · ${board.id}`,
    subtext: `${board.status} · ${stats}`, left: 8, top: `${top - 2}%`,
    textStyle: { color: textColor, fontSize: 11, fontWeight: 600 },
    subtextStyle: { color: mutedColor, fontSize: 10, lineHeight: 12 }, itemGap: 2, padding: 0 });
  grid.push({ left: 8, right: 8, top: `${top + 4.5}%`, height: `${boardShare - 7.5}%`, containLabel: false });
  xAxis.push({ type: "value", min: -0.5, max: 21.5, gridIndex: boardIndex, show: false });
  yAxis.push({ type: "value", min: -0.5, max: 8, inverse: true, gridIndex: boardIndex, show: false });
  series.push({ name: board.id, type: "custom", coordinateSystem: "cartesian2d", xAxisIndex: boardIndex,
    yAxisIndex: boardIndex, animation: false, clip: true, dimensions: ["column", "row"],
    encode: { x: 0, y: 1 }, data: board.invalid ? [] : cells,
    renderItem(params, api) {
      const cell = cells[params.dataIndex];
      const [x, y] = api.coord([cell.column, cell.row]);
      const size = api.size([1, 1]);
      const width = Math.max(1, Math.abs(size[0]) - 2), height = Math.max(1, Math.abs(size[1]) - 2);
      const background = color(cell.reading), cellText = foreground(background);
      const stacked = width >= 36 && height >= 32;
      const font = 16;
      const labelFont = 11;
      const valueText = `${number(cell.reading)}${suffix}`;
      let inlineFont = Math.max(5, Math.min(15, Math.floor(height - 1)));
      let inlineLabelFont = Math.max(5, Math.min(11, inlineFont - 2));
      const combinedWidth = () => textWidth(cell.label, `${inlineLabelFont}px sans-serif`)
        + 6 + textWidth(valueText, `bold ${inlineFont}px sans-serif`);
      while (combinedWidth() > width - 4 && inlineFont > 9) {
        inlineFont--;
        inlineLabelFont = Math.max(5, Math.min(11, inlineFont - 2));
      }
      // A short panel still needs its measurements. Use one line when wide,
      // otherwise prioritize the value; full chip identity remains in the tooltip.
      const combinedFits = combinedWidth() <= width - 4;
      const inlineText = combinedFits ? `{id|${cell.label}}  {reading|${valueText}}` : valueText;
      const textNodes = stacked ? [
        { type: "text", style: { x, y: y - font * 0.5, text: cell.label, fill: cellText,
          font: `${labelFont}px sans-serif`, align: "center", verticalAlign: "middle" } },
        { type: "text", style: { x, y: y + labelFont * 0.5, text: valueText,
          fill: cellText, font: `bold ${font}px sans-serif`, align: "center", verticalAlign: "middle",
          width: Math.max(1, width - 2), overflow: "truncate" } },
      ] : [{ type: "text", style: { x, y, text: inlineText, fill: cellText,
        font: `bold ${inlineFont}px sans-serif`, align: "center", verticalAlign: "middle",
        rich: combinedFits ? {
          id: { fontSize: inlineLabelFont, fontFamily: "sans-serif", fontWeight: "normal", fill: cellText },
          reading: { fontSize: inlineFont, fontFamily: "sans-serif", fontWeight: "bold", fill: cellText },
        } : undefined,
        width: Math.max(1, width - 2), overflow: "truncate" } }];
      return { type: "group", children: [
        { type: "rect", shape: { x: x - width / 2, y: y - height / 2, width, height, r: 2 },
          style: { fill: background, stroke: "#ffffff24", lineWidth: 0.5 } },
        ...textNodes,
      ] };
    },
    tooltip: { formatter(params) {
      const cell = cells[params.dataIndex];
      const lines = [`Board ${board.slot ?? "?"} · assumed PCB ${cell.label} · WEB ${cell.id}`,
        board.id, board.status, `${metrics[metric]}: ${number(cell.reading)}${metric === "temperature" ? " °C" : ""}`];
      if (cell.chip) for (const [key, label] of Object.entries(metrics)) {
        if (key !== metric && Object.hasOwn(cell.chip, key)) lines.push(`${label}: ${number(finite(cell.chip[key]))}`);
      }
      lines.push("PCB correspondence is unverified; raw units and x/pct meanings are unverified.");
      return lines.join("\n");
    } },
  });
});
const legend = [];
for (let index = 0; index < 20; index++) legend.push({ type: "rect", shape: { x: index * 8, y: 0, width: 8, height: 7 }, style: { fill: color(min + (max - min) * index / 19) } });
legend.push({ type: "text", style: { x: -8, y: 3, text: number(min), fill: mutedColor, align: "right", verticalAlign: "middle", font: "10px sans-serif" } },
  { type: "text", style: { x: 168, y: 3, text: `${number(max)} · gray: no reading`, fill: mutedColor, verticalAlign: "middle", font: "10px sans-serif" } });
return { animation: false, backgroundColor: "transparent", grid, xAxis, yAxis, series, title,
  tooltip: { trigger: "item", renderMode: "richText", confine: true },
  graphic: [
    { type: "text", left: 8, top: 0, style: { text: `M60VK2A · ${metrics[metric]} · Unverified WEB Cn → PCB U(n+1) mapping`, fill: mutedColor, font: "10px sans-serif" } },
    { type: "group", left: "center", bottom: 20, children: legend },
    { type: "text", left: 8, bottom: 0, style: { text: `At or before ${utc(target)} · Scale compares readings, not hardware limits.`, fill: mutedColor, font: "10px sans-serif" } },
  ] };
