import test from 'node:test';
import assert from 'node:assert/strict';
import { searchBooks } from '../target/src/domain.mjs';

const books = Object.freeze([
  Object.freeze({ title: 'Agents', author: 'Alice' }),
  Object.freeze({ title: 'SQL Handbook', author: 'Bob' }),
  Object.freeze({ title: 'Agent Engineering', author: 'Carol' }),
  Object.freeze({ title: '中文书籍', author: '张三' }),
]);
test('searches title without case or surrounding whitespace', () => {
  assert.deepEqual(searchBooks(books, ' AGENT '), [books[0], books[2]]);
});
test('searches author and Unicode text', () => {
  assert.deepEqual(searchBooks(books, ' aLiCe '), [books[0]]);
  assert.deepEqual(searchBooks(books, '张三'), [books[3]]);
  assert.deepEqual(searchBooks(books, 'missing'), []);
});
test('blank query copies the array and retains object identity', () => {
  const result = searchBooks(books, ' \t ');
  assert.deepEqual(result, books);
  assert.notEqual(result, books);
  assert.equal(result[0], books[0]);
  assert.deepEqual(searchBooks([], ''), []);
});
