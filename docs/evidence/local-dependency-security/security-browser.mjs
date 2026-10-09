import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const dir = 'C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007';
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [], blocked = [], workers = [], sources = [];
const sourceChecks = [];
page.on('pageerror', e => errors.push(e.message));
page.on('worker', worker => workers.push(worker.url()));
await page.route('**/*', route => {
  const url = new URL(route.request().url());
  if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
    blocked.push(url.href); return route.abort();
  }
  return route.continue();
});
page.on('response', response => {
  if (response.url().includes('/_next/static/') && response.url().includes('.js')) {
    sources.push(response.text().then(text => ({ url: response.url(), patchedSanitizer: text.includes('DOMPurify 3.4.16'), embeddedOldSanitizer: text.includes('DOMPurify 3.4.8'), text })).catch(() => null));
  }
});
try {
  await page.goto('http://127.0.0.1:3000/?session=c1b9feb0-10cc-48fe-9e23-0595b6d39c0d');
  await page.getByRole('button', { name: /^成果/ }).click();
  await page.getByRole('button', { name: /^代码变更/ }).first().waitFor();
  const expand = page.getByRole('button', { name: '展开 Diff', exact: true }).first();
  if (await expand.count() === 0) {
    await page.getByRole('button', { name: /^代码变更/ }).first().click();
  }
  await expand.waitFor(); await expand.click();
  await page.getByRole('button', { name: '并排对比', exact: true }).first().click();
  await page.locator('.monaco-diff-editor').first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(1500);
  const editor = page.locator('.monaco-diff-editor').first();
  const rendered = (await editor.innerText()).replace(/\u00a0/g, ' ');
  assert(rendered.includes('Continue'));
  assert(rendered.includes('Pinned Reference 20261008'));
  assert(workers.length > 0 && workers.every(url => url.startsWith('http://127.0.0.1:3000/')));
  const editArea = editor.locator('textarea').first();
  await editArea.focus(); await page.keyboard.type('UNEXPECTED_MUTATION');
  assert(!(await editor.innerText()).includes('UNEXPECTED_MUTATION'));
  await page.getByRole('button', { name: '展开成果', exact: true }).click();
  await page.screenshot({ path: dir + '/security-diff-light.png' });
  await page.getByRole('button', { name: '恢复布局', exact: true }).click();
  await page.getByRole('button', { name: '切换到暗色模式', exact: true }).click();
  await page.waitForTimeout(100);
  assert(await editor.locator('.monaco-editor.vs-dark').count() > 0);
  await page.getByRole('button', { name: '展开成果', exact: true }).click();
  await page.screenshot({ path: dir + '/security-diff-dark.png' });
  await page.getByRole('button', { name: '补丁', exact: true }).click();
  assert((await page.getByLabel('代码补丁').innerText()).includes('Pinned Reference 20261008'));
  await page.getByRole('button', { name: '并排对比', exact: true }).click();
  await editor.waitFor();
  await page.getByRole('button', { name: '恢复布局', exact: true }).click();
  await page.getByRole('button', { name: /^网页预览.*ready/ }).click();
  const frame = page.frameLocator('iframe').first();
  await frame.getByRole('button', { name: 'Pinned Reference 20261008', exact: true }).waitFor();
  await page.screenshot({ path: dir + '/security-preview.png' });
  const sourceResults = (await Promise.all(sources)).filter(Boolean);
  sourceChecks.push(...sourceResults.map(({text,...other}) => other));
  assert.deepEqual(errors, []);
  assert.deepEqual(blocked, []);
  assert(sourceResults.some(r => r.patchedSanitizer), 'Actual editor chunks must contain patched DOMPurify');
  assert(!sourceResults.some(r => r.embeddedOldSanitizer), 'Old embedded sanitizer must not be bundled');
  await writeFile(dir + '/security-browser.json', JSON.stringify({errors, blocked, workers, sources:sourceChecks, checks:['existing native Diff content displayed in local Monaco','external network blocked with no attempted requests','local editor worker started','actual chunks contain DOMPurify 3.4.16 and exclude embedded 3.4.8','read-only content resists keyboard mutation','light/dark editor and patch view switching','existing healthy Vite preview iframe displays native marker'], boundaries:['reused prior native TaskRun; no new model execution','no dependency audit suppression']}, null, 2));
  console.log(JSON.stringify({status:'passed', errors, blocked, workerCount:workers.length, patchedSanitizer:sourceResults.some(r=>r.patchedSanitizer)}));
} finally { await browser.close(); }
