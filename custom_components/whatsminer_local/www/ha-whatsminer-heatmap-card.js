/* HA-WhatsMiner 0.5.4 — dependency-free Lovelace card. MIT. */
export function finiteTemperature(value) {
  if (value === null || value === undefined || typeof value === "boolean" || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

const chipDetailFields = [
  ["frequency_raw", "Frequency (raw)"], ["voltage_raw", "Voltage (raw)"],
  ["nonce", "Nonce"], ["errors", "Errors"], ["crc_errors", "CRC errors"],
  ["x", "x (first)"], ["x_secondary", "x (second)"], ["repeat", "Repeat"],
  ["pct", "pct (first, %)"], ["pct_secondary", "pct (second, %)"],
];

export function chipDetails(chip) {
  return chipDetailFields.filter(([key]) => Object.hasOwn(chip, key)).map(([key, label]) => {
    const value = finiteTemperature(chip[key]);
    return `${label}: ${value === null ? "—" : value}`;
  }).join(" · ");
}

export function median(values) {
  const sorted = values.filter(Number.isFinite).slice().sort((a, b) => a - b);
  if (!sorted.length) return null;
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export function chipColor(temperature, min, max, mode = "absolute", reference = 0, spread = 15) {
  if (temperature === null) return "#596474";
  if (mode === "delta") {
    const delta = Math.max(-1, Math.min(1, (temperature - reference) / spread));
    return delta >= 0 ? `hsl(${150 * (1 - delta)} 68% 42%)` : `hsl(${150 - delta * 65} 65% 44%)`;
  }
  const ratio = Math.max(0, Math.min(1, (temperature - min) / (max - min)));
  return `hsl(${210 * (1 - ratio)} 72% 44%)`;
}

export function layoutCells(chips, explicitLayout, columns) {
  const byId = new Map(chips.map(chip => [String(chip.id), chip]));
  if (explicitLayout) {
    const used = new Set();
    const cells = [];
    explicitLayout.forEach((row, r) => row.forEach((id, c) => {
      if (id === null || id === "") return;
      id = String(id);
      if (used.has(id)) throw new Error(`Chip ${id} appears more than once in the layout`);
      used.add(id);
      cells.push({ ...(byId.get(id) || { id, temperature: null }), row: r, column: c });
    }));
    const remaining = chips.filter(chip => !used.has(String(chip.id)));
    return { cells, remaining, kind: "User-defined layout", columns: Math.max(1, ...explicitLayout.map(row => row.length)) };
  }
  if (chips.length && chips.every(chip => Number.isInteger(chip.row) && Number.isInteger(chip.column))) {
    return { cells: chips, remaining: [], kind: "Web coordinates · verify against the board layout", columns: Math.max(...chips.map(chip => chip.column)) + 1 };
  }
  return { cells: chips.map((chip, index) => ({ ...chip, row: Math.floor(index / columns), column: index % columns })),
    remaining: [], kind: "Logical grid · physical layout not specified", columns };
}

export function m60vk2aLayout() {
  // Reconstructed from PCB U labels in supplied photos, not from another project's code.
  // WEB Cn -> PCB U(n+1), far endpoints and horizontal block alignment are unverified.
  const upper = Array.from({ length: 4 }, (_, row) => [
    ...Array.from({ length: 21 }, (_, column) => {
      const pcb = 89 + 4 * column + (column % 2 === 0 ? 3 - row : row);
      return `C${pcb - 1}`;
    }), null,
  ]);
  const lower = Array.from({ length: 4 }, (_, row) =>
    Array.from({ length: 22 }, (_, column) => {
      const domain = 21 - column;
      const pcb = 1 + 4 * domain + (domain % 2 === 0 ? row : 3 - row);
      return `C${pcb - 1}`;
    }));
  return [...upper, Array(22).fill(null), ...lower];
}

const m60vk2aRows = m60vk2aLayout();
const m60vk2aIds = new Set(m60vk2aRows.flat().filter(id => id !== null));

export function boardPlacement(chips, config, slot) {
  if (config.layout !== "m60vk2a") return layoutCells(chips, config.layouts?.[String(slot)], config.columns);
  const ids = chips.map(chip => String(chip.id));
  if (chips.length > 172 || new Set(ids).size !== ids.length || ids.some(id => !m60vk2aIds.has(id))) {
    throw new Error("M60VK2A requires WEB chip IDs C0 through C171. Check the board and selected layout profile.");
  }
  const placement = layoutCells(chips, m60vk2aRows, 22);
  return { ...placement,
    cells: placement.cells.map(chip => ({ ...chip, pcbLabel: `U${Number(chip.id.slice(1)) + 1}` })),
    kind: "M60VK2A · reconstructed layout · unverified mapping",
    profile: "m60vk2a", spacerRows: [4],
    warning: "Unverified mapping: C0 → U1, C1 → U2, through C171 → U172. Some PCB positions are inferred from the photographed numbering pattern.",
  };
}

const css = `
:host{display:block}*{box-sizing:border-box}ha-card{display:block;padding:20px;color:var(--primary-text-color,#e9eff7);background:var(--ha-card-background,var(--card-background-color,#151e2b));border-radius:var(--ha-card-border-radius,16px);border:1px solid var(--divider-color,#344154);font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif)}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.title{font-size:20px;font-weight:650}.subtitle{font-size:12px;color:var(--secondary-text-color,#a5b4c8);margin-top:6px}.modes{display:flex;gap:5px}.mode{border:1px solid var(--divider-color,#40516a);border-radius:8px;padding:7px 10px;background:transparent;color:inherit;cursor:pointer;font-size:12px}.mode.active{background:#246475;color:white;border-color:#51c6c9}.board{margin-top:22px}.boardhead{display:flex;justify-content:space-between;gap:10px;align-items:baseline;flex-wrap:wrap}.boardname{font-weight:650}.stats{font-size:12px;color:var(--secondary-text-color,#a5b4c8)}.placement{font-size:11px;margin:7px 0 10px;color:var(--secondary-text-color,#a5b4c8)}.scroll{overflow-x:auto;padding-bottom:5px}.grid{display:grid;gap:5px;min-width:min-content}.chip{border:1px solid #ffffff24;color:#fff;text-shadow:0 1px 2px #0008;min-width:46px;min-height:51px;border-radius:7px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:3px;font:inherit;cursor:pointer;padding:6px 3px}.chip:hover,.chip:focus-visible{outline:2px solid var(--primary-text-color,#fff);outline-offset:1px}.chipid{font-size:10px;opacity:.88}.temp{font-size:12px;font-weight:700}.missing{background:repeating-linear-gradient(45deg,#536071,#536071 4px,#424e60 4px,#424e60 8px)!important}.legend{display:flex;align-items:center;gap:9px;font-size:11px;color:var(--secondary-text-color,#a5b4c8);margin-top:20px;flex-wrap:wrap}.bar{width:140px;height:7px;border-radius:5px;background:linear-gradient(90deg,hsl(210 72% 44%),hsl(150 72% 44%),hsl(70 72% 44%),hsl(0 72% 44%))}.bar.delta{background:linear-gradient(90deg,hsl(215 65% 44%),hsl(150 68% 42%),hsl(0 68% 42%))}.message{padding:16px 0;color:var(--secondary-text-color,#a5b4c8)}.details{padding:10px;margin-top:12px;border-radius:8px;background:#8097b018;font-size:13px;min-height:36px}.note{margin-top:9px;color:var(--secondary-text-color,#a5b4c8);font-size:11px;line-height:1.5}.demo{padding:7px 10px;background:#8b5c15;color:white;border-radius:7px;font-size:11px;margin-bottom:14px}
`;

const compactCss = `
:host{min-width:0}ha-card{min-width:0;--chip-height:51px;--board-gap:24px}.boards{min-width:0}.board{min-width:0}.physical{min-width:0;max-width:100%}.physical .grid{min-width:0}.physical .chip{min-width:0;min-height:0;height:var(--chip-height);overflow:hidden;padding:0;gap:0}.physical .chipid,.physical .temp{white-space:nowrap}.mapping-warning{font-size:11px;color:var(--secondary-text-color,#a5b4c8);margin-top:8px}.disclosure{margin-top:8px;font-size:11px;color:var(--secondary-text-color,#a5b4c8)}.disclosure summary{cursor:pointer}.disclosure .note{margin-top:5px}.compact{padding:10px;line-height:1.2;--chip-height:clamp(24px,calc((100dvh - 440px) / var(--heatmap-total-rows,24)),32px);--board-gap:8px}.compact header{gap:6px}.compact .title{font-size:16px}.compact .subtitle{display:none}.compact .mode{padding:5px 8px;font-size:11px}.compact .boards{display:grid;gap:8px;margin-top:8px}.compact .board{margin-top:0}.compact .boardhead{line-height:14px;flex-wrap:nowrap;align-items:center;gap:8px;margin-bottom:4px;min-width:0}.compact .boardname{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}.compact .stats{font-size:11px;white-space:nowrap;flex-shrink:0}.compact .board>.placement{display:none}.compact .grid{gap:2px}.compact .chipid{font-size:9px;line-height:10px}.compact .temp{font-size:11px;line-height:12px}.compact .scroll{padding-bottom:0}.compact .updated{font-size:10px;margin-top:2px;line-height:12px}.compact .mapping-warning{margin-top:5px;line-height:14px}.compact .legend{margin-top:7px;gap:6px;line-height:14px}.compact .details{font-size:11px;padding:4px 6px;min-height:22px;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.compact .disclosure{margin-top:5px}.compact .disclosure summary{line-height:16px}
@media(max-width:700px){.compact .boardhead{flex-wrap:wrap;gap:2px}.compact .boardname{flex-basis:100%}.compact .title{font-size:14px}.compact .physical .chipid{font-size:8px}.compact .physical .temp{font-size:9px}}
`;

export class HAWhatsminerHeatmapCard extends HTMLElement {
  constructor() { super(); this.attachShadow({ mode: "open" }); this._mode = "absolute"; }
  static getStubConfig() {
    return { auto_discover: true, columns: 14, min_temperature: 60, max_temperature: 100 };
  }
  setConfig(config) {
    if (config.layout !== undefined && config.layout !== "m60vk2a") throw new Error("Unknown layout profile. Use m60vk2a, or omit layout for automatic placement.");
    if (config.layout && config.layouts) throw new Error("Use either layout or layouts, not both.");
    const compact = config.compact === undefined ? config.layout === "m60vk2a" : config.compact;
    if (typeof compact !== "boolean") throw new Error("compact must be true or false");
    const entities = config.entities || (config.entity ? [config.entity] : []);
    const autoDiscover = config.auto_discover ?? (!config.entities && !config.entity);
    if (typeof autoDiscover !== "boolean") throw new Error("auto_discover must be true or false");
    if (!Array.isArray(entities) || (!autoDiscover && !entities.length) || entities.some(id => typeof id !== "string" || !id.startsWith("sensor."))) throw new Error("Specify web chip map sensors or use auto_discover: true without entity/entities");
    if (autoDiscover && entities.length) throw new Error("Remove entity/entities when using auto_discover: true");
    const min = config.min_temperature ?? 70, max = config.max_temperature ?? 110;
    if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) throw new Error("Check the color scale limits");
    const columns = config.columns ?? (config.layout === "m60vk2a" ? 22 : 10);
    if (!Number.isInteger(columns) || columns < 1 || columns > 128) throw new Error("columns must be between 1 and 128");
    if (config.layouts) {
      if (typeof config.layouts !== "object" || Array.isArray(config.layouts)) throw new Error("layouts must be an object indexed by slot number");
      for (const rows of Object.values(config.layouts)) {
        if (!Array.isArray(rows) || !rows.length || rows.length > 128 || rows.some(row => !Array.isArray(row) || row.length > 128)) throw new Error("Invalid board layout");
        layoutCells([], rows, columns);
      }
    }
    this._config = { ...config, compact, entities, auto_discover: autoDiscover, min_temperature: min, max_temperature: max, columns };
    this._discovered = new Set();
    this._previous = undefined;
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
    const next = this._entityIds().map(id => [id, hass.states[id]]);
    if (this._previous && next.length === this._previous.length && next.every(([id, state], i) => id === this._previous[i][0] && state === this._previous[i][1])) return;
    this._previous = next;
    this._render();
  }
  _entityIds() {
    if (!this._config || !this._hass) return [];
    if (!this._config.auto_discover) return this._config.entities;
    for (const [id, state] of Object.entries(this._hass.states)) {
      const attrs = state.attributes;
      if (id.startsWith("sensor.") && attrs?.source === "web" && Number.isInteger(attrs.slot) && Array.isArray(attrs.chips)) this._discovered.add(id);
    }
    // Keep known unavailable sources visible; removed/renamed entities are forgotten.
    for (const id of this._discovered) if (!this._hass.states[id]) this._discovered.delete(id);
    return [...this._discovered].sort((a, b) => a.localeCompare(b));
  }
  getCardSize() { return 5; }
  getGridOptions() { return { columns: "full", rows: "auto", min_columns: 6 }; }
  _node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = String(text);
    return el;
  }
  _render() {
    if (!this._config || !this._hass) return;
    const cfg = this._config;
    const root = this.shadowRoot;
    root.replaceChildren();
    const style = this._node("style"); style.textContent = css + compactCss; root.append(style);
    const card = this._node("ha-card", cfg.compact ? "compact" : ""); root.append(card);
    if (cfg.demo) card.append(this._node("div", "demo", "DEMO · synthetic data, no miner connection"));
    const header = this._node("header");
    const heading = this._node("div"); heading.append(this._node("div", "title", cfg.title || "HA-WhatsMiner · chip heatmap"));
    heading.append(this._node("div", "subtitle", "Individual chip temperatures · °C")); header.append(heading);
    const modes = this._node("div", "modes");
    for (const [value, label] of [["absolute", "Temperature"], ["delta", "Δ from median"]]) {
      const button = this._node("button", `mode ${this._mode === value ? "active" : ""}`, label);
      button.type = "button"; button.setAttribute("aria-pressed", String(this._mode === value));
      button.onclick = () => { this._mode = value; this._render(); };
      modes.append(button);
    }
    header.append(modes); card.append(header);
    const details = this._node("div", "details", "Select a chip to view its temperature, median deviation and available telemetry.");
    const entities = this._entityIds();
    card.style.setProperty("--heatmap-total-rows", String(Math.max(8, entities.length * 8)));
    if (cfg.layout === "m60vk2a") card.append(this._node("div", "mapping-warning", "M60VK2A · Unverified mapping: WEB Cn → PCB U(n+1). U labels and some positions are assumed."));
    const boards = this._node("div", "boards"); card.append(boards);
    let hasRawTelemetry = false;
    if (!entities.length) card.append(this._node("div", "message", "No web chip maps found. Enable web chip data in HA-WhatsMiner and check that Board N web chip map sensors are enabled and available."));
    for (const id of entities) {
      const state = this._hass.states[id];
      const board = this._node("section", "board"); boards.append(board);
      if (!state) {
        board.append(this._node("div", "message", `${id}: entity does not exist. Replace example entity IDs with actual Board N web chip map sensors, or remove entity/entities and use auto_discover: true.`)); continue;
      }
      if (state.state === "unavailable" || !Array.isArray(state.attributes.chips) || !state.attributes.chips.length) {
        board.append(this._node("div", "message", `${id}: no fresh chip data`)); continue;
      }
      const chips = state.attributes.chips.map(chip => ({ ...chip, id: String(chip.id), temperature: finiteTemperature(chip.temperature) }));
      const values = chips.map(chip => chip.temperature).filter(value => value !== null);
      const reference = median(values);
      const slot = state.attributes.slot;
      const boardHead = this._node("div", "boardhead");
      const boardName = this._node("div", "boardname", cfg.auto_discover && state.attributes.friendly_name ? state.attributes.friendly_name : `Board · Slot ${slot ?? "?"}`);
      boardName.title = boardName.textContent;
      boardHead.append(boardName);
      boardHead.append(this._node("div", "stats", values.length ? `min ${Math.min(...values).toFixed(1)}° · avg ${(values.reduce((a, b) => a + b, 0) / values.length).toFixed(1)}° · max ${Math.max(...values).toFixed(1)}° · ${values.length}/${chips.length}` : "No readings"));
      board.append(boardHead);
      hasRawTelemetry ||= chips.some(chip => Object.hasOwn(chip, "voltage_raw") || Object.hasOwn(chip, "frequency_raw"));
      let placement;
      try { placement = boardPlacement(chips, cfg, slot); }
      catch (error) { board.append(this._node("div", "message", error.message)); continue; }
      board.append(this._node("div", "placement", placement.kind));
      const grid = this._grid(placement.cells, placement.columns, reference, slot, details, placement.spacerRows);
      board.append(grid);
      if (placement.remaining.length) {
        board.append(this._node("div", "placement", "Chips outside the specified layout — check their placement"));
        const extra = placement.remaining.map((chip, index) => ({ ...chip, row: Math.floor(index / cfg.columns), column: index % cfg.columns }));
        board.append(this._grid(extra, cfg.columns, reference, slot, details));
      }
      if (state.attributes.updated_at) {
        const date = new Date(state.attributes.updated_at);
        if (!Number.isNaN(date.valueOf())) board.append(this._node("div", "note updated", `Chip data: ${date.toLocaleString("en-GB")}`));
      }
    }
    const legend = this._node("div", "legend");
    const left = this._mode === "absolute" ? `${cfg.min_temperature}°C` : "−15°C";
    const right = this._mode === "absolute" ? `${cfg.max_temperature}°C` : "+15°C";
    legend.append(this._node("span", "", left), this._node("div", `bar ${this._mode === "delta" ? "delta" : ""}`), this._node("span", "", right), this._node("span", "", "▨ No reading"));
    card.append(legend, details);
    const disclosure = this._node("details", "disclosure");
    disclosure.append(this._node("summary", "", "Layout and telemetry notes"));
    if (cfg.layout === "m60vk2a") {
      disclosure.append(this._node("div", "note", "Unverified mapping: C0 → U1, C1 → U2, through C171 → U172. Some PCB positions are inferred from the photographed numbering pattern."));
      disclosure.append(this._node("div", "note", "Power terminals: left · Signal connector: right · Block alignment and spacing are schematic. Select a U label to see its original WEB chip ID."));
    }
    if (hasRawTelemetry) disclosure.append(this._node("div", "note", "Voltage and frequency retain raw firmware values; their units/scales are unverified. Counters are snapshots; pct/x meanings are firmware-specific."));
    disclosure.append(this._node("div", "note", "The color scale compares readings; it is not a temperature limit. Check the placement label before interpreting neighboring cells as physical neighbors."));
    card.append(disclosure);
  }
  _grid(cells, columns, reference, slot, details, spacerRows = []) {
    const physical = this._config.layout === "m60vk2a";
    const scroll = this._node("div", physical ? "scroll physical" : "scroll"), grid = this._node("div", "grid");
    grid.style.gridTemplateColumns = `repeat(${columns}, minmax(${physical ? "0" : "46px"}, 1fr))`;
    if (spacerRows.length) {
      const rows = Math.max(...cells.map(chip => chip.row)) + 1;
      grid.style.gridTemplateRows = Array.from({ length: rows }, (_, row) =>
        spacerRows.includes(row) ? "var(--board-gap)" : "var(--chip-height)").join(" ");
    }
    scroll.append(grid);
    for (const chip of cells) {
      const value = finiteTemperature(chip.temperature);
      const tempText = value === null ? "—" : `${value.toFixed(1)}°`;
      const cell = this._node("button", `chip ${value === null ? "missing" : ""}`);
      cell.type = "button";
      cell.style.gridRow = String(chip.row + 1); cell.style.gridColumn = String(chip.column + 1);
      cell.style.background = chipColor(value, this._config.min_temperature, this._config.max_temperature, this._mode, reference);
      cell.append(this._node("span", "chipid", chip.pcbLabel || chip.id), this._node("span", "temp", tempText));
      const delta = value === null || reference === null ? "—" : `${value - reference >= 0 ? "+" : ""}${(value - reference).toFixed(1)}°C`;
      const telemetry = chipDetails(chip);
      cell.title = `Slot ${slot} · ${chip.id}${chip.pcbLabel ? ` · assumed PCB ${chip.pcbLabel}` : ""} · ${tempText} · Δ ${delta}${telemetry ? ` · ${telemetry}` : ""}`;
      cell.setAttribute("aria-label", cell.title);
      cell.onclick = () => { details.textContent = cell.title; details.title = cell.title; };
      grid.append(cell);
    }
    return scroll;
  }
}
if (!customElements.get("ha-whatsminer-heatmap-card")) customElements.define("ha-whatsminer-heatmap-card", HAWhatsminerHeatmapCard);
window.customCards = window.customCards || [];
if (!window.customCards.some(card => card.type === "ha-whatsminer-heatmap-card")) window.customCards.push({ type: "ha-whatsminer-heatmap-card", name: "HA-WhatsMiner HeatMap", description: "Individual chip temperatures from the web interface" });
