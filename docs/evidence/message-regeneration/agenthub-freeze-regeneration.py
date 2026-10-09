"""Freeze local message-regeneration evidence, including rejected first samples."""
import hashlib,json,re,shutil,sqlite3
from datetime import datetime,timezone
from pathlib import Path

REPO=Path('X:/Git_Clone/AgentHub');TEMP=Path('C:/Users/XCC/AppData/Local/Temp')
ROOT=TEMP/'agenthub-regeneration-20261009';DEST=REPO/'docs/evidence/message-regeneration'
def read(path):
    data=path.read_bytes();return data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def mapping(paths):return {p.relative_to(REPO).as_posix():sha(p) for p in paths}

full=read(TEMP/'agenthub-regenerate-full-2.log')
match=re.search(r'(\d+) passed, (\d+) skipped, .* in ([0-9.]+)s',full)
assert match and int(match[1])+int(match[2])==1846 and 'FAILED ' not in full
assert '249 passed' in read(TEMP/'agenthub-regenerate-web-full-1.log')
assert 'Compiled successfully' in read(TEMP/'agenthub-regenerate-build-final.log')
assert 'is valid' in read(TEMP/'agenthub-regenerate-openspec.log')
assert not read(TEMP/'agenthub-regenerate-diff-check.log').strip()
assert '- [x] 1.1' in read(REPO/'openspec/changes/agenthub-message-regeneration/tasks.md')
for name in ('native.json','network.json','restart-after.json','restart-browser.json'):
    assert json.loads(read(ROOT/name))['passed']
assert json.loads(read(ROOT/'layout-overflow.json'))==[]

code_names=['.gitignore','apps/api/app/models.py','apps/api/app/db.py','apps/api/app/schemas.py',
    'apps/api/app/main.py','apps/api/app/message_regeneration.py','apps/api/app/routes/messages.py',
    'apps/api/app/group_summaries.py','apps/api/app/attachment_context.py',
    'apps/api/tests/test_message_regeneration.py','apps/api/tests/test_message_regeneration_summary.py',
    'apps/api/tests/test_windows_connection_cleanup.py','apps/api/tests/test_group_planning.py','apps/api/tests/test_models.py',
    'apps/web/src/lib/api.ts','apps/web/src/components/chat-thread.tsx','apps/web/src/components/workspace-shell.tsx',
    'apps/web/src/components/group-summary-card.tsx','apps/web/src/components/message-regeneration.tsx',
    'apps/web/src/components/use-message-regeneration.ts','apps/web/src/components/message-regeneration.test.tsx',
    'apps/web/src/components/use-message-regeneration.test.ts']
previous_path=REPO/'docs/evidence/windows-connection-cleanup/validation-index.json'
previous=json.loads(read(previous_path));baseline={**previous['codeSha256'],**previous['unchangedBaselineSha256']}
unchanged={name:digest for name,digest in baseline.items() if name not in code_names}
assert all(sha(REPO/name)==digest for name,digest in unchanged.items()), 'Unexpected baseline code drift'
for key in ('evidenceSha256','specSha256'):
    assert all(sha(REPO/name)==digest for name,digest in previous[key].items()), 'Previous freeze changed'
DEST.mkdir(parents=True,exist_ok=True)
logs={'api-full.txt':'agenthub-regenerate-full-2.log','api-initial-failures.txt':'agenthub-regenerate-full-1.log',
      'api-related.txt':'agenthub-regenerate-initial.log','api-new-requests.txt':'agenthub-regenerate-tests-1.log',
      'api-summary-organization.txt':'agenthub-regenerate-summary-1.log','api-isolation-repro.txt':'agenthub-regenerate-group-repro.log',
      'api-isolation-fixed.txt':'agenthub-regenerate-group-fixed.log','web-full.txt':'agenthub-regenerate-web-full-1.log',
      'check.txt':'agenthub-regenerate-check-final.log','build.txt':'agenthub-regenerate-build-final.log',
      'openspec.txt':'agenthub-regenerate-openspec.log','diff-check.txt':'agenthub-regenerate-diff-check.log',
      'native.txt':'agenthub-regeneration-native-2.log','network.txt':'agenthub-regeneration-network.log',
      'restart-browser.txt':'agenthub-regeneration-after-restart.log','layout-fixed.txt':'agenthub-regeneration-layout-fixed.log'}
for name,source in logs.items():(DEST/name).write_text(read(TEMP/source),encoding='utf-8')
for path in ROOT.iterdir():
    if path.suffix in {'.json','.png','.txt'}:shutil.copyfile(path,DEST/path.name)
for name in ('agenthub-regeneration-history.py','agenthub-regeneration-native.mjs','agenthub-regeneration-network.mjs',
             'agenthub-regeneration-layout.mjs','agenthub-regeneration-restart.py','agenthub-regeneration-after-restart.mjs','agenthub-freeze-regeneration.py'):
    shutil.copyfile(TEMP/name,DEST/name)
lines=[]
for name in ('agenthub-regeneration-api.log','agenthub-regeneration-api-restarted.log'):
    path=TEMP/name;lines.extend([name,'SHA256 '+sha(path)])
    lines.extend(line for line in read(path).splitlines() if any(marker in line for marker in ('Started server process','Application startup complete','agenthub-ready:', 'Shutting down','Application shutdown complete','Finished server process')))
(DEST/'api-lifecycle.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')

native=json.loads(read(ROOT/'native.json'));network=json.loads(read(ROOT/'network.json'))
db_path=TEMP/'agenthub-local-completion-20261007/runtime.sqlite3'
outputs=[]
with sqlite3.connect(db_path) as db:
    db.row_factory=sqlite3.Row
    for stage in native['stages']:
        run=dict(db.execute('SELECT * FROM taskrun WHERE id=?',(stage['runId'],)).fetchone())
        assert run['state']=='completed'
        source_file=ROOT/f"native-source-{stage['number']}.txt"
        assert sha(source_file)==stage['sourceSha256']
        diffs=[]
        for expected in stage['diffs']:
            diff=dict(db.execute('SELECT * FROM diff WHERE id=?',(expected['id'],)).fetchone())
            assert hashlib.sha256(diff['patch_text'].encode()).hexdigest()==expected['patchSha256']
            diffs.append({'id':diff['id'],'patch':diff['patch_text'],'sha256':expected['patchSha256']})
        request=dict(db.execute('SELECT * FROM message WHERE id=?',(stage['requestId'],)).fetchone())
        task=dict(db.execute('SELECT * FROM task WHERE id=?',(stage['taskId'],)).fetchone())
        assert request['content_md']==native['request'] and task['created_by_message_id']==request['id']
        outputs.append({'stage':stage,'regeneration':json.loads(request['regeneration_json']),'diffs':diffs})
    current=Path(native['session']['worktreePath'])/'apps/demo/src/App.tsx'
    assert sha(current)==native['stages'][-1]['sourceSha256']==network['sourceSha256']
    rejected=json.loads(read(ROOT/'native-first-planner-rejected.json'))
    assert db.execute('SELECT count(*) FROM task WHERE session_id=?',(rejected['session']['id'],)).fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM message WHERE id=?',(network['operationId'],)).fetchone()[0]==1
(DEST/'persisted-native-outputs.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf-8')
code=[REPO/name for name in code_names]
docs=[REPO/'docs'/name for name in ('message-regeneration-review.md','change-log.md','project-state.md','local-usage.md','local-project-delivery.md')]
spec=sorted((REPO/'openspec/changes/agenthub-message-regeneration').rglob('*.md'))
evidence=sorted(p for p in DEST.iterdir() if p.is_file() and p.name!='validation-index.json')
settings=Path('C:/Users/XCC/.claude/settings.json');private=[]
if settings.exists():
    private=[v for k,v in json.loads(read(settings)).get('env',{}).items() if isinstance(v,str) and len(v)>8 and any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD','BASE_URL'))]
for path in [*code,*docs,*spec,*evidence]:
    if path.suffix=='.png':continue
    data=path.read_bytes()
    assert all(v.encode() not in data and json.dumps(v)[1:-1].encode() not in data for v in private),path.name
index={'scope':'agenthub-message-regeneration 1.1','status':'verified','createdAt':datetime.now(timezone.utc).isoformat(),
       'previousIndex':{'path':previous_path.relative_to(REPO).as_posix(),'sha256':sha(previous_path)},
       'codeSha256':mapping(code),'unchangedBaselineSha256':unchanged,'documentationSha256':mapping(docs),'specSha256':mapping(spec),'evidenceSha256':mapping(evidence),
       'verification':{'apiPassed':int(match[1]),'apiSkipped':int(match[2]),'apiSeconds':float(match[3]),'webPassed':249,
          'newBackendTests':18,'newWebTests':7,'check':'pnpm check exit 0','build':'Next 16.3.8 build exit 0',
          'native':'same request and attachment: real planner/Claude code changed counter 1 to 2; actual Diff and Vite',
          'summary':'two native summary regenerations; coding runs and source unchanged',
          'network':'actual committed request followed by dropped browser response; same UUID recovered/replayed once and other Session retained',
          'restart':'controlled committed preparation marked interrupted on actual restart; no auto dispatch; current iframe healthy',
          'history':'32 old Sessions,98 Messages,46 TaskRuns,37 Diffs,9 attachments unchanged in original columns;63 Tasks unchanged except one old scheduler updated_at',
          'privacy':'private SDK values excluded'},
       'limits':['Initial native planner command description rejected before task creation; not hidden or allowed',
          'Preparation restart case is controlled state injection, not a natural process crash',
          'Current context/config/worktree apply; not exact replay, rollback or task execution resumption',
          'Browser storage unavailable: uncertain ID survives only current page memory',
          'One local API process; no shared-database multi-process regeneration coordination',
          'Whole local project unfinished; next scope remains conversational Agent creation, bounded editing and final workflow/UI audit']}
(DEST/'validation-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for key,value in index.items():
    if key.endswith('Sha256'):assert all(sha(REPO/name)==digest for name,digest in value.items())
print(json.dumps({'verified':{key:len(value) for key,value in index.items() if key.endswith('Sha256')},'apiPassed':int(match[1]),'apiSkipped':int(match[2])}))
