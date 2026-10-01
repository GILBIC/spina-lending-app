import assert from 'node:assert/strict';
import test from 'node:test';
import { bindNavigation, navigationMarkup } from '../assets/ui.js';

function node(attributes = {}) {
  const listeners = new Map();
  return {
    attributes, hidden: false, focused: false,
    classList: { toggle() {} },
    getAttribute: (key) => attributes[key] ?? null,
    setAttribute: (key, value) => { attributes[key] = String(value); },
    removeAttribute: (key) => { delete attributes[key]; },
    addEventListener: (name, handler) => listeners.set(name, handler),
    focus() { this.focused = true; },
    scrollIntoView() {},
    click(target) { listeners.get('click')?.({ target: { closest: () => target }, preventDefault() {} }); },
  };
}

function workspace() {
  const today = node({ id: 'today', 'data-workspace-section': '' });
  const records = node({ id: 'records', 'data-workspace-section': '' });
  records.draft = 'Unsaved correction';
  const buttons = ['today', 'records'].map(id => node({ 'data-nav-target': id, 'data-nav-label': id === 'today' ? 'Today' : 'Records' }));
  const nav = node();
  const content = node();
  let sections = [today, records];
  nav.querySelectorAll = () => buttons;
  content.querySelectorAll = () => sections;
  const visited = [];
  const control = bindNavigation(nav, content, { onNavigate: (item) => visited.push(item) });
  return { nav, content, buttons, today, records, control, visited, replace: (value) => { sections = value; } };
}

test('daily work opens alone and task navigation preserves the hidden form draft', () => {
  const h = workspace();
  assert.equal(typeof h.control?.activate, 'function');
  h.control.activate();
  assert.equal(h.today.hidden, false);
  assert.equal(h.records.hidden, true);
  h.nav.click(h.buttons[1]);
  assert.equal(h.today.hidden, true);
  assert.equal(h.records.hidden, false);
  assert.equal(h.records.focused, true);
  assert.equal(h.records.getAttribute('aria-label'), 'Records');
  assert.equal(h.buttons[1].getAttribute('aria-current'), 'page');
  assert.equal(h.buttons[0].getAttribute('aria-current'), null);
  h.nav.click(h.buttons[0]);
  assert.equal(h.records.draft, 'Unsaved correction');
});

test('phone menu closes before the selected section is scrolled into view', () => {
  const h = workspace();
  const order = [];
  h.records.focus = () => order.push('focus');
  h.records.scrollIntoView = () => order.push('scroll');
  const control = bindNavigation(h.nav, h.content, { onNavigate: () => order.push('collapse-menu') });
  control.activate('records', { focus: true });
  assert.deepEqual(order, ['collapse-menu', 'focus', 'scroll']);
});

test('home task shortcuts navigate through the same control and unknown targets do nothing', () => {
  const h = workspace();
  assert.equal(typeof h.control?.activate, 'function');
  h.control.activate();
  h.content.click(node({ 'data-nav-target': 'records' }));
  assert.equal(h.records.hidden, false);
  h.content.click(node({ 'data-nav-target': 'not-authorized' }));
  assert.equal(h.records.hidden, false);
  assert.equal(h.today.hidden, true);
});

test('refresh keeps the current section and permission removal falls back to an available section', () => {
  const h = workspace();
  assert.equal(typeof h.control?.activate, 'function');
  h.control.activate('records');
  const nextToday = node({ id: 'today' });
  const nextRecords = node({ id: 'records' });
  h.replace([nextToday, nextRecords]);
  h.control.activate();
  assert.equal(nextRecords.hidden, false);
  assert.equal(nextToday.hidden, true);
  h.replace([nextToday]);
  h.control.activate();
  assert.equal(nextToday.hidden, false);
  assert.equal(h.buttons[0].getAttribute('aria-current'), 'page');
});

test('navigation renders ordered labelled groups without inventing links', () => {
  const html = navigationMarkup([
    { id: 'today', label: 'Today', group: 'Daily work' },
    { id: 'receipts', label: 'Receipts', group: 'Records' },
  ]);
  assert.match(html, /Daily work/);
  assert.match(html, /Records/);
  assert.equal((html.match(/data-nav-target=/g) || []).length, 2);
  assert.ok(html.indexOf('Today') < html.indexOf('Receipts'));
});
