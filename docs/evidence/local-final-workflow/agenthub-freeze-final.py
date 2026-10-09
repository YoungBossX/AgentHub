import hashlib, json, os, re, shutil
from pathlib import Path

repo=Path('X:/Git_Clone/AgentHub').resolve()
temp=Path('C:/Users/XCC/AppData/Local/Temp')
source=temp/'agenthub-final-local-20261009'
out=repo/'docs/evidence/local-final-workflow'
assert out.resolve().is_relative_to(repo)
out.mkdir(parents=True,exist_ok=True)
reports=['native.json','native-driver-first-failure.json','selection-first-failure.json',
         'selection-planner-failure.json','selection-runtime.json','codex-followup.json','recovery.json',
         'history-before.json','history-final.json','restart-before.json','restart-after.json','final-browser.json',
         'composer-after.json']
for name in reports: shutil.copyfile(source/name,out/name)
# The initial probe's screenshots were overwritten by a later measurement. The
# retained initial stdout is the source for before geometry; do not invent images.
before=json.loads(next(line for line in (temp/'agenthub-final-ui-probe.log').read_text(encoding='utf-8-sig').splitlines() if line.startswith('{')))
assert all(row['form']['right']>320 for row in before['measurements'] if row['width']==320)
(out/'composer-before.json').write_text(json.dumps(before,indent=2),encoding='utf-8')
for name in ['composer-320-light-after.png','composer-320-dark-after.png','composer-1440-light-after.png',
             'selection-context-320-dark.png','selection-context-390-light.png','selection-context-1440-light.png',
             'selection-native-preview.png','final-codex-preview.png','final-claude-preview.png','final-fallback-preview.png']:
    shutil.copyfile(source/name,out/name)
for name in ['agenthub-final-ui-probe.mjs','agenthub-final-native.mjs','agenthub-final-selection.mjs',
             'agenthub-final-codex-followup.mjs','agenthub-final-recovery.mjs','agenthub-final-browser.mjs',
             'agenthub-final-history.py','agenthub-final-restart.py','agenthub-freeze-final.py']:
    shutil.copyfile(temp/name,out/name)
logs={
 'clock-first-failure':'agenthub-final-clock-1.log','clock-contract':'agenthub-final-clock-2.log',
 'web-first-lint':'agenthub-final-web-check-1.log','web-fixture-failure':'agenthub-final-web-final.log',
 'web-final':'agenthub-final-web-final-2.log','api-first-full-stage':'agenthub-final-api-all.log',
 'reference-first-failure':'agenthub-final-references.log','reference-related':'agenthub-final-references-3.log',
 'api-final':'agenthub-final-api-all-2.log','local-tests':'agenthub-final-local-test.log',
 'demo-api':'agenthub-final-demo-api.log','doctor-occupied':'agenthub-final-doctor.log','doctor-free':'agenthub-final-doctor-free.log',
 'check':'agenthub-final-gates-check.log','build':'agenthub-final-build.log',
 'openspec':'agenthub-final-gates-openspec.log','diff-check':'agenthub-final-gates-diff.log',
 'native':'agenthub-final-native-2.log','selection-planner-failure':'agenthub-final-selection-6.log',
 'selection-corrected':'agenthub-final-selection-corrected.log','codex-followup':'agenthub-final-codex-followup.log',
 'recovery':'agenthub-final-recovery.log','final-browser':'agenthub-final-browser.log',
}
for name,filename in logs.items(): shutil.copyfile(temp/filename,out/(name+'.txt'))
assert '1949 passed, 1 skipped' in (out/'api-final.txt').read_text(encoding='utf-8')
assert '267 passed' in (out/'web-final.txt').read_text(encoding='utf-8')
assert '105 passed' in (out/'reference-related.txt').read_text(encoding='utf-8')
for name in ['native','selection-runtime','codex-followup','recovery','restart-after','final-browser','history-final']:
    assert json.loads((out/(name+'.json')).read_text(encoding='utf-8'))['passed'],name
assert '- [x] 1.1' in (repo/'openspec/changes/agenthub-local-final-workflow-acceptance/tasks.md').read_text(encoding='utf-8')
code=[]
for root in ['apps/api/app','apps/api/tests','apps/web/src','apps/demo/src','apps/demo-api/app','scripts']:
    code.extend(p for p in (repo/root).rglob('*') if p.is_file() and p.suffix in {'.py','.ts','.tsx','.css','.mjs','.cjs','.sh'})
code.extend(repo/name for name in ['AGENTS.md','.gitignore','package.json','pnpm-lock.yaml','apps/api/requirements.txt','apps/web/package.json','apps/web/AGENTS.md'])
docs=[repo/name for name in ['docs/local-final-workflow-review.md','docs/local-project-delivery.md','docs/project-state.md','docs/change-log.md','docs/local-usage.md']]
specs=list((repo/'openspec/changes/agenthub-local-final-workflow-acceptance').rglob('*.md'))
hashfile=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mapping=lambda paths:{str(p.relative_to(repo)).replace('\\','/'):hashfile(p) for p in sorted(paths)}
for path in out.iterdir():
    if path.suffix in {'.json','.txt','.py','.mjs'}:
        data=path.read_text(encoding='utf-8')
        for key,value in os.environ.items():
            if any(marker in key.upper() for marker in ['TOKEN','SECRET','PASSWORD','API_KEY']) and len(value)>=12:
                assert value not in data,f'Private environment value detected in {path.name}; key={key}'
manifest={'task':'agenthub-local-final-workflow-acceptance 1.1','status':'verified_local_uncommitted',
          'verification':{'apiFinal':{'passed':1949,'skipped':1,'deprecations':'errors'},'web':267,'localTools':17,'demoApi':5,
                          'boundary':'Actual native CLI and browser evidence is local; injected failure and queued interruption are labeled. No production deployment or full PDF P2 coverage.'},
          'code':mapping(set(code)),'docs':mapping(docs),'specs':mapping(specs),
          'evidence':mapping(p for p in out.iterdir() if p.name!='validation-index.json')}
(out/'validation-index.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for key in ['code','docs','specs','evidence']:
    for name,expected in manifest[key].items(): assert hashfile(repo/name)==expected,name
print(json.dumps({'passed':True,'counts':{k:len(manifest[k]) for k in ['code','docs','specs','evidence']}}))
