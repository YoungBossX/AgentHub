import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

repo=Path('X:/Git_Clone/AgentHub')
temp=Path(__file__).parent
dest=repo/'docs/evidence/scope-finalization-performance'
digest=lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
full=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-scope-finalization-full-20261008.log')
assert '1770 passed, 1 skipped' in full.read_text(encoding='utf-8-sig')
assert '- [x] 1.1' in (repo/'openspec/changes/agenthub-scope-finalization-performance/tasks.md').read_text(encoding='utf-8')
dest.mkdir(parents=True,exist_ok=True)

def write(name,value):
    (dest/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

for tag, helper in [('original','accept-scope-timing.mjs'),('revised','accept-scope-timing.mjs'),('browser','accept-scope-browser.mjs'),('restart','accept-scope-restart.mjs')]:
    folder=temp/('scope-timing-'+tag)
    proof=json.loads((folder/'acceptance.json').read_text(encoding='utf-8'))
    assert digest(temp/helper)==proof['helperSha256']
    executed=json.loads((folder/'executed-source.json').read_text(encoding='utf-8'))
    for name, expected in executed.items():
        source=(temp/'scope-timing-before-verified'/Path(name).name) if tag=='original' and Path(name).name in {'run_engine.py','task_runs.py'} else repo/name
        assert digest(source)==expected, name
    for path in folder.iterdir():
        if path.suffix in {'.json','.txt','.png'}:
            shutil.copyfile(path,dest/(tag+'-'+path.name))
for name in ['task_runs.py','run_engine.py']:
    shutil.copyfile(temp/'scope-timing-before-verified'/name,dest/('before-'+name))
for name in ['accept-scope-timing.mjs','accept-scope-browser.mjs','accept-scope-restart.mjs','scope-timing-server.py','profile-scope-snapshot.py','analyze-scope-timing.py','freeze-scope-performance.py']:
    shutil.copyfile(temp/name,dest/name)
shutil.copyfile(temp/'scope-timing-comparison.json',dest/'timing-comparison.json')
for name in ['profile.json','top.txt']:
    shutil.copyfile(temp/'scope-profile-before'/name,dest/('profile-'+name))
profile=json.loads((dest/'profile-profile.json').read_text(encoding='utf-8'))
assert profile['sourceSha256']==digest(repo/'apps/api/app/task_run_scope.py')
assert profile['available'] and profile['scopeEntryCount']==517
comparison=json.loads((dest/'timing-comparison.json').read_text(encoding='utf-8'))
assert comparison['original']['totalSnapshots']==8 and comparison['revised']['totalSnapshots']==6
for before, after in zip(comparison['original']['runs'],comparison['revised']['runs']):
    assert before['scopeBaselineSha256']==after['scopeBaselineSha256']
browser=json.loads((dest/'browser-acceptance.json').read_text(encoding='utf-8'))
assert len(browser['previews'])==2
assert [p['actualText'] for p in browser['previews']]==['Timing first','Timing second']
assert all(not p['errors'] for p in browser['previews'])
restart=json.loads((dest/'restart-acceptance.json').read_text(encoding='utf-8'))
assert restart['historyBefore']==restart['historyAfterStartup'] and len(restart['historyBefore'])==4
assert restart['actualText']=='Timing second' and not restart['errors']
for stem, name in [('focused','focused-tests.txt'),('full','api-tests.txt'),('check','static-checks.txt'),('openspec','openspec-checks.txt')]:
    shutil.copyfile(Path('C:/Users/XCC/AppData/Local/Temp')/f'agenthub-scope-finalization-{stem}-20261008.log',dest/name)
assert '543 passed, 1 skipped' in (dest/'focused-tests.txt').read_text(encoding='utf-8-sig')

code=['.gitignore','apps/api/app/task_runs.py','apps/api/app/run_engine.py','apps/api/tests/test_task_runs.py']
previous=json.loads((repo/'docs/evidence/scripted-copy-literal-rendering/validation-index.json').read_text(encoding='utf-8'))
unchanged={name:expected for name,expected in {**previous['codeSha256'],**previous['unchangedBaselineSha256']}.items() if name not in code}
unchanged['apps/api/app/task_run_scope.py']=profile['sourceSha256']
assert all(digest(repo/name)==expected for name,expected in unchanged.items())
docs=['docs/change-log.md','docs/project-state.md','docs/local-project-delivery.md','docs/local-usage.md','docs/scope-finalization-performance-review.md']
index={'status':'verified','createdAt':datetime.now(timezone.utc).isoformat(),'scope':'agenthub-scope-finalization-performance 1.1',
       'codeSha256':{name:digest(repo/name) for name in code},'unchangedBaselineSha256':unchanged,
       'documentationSha256':{name:digest(repo/name) for name in docs},
       'specSha256':{p.relative_to(repo).as_posix():digest(p) for p in sorted((repo/'openspec/changes/agenthub-scope-finalization-performance').rglob('*.md'))},
       'evidenceSha256':{p.name:digest(p) for p in sorted(dest.iterdir()) if p.name!='validation-index.json'},
       'tests':{'focusedApi':'543 passed / 1 POSIX-only skipped','fullApi':'1770 passed / 1 POSIX-only skipped','browser':'2 actual Vite DOM continuations and 1 post-restart restore','static':'pnpm check passed','openspec':'strict passed','whitespace':'git diff --check passed'},
       'boundaries':['Two scripted tasks per timing version with matching baseline entry hashes; no general performance or real-model claim','Collector bytes and all protected checks retained; no cache or path filtering','Browser acceptance under regression load is excluded from before/after timings','Fresh isolated SQLite and API8007; main API8006 and existing native session preserved; main API needs normal restart','No dependencies installed, historical evidence rewritten, commit, push or deployment; complete project audit remains']}
write('validation-index.json',index)
private=json.loads(Path('C:/Users/XCC/.claude/settings.json').read_text(encoding='utf-8-sig')).get('env',{})
values=[value for value in private.values() if isinstance(value,str) and len(value)>=8]
for path in dest.iterdir():
    assert path.suffix in {'.json','.txt','.png','.mjs','.py'}
    if path.suffix!='.png':
        assert not any(value in path.read_text(encoding='utf-8-sig') for value in values),'Private SDK value in evidence'
for name in docs:
    assert not any(value in (repo/name).read_text(encoding='utf-8') for value in values),'Private SDK value in docs'
for key in ['codeSha256','unchangedBaselineSha256','documentationSha256','specSha256']:
    assert all(digest(repo/name)==expected for name,expected in index[key].items())
assert all(digest(dest/name)==expected for name,expected in index['evidenceSha256'].items())
print(f'Verified {len(code)} code, {len(unchanged)} unchanged, {len(docs)} docs, {len(index["specSha256"])} spec, {len(index["evidenceSha256"])} evidence hashes; private SDK values excluded')
