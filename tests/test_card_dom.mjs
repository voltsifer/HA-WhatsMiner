import test from 'node:test';
import assert from 'node:assert/strict';
import { Window } from 'happy-dom';

const win = new Window({ url: 'http://localhost/' });
for (const name of ['HTMLElement', 'document', 'customElements']) globalThis[name] = win[name];
globalThis.window = win;
await import('../custom_components/whatsminer_local/www/ha-whatsminer-heatmap-card.js');

const id = 'sensor.slot_0_chips';
function makeCard(chips, config = {}) {
  const card = document.createElement('ha-whatsminer-heatmap-card');
  document.body.append(card);
  card.setConfig({ entity: id, ...config });
  card.hass = { states: { [id]: { state: '95', attributes: { slot: 0, chips } } } };
  return card;
}

test('Card renders, selects a chip and switches the comparison mode', () => {
  const card = makeCard([{ id: 'U1', temperature: 92 }, { id: 'U2', temperature: 96 }]);
  const root = card.shadowRoot;
  assert.equal(root.querySelectorAll('.chip').length, 2);
  root.querySelector('.chip').click();
  assert.match(root.querySelector('.details').textContent, /U1.*92.0/);
  root.querySelectorAll('.mode')[1].click();
  assert.equal(root.querySelector('.mode.active').textContent, 'Δ from median');
});

test('A board with 172 chips renders every chip without truncation', () => {
  const card = makeCard(Array.from({length: 172}, (_, index) => ({id: `U${index + 1}`, temperature: 90 + index / 100})), {columns: 14});
  assert.equal(card.shadowRoot.querySelectorAll('.chip').length, 172);
  assert.equal(card.shadowRoot.querySelectorAll('.chipid')[171].textContent, 'U172');
  card.shadowRoot.querySelectorAll('.chip')[171].click();
  assert.match(card.shadowRoot.querySelector('.details').textContent, /U172/);
});

test('Lost readings are not kept on the map', () => {
  const card = makeCard([{ id: 'U1', temperature: 92 }]);
  card.hass = { states: { [id]: { state: 'unavailable', attributes: { chips: [{ id: 'U1', temperature: 92 }] } } } };
  assert.equal(card.shadowRoot.querySelectorAll('.chip').length, 0);
  assert.match(card.shadowRoot.textContent, /no fresh chip data/);
});

test('Selected chip exposes all available telemetry with zero and missing values', () => {
  const card = makeCard([{ id: 'C0', temperature: 73, frequency_raw: 480, voltage_raw: 275,
    nonce: 1234, errors: 3, crc_errors: 0, x: 0, x_secondary: 2, repeat: null,
    pct: 99.3, pct_secondary: 96.6, password: 'never-display-this' }]);
  const cell = card.shadowRoot.querySelector('.chip');
  cell.click();
  const text = card.shadowRoot.querySelector('.details').textContent;
  for (const expected of ['Frequency (raw): 480', 'Voltage (raw): 275', 'Nonce: 1234',
    'Errors: 3', 'CRC errors: 0', 'x (first): 0', 'x (second): 2', 'Repeat: —',
    'pct (first, %): 99.3', 'pct (second, %): 96.6']) assert.ok(text.includes(expected), expected);
  assert.ok(!text.includes('never-display-this'));
  assert.match(card.shadowRoot.textContent, /units\/scales are unverified/);
});

test('Other telemetry remains selectable when every temperature is missing', () => {
  const card = makeCard([]);
  card.hass = { states: { [id]: { state: 'unknown', attributes: { slot: 0,
    chips: [{ id: 'C0', temperature: null, voltage_raw: 275, errors: 0 }] } } } };
  const cell = card.shadowRoot.querySelector('.chip');
  assert.ok(cell);
  cell.click();
  assert.match(card.shadowRoot.querySelector('.details').textContent, /Voltage \(raw\): 275.*Errors: 0/);
});

test('Chip labels and titles cannot inject HTML', () => {
  const card = makeCard([{ id: '<img src=x onerror=alert(1)>', temperature: 92 }], { title: '<script>bad()</script>' });
  assert.equal(card.shadowRoot.querySelectorAll('img,script').length, 0);
  assert.match(card.shadowRoot.querySelector('.chipid').textContent, /<img/);
});

test('Explicit missing positions remain visible and unmatched chips are labelled', () => {
  const card = makeCard([{ id: 'U2', temperature: 92 }, { id: 'U3', temperature: null }], {
    layouts: { '0': [['U1', 'U2']] },
  });
  assert.equal(card.shadowRoot.querySelectorAll('.chip').length, 3);
  assert.equal(card.shadowRoot.querySelectorAll('.missing').length, 2);
  assert.match(card.shadowRoot.textContent, /outside the specified layout/);
});
