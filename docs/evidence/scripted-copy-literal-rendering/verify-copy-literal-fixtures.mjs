import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const root='X:/Git_Clone/AgentHub';
const require=createRequire(root+'/apps/demo/package.json');
const ts=require('typescript');
const viteRequire=createRequire(require.resolve('vite/package.json'));
const esbuild=viteRequire('esbuild');
const { chromium }=createRequire(import.meta.url)('C:/Users/XCC/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/copy-literal-fixtures';
const hash=value=>createHash('sha256').update(value).digest('hex');
const fixture=JSON.parse(await readFile(folder+'/fixture-sources.json','utf8'));
assert.equal(hash(await readFile(root+'/apps/api/app/scripted_mock.py')),fixture.adapterSha256);
const results=[],browser=await chromium.launch({channel:'msedge',headless:true});
const virtual=root+'/apps/demo/src/agenthub-literal-fixture.tsx';
const matches=name=>name.replaceAll('\\','/').toLowerCase()===virtual.toLowerCase();
try {
  const page=await browser.newPage();
  for(const test of fixture.cases) {
    assert.equal(hash(test.source),test.sourceSha256);
    const options={noEmit:true,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,
      module:ts.ModuleKind.ESNext,moduleResolution:ts.ModuleResolutionKind.Bundler,skipLibCheck:true,strict:true};
    const host=ts.createCompilerHost(options),read=host.readFile,exists=host.fileExists,get=host.getSourceFile;
    host.readFile=name=>matches(name)?test.source:read(name);
    host.fileExists=name=>matches(name)||exists(name);
    host.getSourceFile=(name,version,onError,createNew)=>matches(name)?ts.createSourceFile(name,test.source,version,true,ts.ScriptKind.TSX):get(name,version,onError,createNew);
    const program=ts.createProgram([virtual],options,host);
    const diagnostics=ts.getPreEmitDiagnostics(program);
    assert.deepEqual(diagnostics.map(d=>ts.flattenDiagnosticMessageText(d.messageText,'\n')),[]);
    const bundle=await esbuild.build({stdin:{contents:test.source+'\nimport {createRoot} from "react-dom/client";createRoot(document.getElementById("root")).render(<App/>);',
      resolveDir:root+'/apps/demo/src',sourcefile:'literal-fixture.tsx',loader:'tsx'},
      bundle:true,write:false,format:'iife',jsx:'automatic',target:'es2022',define:{'process.env.NODE_ENV':'"production"'}});
    await page.goto('about:blank');await page.setContent('<!doctype html><div id="root"></div>');
    const errors=[];const onError=e=>errors.push(e.message);page.on('pageerror',onError);
    await page.addScriptTag({content:bundle.outputFiles[0].text});
    const element=page.locator(test.target==='demo_heading_text'?'#demo-heading':'[data-agenthub-target="primary-action-button"]');
    await element.waitFor();const text=await element.textContent(),children=await element.locator('*').count();
    assert.equal(text,test.value);assert.equal(children,0);assert.deepEqual(errors,[]);page.off('pageerror',onError);
    results.push({target:test.target,expected:test.value,actual:text,childElements:children,typeErrors:diagnostics.length,browserErrors:errors,sourceSha256:test.sourceSha256});
  }
  await writeFile(folder+'/fixture-results.json',JSON.stringify({boundary:fixture.boundary,typescript:ts.version,esbuild:esbuild.version,
    adapterSha256:fixture.adapterSha256,verifierSha256:hash(await readFile(new URL(import.meta.url))),cases:results},null,2));
  console.log('PASS '+results.length+' structured adapter -> strict TypeScript -> esbuild -> actual Edge React DOM fixtures');
} finally {await browser.close();}
