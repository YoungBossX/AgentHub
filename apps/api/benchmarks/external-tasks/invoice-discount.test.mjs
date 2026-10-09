import test from 'node:test';
import assert from 'node:assert/strict';
import { invoiceTotalCents } from '../target/src/domain.mjs';

test('applies discount once and rounds the final cents', () => {
  assert.equal(invoiceTotalCents([{ priceCents: 999, quantity: 2 }], 1500), 1698);
  assert.equal(invoiceTotalCents([{ priceCents: 1, quantity: 1 }], 5000), 1);
  assert.equal(invoiceTotalCents([{ priceCents: 1, quantity: 1 }, { priceCents: 1, quantity: 1 }], 5000), 1);
});
test('supports defaults, empty, zero and full discount', () => {
  assert.equal(invoiceTotalCents([{ priceCents: 100, quantity: 3 }]), 300);
  assert.equal(invoiceTotalCents([], 2500), 0);
  assert.equal(invoiceTotalCents([{ priceCents: 100, quantity: 0 }]), 0);
  assert.equal(invoiceTotalCents([{ priceCents: 100, quantity: 3 }], 10000), 0);
});
test('rejects invalid integers and unsafe totals', () => {
  for (const invalid of [-1, 0.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => invoiceTotalCents([{ priceCents: invalid, quantity: 1 }]), RangeError);
    assert.throws(() => invoiceTotalCents([{ priceCents: 1, quantity: invalid }]), RangeError);
  }
  for (const invalid of [-1, 10001, 0.5, NaN, Infinity]) {
    assert.throws(() => invoiceTotalCents([], invalid), RangeError);
  }
  assert.throws(() => invoiceTotalCents([{ priceCents: Number.MAX_SAFE_INTEGER, quantity: 2 }]), RangeError);
  assert.throws(() => invoiceTotalCents([{ priceCents: Number.MAX_SAFE_INTEGER, quantity: 1 }, { priceCents: 1, quantity: 1 }]), RangeError);
});
test('preserves inputs', () => {
  const line = Object.freeze({ priceCents: 100, quantity: 2 });
  const lines = Object.freeze([line]);
  assert.equal(invoiceTotalCents(lines, 5000), 100);
  assert.equal(lines[0], line);
});
