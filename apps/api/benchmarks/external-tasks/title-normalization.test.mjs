import test from 'node:test';
import assert from 'node:assert/strict';
import { slugifyTitle } from '../target/src/domain.mjs';

test('normalizes punctuation, whitespace and separators', () => {
  assert.equal(slugifyTitle('  Hello__World!! '), 'hello-world');
  assert.equal(slugifyTitle('A\t\nB---C'), 'a-b-c');
});
test('keeps Unicode letters and numbers', () => {
  assert.equal(slugifyTitle(' 中文 书籍 42 '), '中文-书籍-42');
  assert.equal(slugifyTitle('Café déjà vu'), 'café-déjà-vu');
});
test('handles empty titles', () => {
  assert.equal(slugifyTitle(''), '');
  assert.equal(slugifyTitle(' !!__ '), '');
});
