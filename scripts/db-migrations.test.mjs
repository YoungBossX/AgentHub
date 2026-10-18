import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm, access } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const bash = process.platform === 'win32' ? path.resolve(path.dirname(spawnSync('where.exe', ['git'], { encoding: 'utf8' }).stdout.trim().split(/\r?\n/)[0]), '../bin/bash.exe') : 'bash';

async function spy(t, script, args = [], extra = {}) {
  const temp = await mkdtemp(path.join(os.tmpdir(), 'agenthub migration 参数 '));
  t.after(() => rm(temp, { recursive: true, force: true }));
  const output = path.join(temp, 'calls.jsonl');
  const nodeScript = path.join(temp, 'spy.mjs');
  await writeFile(nodeScript, `import fs from 'node:fs'; fs.appendFileSync(process.env.SPY_OUTPUT, JSON.stringify({args:process.argv.slice(2),url:process.env.AGENTHUB_DATABASE_URL})+'\\n'); process.exit(Number(process.env.SPY_EXIT || 0));`);
  const executable = path.join(temp, 'python-spy.sh');
  await writeFile(executable, '#!/usr/bin/env bash\nexec node "' + nodeScript.replaceAll('\\', '/') + '" "$@"\n', { mode: 0o700 });
  const result = spawnSync(bash, [path.join(root, 'scripts', script), ...args], { cwd: root,
    env: { ...process.env, AGENTHUB_PYTHON_BIN: executable, SPY_OUTPUT: output, ...extra }, encoding: 'utf8', timeout: 30000 });
  let calls = [];
  try { calls = (await readFile(output, 'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse); } catch { /* Assertions report missing invocation. */ }
  return { ...result, calls };
}

test('migration wrapper preserves structured arguments and child exit status', async t => {
  const args = ['upgrade', '--backup-dir', 'E:/备份 space/#%literal'];
  const result = await spy(t, 'db-migrations.sh', args, { SPY_EXIT: '7' });
  assert.equal(result.status, 7, result.stderr);
  assert.deepEqual(result.calls[0].args, ['-m', 'app.db_migrations', ...args]);
});

test('API wrapper overrides inherited product database before every import', async t => {
  const result = await spy(t, 'test-api.sh', [], { AGENTHUB_DATABASE_URL: 'sqlite:///DO-NOT-TOUCH-PRODUCT.sqlite3' });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.calls.length, 2);
  assert.deepEqual(result.calls[0].args, ['-m', 'app.db']);
  assert.equal(result.calls[1].args[1], 'pytest');
  assert.ok(result.calls.every(call => call.url.startsWith('sqlite:///') && !call.url.includes('DO-NOT-TOUCH')));
  assert.equal(result.calls[0].url, result.calls[1].url);
  assert.ok(result.calls[1].args.some(arg => arg.startsWith('--junitxml=')));
});

test('failed API setup retains bounded evidence and stops before pytest', async t => {
  const result = await spy(t, 'test-api.sh', [], { SPY_EXIT: '9' });
  assert.equal(result.status, 9, result.stderr);
  assert.equal(result.calls.length, 1);
  assert.match(result.stderr, /evidence retained/i);
});

test('migration wrapper has no runtime dependency installer', async () => {
  const source = await readFile(path.join(root, 'scripts/db-migrations.sh'), 'utf8');
  assert.doesNotMatch(source, /pip install|pnpm install|npm install/);
  assert.match(source, /"\$@"/);
});
