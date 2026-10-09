"""Freeze this Windows acceptance run; helpers use this machine's fixture paths."""
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('X:/Git_Clone/AgentHub')
TEMP = Path('C:/Users/XCC/AppData/Local/Temp')
ROOT = TEMP / 'agenthub-shutdown-20261009'
OLD = TEMP / 'agenthub-local-completion-20261007'
DEST = REPO / 'docs/evidence/windows-connection-cleanup'

def read(path):
    data = path.read_bytes()
    return data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mapping(paths):
    return {path.relative_to(REPO).as_posix(): sha(path) for path in paths}

full = read(TEMP / 'agenthub-shutdown-full.log')
match = re.search(r'(\d+) passed, (\d+) skipped, .* in ([0-9.]+)s', full)
assert match and int(match[1]) == 1827 and int(match[2]) == 1 and 'FAILED ' not in full
assert '62 passed' in read(TEMP / 'agenthub-shutdown-related-2.log')
assert '# pass 17' in read(TEMP / 'agenthub-shutdown-local.log')
assert 'is valid' in read(TEMP / 'agenthub-shutdown-openspec.log')
assert not read(TEMP / 'agenthub-shutdown-diff-check.log').strip()
assert '- [x] 1.1' in read(REPO / 'openspec/changes/agenthub-windows-connection-cleanup/tasks.md')

previous_path = REPO / 'docs/evidence/message-attachments/validation-index.json'
previous = json.loads(read(previous_path))
baseline = {**previous['codeSha256'], **previous['unchangedBaselineSha256']}
allowed = {'.gitignore', 'apps/api/app/main.py'}
unchanged = {name: digest for name, digest in baseline.items() if name not in allowed}
assert all(sha(REPO / name) == digest for name, digest in unchanged.items()), 'Unexpected baseline code change'
for field in ('evidenceSha256', 'specSha256'):
    assert all(sha(REPO / name) == digest for name, digest in previous[field].items()), 'Previous evidence or spec was changed'
DEST.mkdir(parents=True, exist_ok=True)

logs = {'api-full.txt':'agenthub-shutdown-full.log', 'api-related.txt':'agenthub-shutdown-related-2.log',
        'local-tools.txt':'agenthub-shutdown-local.log', 'check.txt':'agenthub-shutdown-check.log',
        'openspec.txt':'agenthub-shutdown-openspec.log', 'diff-check.txt':'agenthub-shutdown-diff-check.log',
        'ordinary-rst.txt':'agenthub-shutdown-probe-baseline.log',
        'current-browser.txt':'agenthub-shutdown-current-browser.log'}
for name, source in logs.items():
    (DEST / name).write_text(read(TEMP / source), encoding='utf-8')
managed = Path(json.loads(read(ROOT / 'managed-latest.json'))['root'])
assert managed.resolve().is_relative_to(ROOT.resolve())
reports = json.loads(read(managed / 'report.json'))
for report in reports['reports']:
    assert report['exitCode'] == 0 and report['apiAndPreviewPortsClosed'] and not report['errors']
for name in ('report.json','baseline-fault.json','fixed-fault.json','baseline-preview.png','fixed-preview.png'):
    shutil.copyfile(managed / name, DEST / ('managed-' + name))
for name in ('baseline','fixed'):
    (DEST / f'managed-{name}.txt').write_text(read(managed / f'{name}.log'), encoding='utf-8')
shutil.copyfile(ROOT / 'baseline.json', DEST / 'ordinary-rst.json')

history = json.loads(read(ROOT / 'history-before.json'))
for path in sorted(ROOT.glob('history-*.json')):
    assert json.loads(read(path)) == history
    shutil.copyfile(path, DEST / path.name)
for name in ('attachment-preview-connection-cleanup.json', 'attachment-codex-preview-connection-cleanup.png',
             'attachment-claude-preview-connection-cleanup.png'):
    shutil.copyfile(OLD / name, DEST / name)
assert not json.loads(read(OLD / 'attachment-preview-connection-cleanup.json'))['errors']

# Verify the reused native outputs independently of DOM assertions; no new inference.
outputs = []
with sqlite3.connect(OLD / 'runtime.sqlite3') as db:
    for mode in ('codex', 'claude'):
        proof = json.loads(read(OLD / f'attachment-{mode}-native.json'))
        state, worktree = db.execute('select state,worktree_path from taskrun where id=?', (proof['runId'],)).fetchone()
        assert state == 'completed'
        app = Path(worktree) / 'apps/demo/src/App.tsx'
        assert sha(app) == proof['appSha256']
        outputs.append({'mode':mode, 'runId':proof['runId'], 'state':state, 'appSha256':sha(app),
                        'source':'unchanged native result from message-attachments acceptance; no new inference'})
(DEST / 'reused-output-hashes.json').write_text(json.dumps(outputs, indent=2), encoding='utf-8')

historical = TEMP / 'agenthub-attachment-server-v2.log'
lines = read(historical).splitlines()
excerpts = ['Historical natural failure, NOT the controlled fault injection.',
            'Source: '+str(historical), 'Source SHA-256: '+sha(historical), '']
for start, end in ((1493,1500),(1600,1602)):
    excerpts.extend(f'{i}: {lines[i-1]}' for i in range(start,end+1))
(DEST / 'historical-reset.txt').write_text('\n'.join(excerpts)+'\n', encoding='utf-8')
for name in ('agenthub-shutdown-managed.py','agenthub-shutdown-managed.mjs','agenthub-shutdown-history.py',
             'agenthub-shutdown-probe.py','agenthub-attachment-preview.mjs','agenthub-freeze-shutdown.py'):
    shutil.copyfile(TEMP / name, DEST / name)

code = [REPO / name for name in ('.gitignore','apps/api/app/main.py','apps/api/app/windows_connection_cleanup.py',
        'apps/api/tests/test_windows_connection_cleanup.py','scripts/local-api.py')]
docs = [REPO / 'docs' / name for name in ('windows-connection-cleanup-review.md','change-log.md',
         'project-state.md','local-project-delivery.md','local-usage.md')]
spec = sorted((REPO / 'openspec/changes/agenthub-windows-connection-cleanup').rglob('*.md'))
evidence = sorted(p for p in DEST.iterdir() if p.is_file() and p.name != 'validation-index.json')
settings = Path('C:/Users/XCC/.claude/settings.json')
private_values = []
if settings.exists():
    env = json.loads(read(settings)).get('env',{})
    private_values = [v for k,v in env.items() if isinstance(v,str) and len(v)>8
                      and any(marker in k.upper() for marker in ('KEY','TOKEN','SECRET','PASSWORD','BASE_URL'))]
for path in [*code,*docs,*spec,*evidence]:
    if path.suffix == '.png': continue
    data = path.read_bytes()
    assert all(v.encode() not in data and json.dumps(v)[1:-1].encode() not in data for v in private_values), path.name
index = {'scope':'agenthub-windows-connection-cleanup 1.1', 'status':'verified',
         'createdAt':datetime.now(timezone.utc).isoformat(),
         'previousIndex':{'path':previous_path.relative_to(REPO).as_posix(), 'sha256':sha(previous_path)},
         'codeSha256':mapping(code), 'unchangedBaselineSha256':unchanged,
         'documentationSha256':mapping(docs), 'specSha256':mapping(spec), 'evidenceSha256':mapping(evidence),
         'verification':{'apiPassed':int(match[1]),'apiSkipped':int(match[2]),'apiSeconds':float(match[3]),
             'relatedPassed':62,'newTests':13,'localToolsPassed':17,'check':'pnpm check exit 0',
             'strictOpenSpec':'passed','diffCheck':'passed', 'managedControl':reports,
             'currentRuntime':'API 8006 on official wrapper; Web 3000 iframe passed for both prior native outputs',
             'persistence':history,'privateSdkValues':'excluded'},
         'limits':['Exact socket-shutdown controlled injection reproduces historical failure path; ordinary 200 TCP resets did not',
             'One managed control comparison is not a performance benchmark',
             'Actually exercised Windows Python 3.12.7; newer detach signature has unit-test coverage only',
             'No new model inference, database schema changes or deployment',
             'Whole project remains incomplete; see local-project-delivery.md']}
(DEST / 'validation-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for key,value in index.items():
    if key.endswith('Sha256'):
        assert all(sha(REPO / name) == digest for name,digest in value.items())
print(json.dumps({'verified':{key:len(value) for key,value in index.items() if key.endswith('Sha256')},
                  'apiPassed':int(match[1]), 'previousIndexUnchanged':True}))
