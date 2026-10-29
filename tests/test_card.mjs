import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => undefined, define: () => {} };
globalThis.window = {};
const { median, chipColor, finiteTemperature, layoutCells } = await import('../custom_components/whatsminer_local/www/ha-whatsminer-heatmap-card.js');
test('Missing readings are never represented as zero degrees', () => {
  for (const value of [null, undefined, true, '', NaN, Infinity, 'bad']) assert.equal(finiteTemperature(value), null);
  assert.equal(finiteTemperature(0), 0);
  assert.equal(finiteTemperature('92.3'), 92.3);
});
test('Median and fixed color scale', () => {
  assert.equal(median([100, 80, 90, 95]), 92.5);
  assert.equal(median([]), null);
  assert.equal(chipColor(null, 70, 110), '#596474');
  assert.notEqual(chipColor(70, 70, 110), chipColor(110, 70, 110));
});
test('Explicit mapping preserves missing and unmapped chips', () => {
  const chips = [{id:'U2', temperature:91}, {id:'U7', temperature:98}];
  const mapped = layoutCells(chips, [['U1', 'U2']], 8);
  assert.equal(mapped.cells[0].temperature, null);
  assert.equal(mapped.cells[1].temperature, 91);
  assert.equal(mapped.remaining[0].id, 'U7');
  assert.throws(() => layoutCells(chips, [['U1', 'U1']], 8));
});
test('Unconfirmed geometry is labelled as a logical grid', () => {
  const result = layoutCells([{id:'U8',temperature:95}, {id:'U1',temperature:90}], null, 1);
  assert.match(result.kind, /Условная сетка/);
  assert.equal(result.cells[1].row, 1);
});
