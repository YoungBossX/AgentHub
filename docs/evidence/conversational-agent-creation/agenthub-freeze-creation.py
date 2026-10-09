import hashlib,json,re,shutil,sqlite3
from datetime import datetime,timezone
from pathlib import Path

REPO=Path('X:/Git_Clone/AgentHub');TEMP=Path('C:/Users/XCC/AppData/Local/Temp')
ROOT=TEMP/'agenthub-creation-20261009';DEST=REPO/'docs/evidence/conversational-agent-creation'
def read(path):
    value=path.read_bytes();return value.decode('utf-16' if value.startswith(b'\xff\xfe') else 'utf-8-sig')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def mapping(paths):return {p.relative_to(REPO).as_posix():sha(p) for p in paths}
full=read(TEMP/'agenthub-creation-full-1.log')
match=re.search(r'(\d+) passed, (\d+) skipped, .* in ([0-9.]+)s',full)
assert match and int(match[1])+int(match[2])==1874 and 'FAILED ' not in full
assert '256 passed' in read(TEMP/'agenthub-creation-web-full-1.log')
assert '28 passed' in read(TEMP/'agenthub-creation-new-2.log')
assert '123 passed' in read(TEMP/'agenthub-creation-related-1.log')
assert 'Compiled successfully' in read(TEMP/'agenthub-creation-build-1.log')
assert 'is valid' in read(TEMP/'agenthub-creation-openspec.log')
assert not read(TEMP/'agenthub-creation-diff-check.log').strip()
assert '- [x] 1.1' in read(REPO/'openspec/changes/agenthub-conversational-agent-creation/tasks.md')
native=json.loads(read(ROOT/'native.json'));restart=json.loads(read(ROOT/'restart-browser.json'))
assert native['passed'] and restart['passed'] and native['runtimeRestored']
assert json.loads(read(ROOT/'native-restart-before.json'))==json.loads(read(ROOT/'native-restart-after.json'))

code_names=['.gitignore','apps/api/app/agent_creation.py','apps/api/app/custom_agents.py',
    'apps/api/app/planner_providers.py','apps/api/app/routes/agent_settings.py','apps/api/tests/test_agent_creation.py',
    'apps/web/src/lib/api.ts','apps/web/src/components/custom-agent-editor.tsx',
    'apps/web/src/components/agent-creation-chat.tsx','apps/web/src/components/agent-creation-chat.test.tsx',
    'apps/web/src/components/agent-directory-settings-page-client.tsx','apps/web/src/components/session-sidebar.tsx']
previous_path=REPO/'docs/evidence/message-regeneration/validation-index.json'
previous=json.loads(read(previous_path));baseline={**previous['codeSha256'],**previous['unchangedBaselineSha256']}
unchanged={name:digest for name,digest in baseline.items() if name not in code_names}
assert all(sha(REPO/name)==digest for name,digest in unchanged.items()),'Previous baseline code changed outside scope'
for key in ('evidenceSha256','specSha256'):
    assert all(sha(REPO/name)==digest for name,digest in previous[key].items()),'Previous frozen evidence changed'
DEST.mkdir(parents=True,exist_ok=True)
logs={'api-full.txt':'agenthub-creation-full-1.log','api-new.txt':'agenthub-creation-new-2.log',
    'api-initial-test-id-errors.txt':'agenthub-creation-new-1.log','api-related.txt':'agenthub-creation-related-1.log',
    'web-new.txt':'agenthub-creation-web-new-1.log','web-full.txt':'agenthub-creation-web-full-1.log',
    'check.txt':'agenthub-creation-check-1.log','build.txt':'agenthub-creation-build-1.log',
    'openspec.txt':'agenthub-creation-openspec.log','diff-check.txt':'agenthub-creation-diff-check.log',
    'native-setup-rejected.txt':'agenthub-creation-native-1.log','native.txt':'agenthub-creation-native-2.log',
    'restart-browser.txt':'agenthub-creation-restart-browser.log'}
for name,source in logs.items():(DEST/name).write_text(read(TEMP/source),encoding='utf-8')
for path in ROOT.iterdir():
    if path.suffix in {'.json','.png','.txt'}:shutil.copyfile(path,DEST/path.name)
for name in ('agenthub-creation-runtime.py','agenthub-creation-native.mjs','agenthub-creation-restart-browser.mjs','agenthub-freeze-creation.py'):
    shutil.copyfile(TEMP/name,DEST/name)
lines=[]
for name in ('agenthub-creation-api.log','agenthub-creation-api-restarted.log'):
    path=TEMP/name;lines.extend([name,'SHA256 '+sha(path)])
    lines.extend(line for line in read(path).splitlines() if any(marker in line for marker in ('Started server process','Application startup complete','agenthub-ready:','Shutting down','Application shutdown complete','Finished server process')))
(DEST/'api-lifecycle.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')

with sqlite3.connect(TEMP/'agenthub-local-completion-20261007/runtime.sqlite3') as db:
    db.row_factory=sqlite3.Row
    profile=dict(db.execute('select * from agentprofiledraft where id=?',(native['profile']['id'],)).fetchone())
    assert profile['status']=='available' and profile['tool_policy']=='claude_file_edit'
    assert profile['system_prompt']==native['profile']['systemPrompt']
    assert hashlib.sha256(profile['system_prompt'].encode()).hexdigest()==native['execution']['instruction']['sha256']
    run=dict(db.execute('select * from taskrun where id=?',(native['execution']['runId'],)).fetchone())
    assert run['state']=='completed'
    diff=dict(db.execute('select * from diff where id=?',(native['execution']['diffs'][0]['id'],)).fetchone())
    assert hashlib.sha256(diff['patch_text'].encode()).hexdigest()==native['execution']['diffs'][0]['sha256']
    assert sha(Path(native['session']['worktreePath'])/'apps/demo/src/App.tsx')==native['execution']['sourceSha256']
    assert db.execute('select count(*) from agentprofiledraft where workspace_id=? and mention_alias=?',(native['workspaceId'],profile['mention_alias'])).fetchone()[0]==1
    (DEST/'persisted-output.json').write_text(json.dumps({'profileId':profile['id'],'promptSha256':native['execution']['instruction']['sha256'],'runId':run['id'],'diffId':diff['id'],'patchText':diff['patch_text']},ensure_ascii=False,indent=2),encoding='utf-8')

docs=[REPO/'docs'/name for name in ('conversational-agent-creation-review.md','change-log.md','project-state.md','local-usage.md','local-project-delivery.md')]
code=[REPO/name for name in code_names];spec=sorted((REPO/'openspec/changes/agenthub-conversational-agent-creation').rglob('*.md'))
evidence=sorted(p for p in DEST.iterdir() if p.is_file() and p.name!='validation-index.json')
private=[];settings=Path('C:/Users/XCC/.claude/settings.json')
if settings.exists():
    private=[v for k,v in json.loads(read(settings)).get('env',{}).items() if isinstance(v,str) and len(v)>8 and any(s in k.upper() for s in ('KEY','TOKEN','SECRET','PASSWORD','BASE_URL'))]
for path in [*code,*docs,*spec,*evidence]:
    if path.suffix=='.png':continue
    data=path.read_bytes()
    assert all(v.encode() not in data and json.dumps(v)[1:-1].encode() not in data for v in private),path.name
index={'scope':'agenthub-conversational-agent-creation 1.1','status':'verified','createdAt':datetime.now(timezone.utc).isoformat(),
    'previousIndex':{'path':previous_path.relative_to(REPO).as_posix(),'sha256':sha(previous_path)},
    'codeSha256':mapping(code),'unchangedBaselineSha256':unchanged,'documentationSha256':mapping(docs),'specSha256':mapping(spec),'evidenceSha256':mapping(evidence),
    'verification':{'apiPassed':int(match[1]),'apiSkipped':int(match[2]),'apiSeconds':float(match[3]),'webPassed':256,'newBackendTests':28,'newFrontendTests':7,
        'relatedBackendTests':123,'check':'pnpm check exit 0','build':'Next 16.3.8 build exit 0','nativeGenerationCount':2,
        'profileId':native['profile']['id'],'nativeRunId':native['execution']['runId'],'provider':'claude_code',
        'promptBound':True,'diffSourceViteMatched':True,'refreshRestored':native['refreshRestored'],'nativeRowsPreservedAfterRestart':True,
        'originalRuntimeConfigurationRestored':True,'privacy':'private SDK values excluded'},
    'limits':['Configuration generator has no execution tools and never saves by itself; explicit existing form save is required',
        'Draft history persists only within the browser tab; unavailable storage falls back to current page memory',
        'Current Planner must be configured; unavailable/invalid native output is rejected without fabricated fallback',
        'Two original timestamps changed: restored runtime configuration and the existing scheduler Task; other original row fields match',
        'Initial setup test omitted planner Profile ID and was rejected; driver corrected without weakening runtime validation',
        '1874 API test nodes include two environment-conditional skips; UTC deprecation warnings remain visible',
        'Whole local project is still unfinished: bounded editing/apply Diff and final workflow/UI audit remain']}
(DEST/'validation-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for key,value in index.items():
    if key.endswith('Sha256'):assert all(sha(REPO/name)==digest for name,digest in value.items())
print(json.dumps({'verified':{key:len(value) for key,value in index.items() if key.endswith('Sha256')},'apiPassed':int(match[1]),'apiSkipped':int(match[2])}))
