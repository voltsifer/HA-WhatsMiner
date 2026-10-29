import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as echarts from 'echarts';

globalThis.HTMLElement = class {};
globalThis.customElements = {get: () => undefined, define: () => {}};
globalThis.window = {};
const {m60vk2aLayout} = await import('../custom_components/whatsminer_local/www/ha-whatsminer-heatmap-card.js');

const source = readFileSync(new URL('../grafana/heatmap.js', import.meta.url), 'utf8');
const chartFunction = new Function('context', source);
const moment = Date.parse('2026-10-29T12:00:00Z');
const measured = moment - 30 * 60 * 1000;
const entity = slot => `ha_whatsminer_miner_board_${slot}_web_chip_map`;
const chips = () => Array.from({length: 172}, (_, index) => ({
  id: `C${index}`, temperature: 70 + index / 100, voltage_raw: 275, frequency_raw: 480,
  nonce: index * 100, errors: 0, crc_errors: 0, repeat: 0,
  x: 0, x_secondary: 2, pct: 99.3, pct_secondary: 96.6,
}));
function snapshot(slot, overrides = {}) {
  return {schema_version: 1, slot, updated_at: new Date(measured).toISOString(), chips: chips(), ...overrides};
}
function frame(payload, id = entity(payload.slot), stamp = measured + 1000) {
  return {fields: [
    {name: '_time', type: 'time', values: [stamp]},
    {name: '_value', type: 'string', values: [JSON.stringify(payload)]},
    {name: 'entity_id', type: 'string', values: [id]},
  ]};
}
function option(frames, overrides = {}) {
  const variables = {metric: 'temperature', lookback: '2h', __to: String(moment), 'boards:json': '[]', ...overrides};
  return chartFunction({panel: {data: {series: frames}}, grafana: {
    theme: {isDark: true}, replaceVariables: text => variables[text.slice(2, -1)] ?? text,
  }});
}
const allCells = opt => opt.series?.flatMap(series => series.data) ?? [];
const chipCell = (opt, id, board = 0) => opt.series[board].data.find(cell => cell.id === id);

test('Grafana renders 516 cells with ECharts and preserves source IDs and full telemetry', () => {
  const opt = option([0, 1, 2].map(slot => frame(snapshot(slot))));
  assert.equal(opt.series.length, 3);
  assert.equal(allCells(opt).length, 516);
  assert.ok(opt.series.every(series => series.type === 'custom' && series.data.length === 172));
  assert.equal(opt.tooltip.renderMode, 'richText');
  const zero = chipCell(opt, 'C0');
  assert.equal(zero.label, 'U1');
  assert.equal(zero.reading, 70);
  assert.equal(zero.chip.voltage_raw, 275);
  assert.equal(zero.chip.errors, 0);
  const tooltip = opt.series[0].tooltip.formatter({dataIndex: opt.series[0].data.indexOf(zero)});
  for (const text of ['assumed PCB U1', 'WEB C0', 'Voltage (raw): 275', 'Frequency (raw): 480',
    'Errors: 0', 'CRC errors: 0', 'x (second): 2', 'pct (first, %): 99.3']) assert.ok(tooltip.includes(text), text);
  const chart = echarts.init(null, null, {renderer: 'svg', ssr: true, width: 1600, height: 720});
  try {
    chart.setOption(opt);
    const svg = chart.renderToSVGString();
    assert.match(svg, /U172/);
    assert.match(svg, /Unverified/);
    assert.ok(!svg.includes('NaN'));
    assert.equal(chart.getZr().storage.getDisplayList().filter(item => item.style?.text?.endsWith('°')).length, 516);
    // The same option must adapt when Grafana only calls chart.resize().
    const firstRect = chart.getZr().storage.getDisplayList().find(item => item.type === 'rect' && item.shape.height > 8);
    const originalWidth = firstRect.shape.width;
    chart.resize({width: 1000, height: 700});
    chart.renderToSVGString();
    const resizedRect = chart.getZr().storage.getDisplayList().find(item => item.type === 'rect' && item.shape.height > 8);
    assert.ok(resizedRect.shape.width < originalWidth);
    assert.ok(resizedRect.shape.width > 0);
  } finally { chart.dispose(); }
});

test('Grafana keeps all 172 PCB positions and the photographed numbering anchors', () => {
  const opt = option([frame(snapshot(0))]);
  const cells = allCells(opt);
  assert.equal(new Set(cells.map(cell => cell.id)).size, 172);
  assert.equal(new Set(cells.map(cell => cell.label)).size, 172);
  assert.deepEqual([chipCell(opt, 'C91').column, chipCell(opt, 'C91').row], [0, 0]);
  assert.deepEqual([chipCell(opt, 'C88').column, chipCell(opt, 'C88').row], [0, 3]);
  assert.deepEqual([chipCell(opt, 'C171').column, chipCell(opt, 'C171').row], [20, 0]);
  assert.deepEqual([chipCell(opt, 'C0').column, chipCell(opt, 'C0').row], [21, 4.5]);
  assert.deepEqual([chipCell(opt, 'C3').column, chipCell(opt, 'C3').row], [21, 7.5]);
  assert.deepEqual([chipCell(opt, 'C87').column, chipCell(opt, 'C87').row], [0, 4.5]);
  assert.equal(cells.filter(cell => cell.row < 4).length, 84);
  assert.equal(cells.filter(cell => cell.row > 4).length, 88);
  m60vk2aLayout().forEach((row, rowIndex) => row.forEach((id, column) => {
    if (id !== null) {
      const cell = chipCell(opt, id);
      assert.equal(cell.column, column);
      assert.equal(cell.row, rowIndex > 4 ? rowIndex - 0.5 : rowIndex);
    }
  }));
});

test('Missing and invalid metrics remain missing, while zero values and other metrics survive', () => {
  const opt = option([frame(snapshot(0, {chips: [
    {id: 'C0', temperature: null, errors: 0, voltage_raw: 275},
    {id: 'C1', temperature: 0, errors: 0},
    {id: 'C2', temperature: true}, {id: 'C3', temperature: '73'},
  ]}))]);
  assert.equal(allCells(opt).length, 172);
  assert.equal(chipCell(opt, 'C0').reading, null);
  assert.equal(chipCell(opt, 'C1').reading, 0);
  assert.equal(chipCell(opt, 'C2').reading, null);
  assert.equal(chipCell(opt, 'C3').reading, null);
  assert.equal(chipCell(opt, 'C171').reading, null);
  assert.equal(chipCell(opt, 'C171').chip, undefined);
  const errors = option([frame(snapshot(0, {chips: [{id: 'C0', temperature: null, errors: 0}]}))], {metric: 'errors'});
  assert.equal(chipCell(errors, 'C0').reading, 0);
  const chart = echarts.init(null, null, {renderer: 'svg', ssr: true, width: 1400, height: 700});
  try {
    chart.setOption(opt);
    const svg = chart.renderToSVGString();
    assert.match(svg, /#596474/);
    assert.match(svg, /0°/);
  } finally { chart.dispose(); }
});

test('Historical maps never display future, stale or malformed snapshot readings', () => {
  for (const payload of [
    snapshot(0, {updated_at: new Date(moment + 1000).toISOString()}),
    snapshot(0, {updated_at: new Date(moment - 3 * 3600000).toISOString()}),
    snapshot(0, {updated_at: 'not-a-date'}),
    snapshot(0, {schema_version: 2}),
  ]) {
    const opt = option([frame(payload)], {'boards:json': JSON.stringify([entity(0)])});
    assert.ok(allCells(opt).every(cell => cell.reading === null));
    assert.match(opt.title[0].subtext, /invalid|outside/i);
  }
  for (const stamp of [moment + 1000, moment - 3 * 3600000]) {
    const opt = option([frame(snapshot(0), entity(0), stamp)], {'boards:json': JSON.stringify([entity(0)])});
    assert.equal(allCells(opt).length, 172);
    assert.ok(allCells(opt).every(cell => cell.reading === null));
    assert.match(opt.title[0].subtext, /No snapshot/);
  }
});

test('Multiple frames choose the newest archived record and respect explicit board scope', () => {
  const old = snapshot(0, {chips: [{id: 'C0', temperature: 71}]});
  const recent = snapshot(0, {chips: [{id: 'C0', temperature: 79}]});
  const opt = option([frame(recent, entity(0), measured + 2000), frame(snapshot(1)), frame(old)],
    {'boards:json': JSON.stringify([entity(0)])});
  assert.equal(opt.series.length, 1);
  assert.equal(opt.series[0].name, entity(0));
  assert.equal(chipCell(opt, 'C0').reading, 79);
  const corrupt = frame(snapshot(0), entity(0), measured + 3000);
  corrupt.fields[1].values[0] = '{invalid JSON';
  const closed = option([frame(old), corrupt], {'boards:json': JSON.stringify([entity(0)])});
  assert.equal(allCells(closed).length, 0);
  assert.match(closed.title[0].subtext, /Invalid snapshot/);
});

test('Incompatible chip identities are rejected rather than assigned false physical positions', () => {
  for (const invalid of [
    [{id: 'C0', temperature: 73}, {id: 'C0', temperature: 74}],
    [{id: 'C172', temperature: 73}], [{id: 'U1', temperature: 73}],
    [{id: 'C01', temperature: 73}],
    Array.from({length: 173}, (_, index) => ({id: `C${index}`, temperature: 73})),
  ]) {
    const opt = option([frame(snapshot(0, {chips: invalid}))]);
    assert.equal(allCells(opt).length, 0);
    assert.match(opt.title[0].subtext, /Invalid snapshot/);
  }
});

test('Grafana Flux labels and vector values work without exposing HTML tooltips', () => {
  const malicious = 'board_<img src=x onerror=alert(1)>';
  const f = frame(snapshot(0), malicious);
  f.fields.pop();
  f.fields[1].labels = {entity_id: malicious};
  for (const field of f.fields) {
    const array = field.values;
    field.values = {length: array.length, get: index => array[index]};
  }
  const opt = option([f]);
  assert.equal(opt.series.length, 1);
  assert.equal(opt.tooltip.renderMode, 'richText');
  assert.equal(allCells(opt).length, 172);
  assert.equal(opt.series[0].name, malicious);
  const content = opt.series[0].tooltip.formatter({dataIndex: 0});
  assert.ok(content.includes(malicious));
  const chart = echarts.init(null, null, {renderer: 'svg', ssr: true, width: 1000, height: 700});
  try {
    chart.setOption(opt);
    const svg = chart.renderToSVGString();
    assert.ok(!svg.includes('<img'));
    assert.ok(svg.includes('&lt;img'));
  } finally { chart.dispose(); }
});

test('Importable dashboard embeds its readable sources and bounds historical Flux work', () => {
  const dashboard = JSON.parse(readFileSync(new URL('../grafana/whatsminer-m60vk2a.json', import.meta.url)));
  const flux = readFileSync(new URL('../grafana/snapshot.flux', import.meta.url), 'utf8');
  const panel = dashboard.panels.find(panel => panel.type === 'volkovlabs-echarts-panel');
  assert.equal(panel.options.getOption, source);
  assert.equal(panel.options.editorMode, 'code');
  assert.equal(panel.options.map, 'none');
  assert.equal(panel.targets[0].query, flux);
  assert.match(flux, /range\(start: snapshotStart, stop: v\.timeRangeStop\)/);
  assert.match(flux, /v\.timeRangeStop.*\$\{lookback\}/);
  assert.match(flux, /r\._field == "chip_snapshot_str"/);
  assert.match(flux, /group\(columns: \["entity_id"\]\)/);
  assert.match(flux, /last\(\)/);
  assert.doesNotMatch(flux, /aggregateWindow|mean\(/);
  assert.ok(!JSON.stringify(dashboard).includes('Authorization'));
  assert.ok(!/https?:\/\/.*\.(?:js|json)/.test(source));
});
