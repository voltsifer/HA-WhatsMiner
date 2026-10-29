import test from 'node:test';
import assert from 'node:assert/strict';
globalThis.HTMLElement = class {};
globalThis.customElements = { get: () => undefined, define: () => {} };
globalThis.window = {};
const { median, chipColor, finiteTemperature, layoutCells, m60vk2aLayout, boardPlacement } = await import('../custom_components/whatsminer_local/www/ha-whatsminer-heatmap-card.js');
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
  assert.match(result.kind, /Logical grid/);
  assert.equal(result.cells[1].row, 1);
});

test('M60VK2A candidate geometry preserves 172 identities and photographed PCB anchors', () => {
  const rows = m60vk2aLayout();
  assert.equal(rows.length, 9);
  assert.ok(rows.every(row => row.length === 22));
  assert.deepEqual(rows.slice(0, 4).map(row => row.filter(id => id !== null).length), [21, 21, 21, 21]);
  assert.ok(rows[4].every(id => id === null));
  assert.deepEqual(rows.slice(5).map(row => row.filter(id => id !== null).length), [22, 22, 22, 22]);
  const ids = rows.flat().filter(id => id !== null);
  assert.equal(ids.length, 172);
  assert.equal(new Set(ids).size, 172);
  assert.deepEqual(new Set(ids), new Set(Array.from({length: 172}, (_, index) => `C${index}`)));
  // Upper-left PCB labels: U92/U91/U90/U89, then U93/U94/U95/U96.
  assert.deepEqual(rows.slice(0, 4).map(row => row[0]), ['C91', 'C90', 'C89', 'C88']);
  assert.deepEqual(rows.slice(0, 4).map(row => row[1]), ['C92', 'C93', 'C94', 'C95']);
  assert.deepEqual(rows[0].slice(0, 4), ['C91', 'C92', 'C99', 'C100']);
  assert.equal(rows[0][20], 'C171');
  assert.deepEqual(rows.slice(5).map(row => row[21]), ['C0', 'C1', 'C2', 'C3']);
  assert.deepEqual(rows.slice(5).map(row => row[20]), ['C7', 'C6', 'C5', 'C4']);
  assert.deepEqual(rows[7].slice(0, 5), ['C85', 'C82', 'C77', 'C74', 'C69']);
  assert.deepEqual(rows[8].slice(0, 5), ['C84', 'C83', 'C76', 'C75', 'C68']);
});

test('Candidate placement never renumbers WEB readings and retains metrics and missing chips', () => {
  const chips = [{id: 'C171', temperature: 81, errors: 4}, {id: 'C0', temperature: 73, voltage_raw: 275, crc_errors: 0}];
  const before = structuredClone(chips);
  const placement = boardPlacement(chips, {layout: 'm60vk2a', columns: 14}, 0);
  assert.equal(placement.cells.length, 172);
  assert.equal(placement.columns, 22);
  assert.match(placement.kind, /unverified/i);
  const zero = placement.cells.find(chip => chip.id === 'C0');
  assert.equal(zero.row, 5);
  assert.equal(zero.column, 21);
  assert.equal(zero.pcbLabel, 'U1');
  assert.equal(zero.temperature, 73);
  assert.equal(zero.voltage_raw, 275);
  assert.equal(zero.crc_errors, 0);
  const last = placement.cells.find(chip => chip.id === 'C171');
  assert.equal(last.row, 0);
  assert.equal(last.column, 20);
  assert.equal(last.pcbLabel, 'U172');
  assert.equal(last.temperature, 81);
  assert.equal(last.errors, 4);
  assert.equal(placement.cells.find(chip => chip.id === 'C1').temperature, null);
  assert.deepEqual(chips, before);
});

test('Candidate profile rejects incompatible or duplicate identities instead of assigning false positions', () => {
  for (const chips of [
    [{id: 'U1', temperature: 73}],
    [{id: 'C172', temperature: 73}],
    [{id: 'C0', temperature: 73}, {id: 'C0', temperature: 74}],
    Array.from({length: 173}, (_, index) => ({id: `C${index}`, temperature: 73})),
  ]) assert.throws(() => boardPlacement(chips, {layout: 'm60vk2a', columns: 14}, 0));
  const logical = boardPlacement([{id: 'C0', temperature: 73}], {columns: 14}, 0);
  assert.match(logical.kind, /logical/i);
  assert.ok(!Object.hasOwn(logical.cells[0], 'pcbLabel'));
});
