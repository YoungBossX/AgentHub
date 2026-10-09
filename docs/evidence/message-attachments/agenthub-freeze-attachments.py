"""Freeze this local acceptance run; not a portable replay or a new inference run."""
import base64
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('X:/Git_Clone/AgentHub')
TEMP = Path('C:/Users/XCC/AppData/Local/Temp')
ROOT = TEMP / 'agenthub-local-completion-20261007'
DEST = REPO / 'docs/evidence/message-attachments'

def read(path):
    raw = path.read_bytes()
    return raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mapping(paths):
    return {path.relative_to(REPO).as_posix(): sha(path) for path in paths}

report = read(TEMP / 'agenthub-attach-full-verified.log')
match = re.search(r'(\d+) passed, (\d+) skipped, .* in ([0-9.]+)s', report)
assert match and 'FAILED ' not in report and int(match[1]) >= 1814
assert '242 passed' in read(TEMP / 'agenthub-attach-web-verified.log')
assert 'Compiled successfully' in read(TEMP / 'agenthub-attach-build-verified.log')
assert 'is valid' in read(TEMP / 'agenthub-attach-openspec.log')
assert not read(TEMP / 'agenthub-attach-diff-check.log').strip()
assert '- [x] 1.1' in read(REPO / 'openspec/changes/agenthub-message-attachments/tasks.md')
DEST.mkdir(parents=True, exist_ok=True)

logs = {
    'api-full.txt': 'agenthub-attach-full-verified.log',
    'api-finalizer-setup-timeout.txt': 'agenthub-attach-full-final.log',
    'api-finalizer-isolated.txt': 'agenthub-attachment-fence-repro.log',
    'api-related.txt': 'agenthub-attach-focused-5.log',
    'web-full.txt': 'agenthub-attach-web-verified.log',
    'check.txt': 'agenthub-attach-check-verified.log',
    'build.txt': 'agenthub-attach-build-verified.log',
    'openspec.txt': 'agenthub-attach-openspec.log',
    'diff-check.txt': 'agenthub-attach-diff-check.log',
    'runtime-exit-recovery.txt': 'agenthub-attachment-restart-recovery.log',
    'local-tools.txt': 'agenthub-attach-local-tools.log',
    'local-doctor.txt': 'agenthub-attach-local-doctor.log',
}
for name, source in logs.items():
    (DEST / name).write_text(read(TEMP / source), encoding='utf-8')

files = [
    'attachment-reference.txt', 'attachment-reference.png',
    'attachment-codex-native.json', 'attachment-claude-native.json',
    'attachment-persistence-before-restart.json', 'attachment-persistence-after-restart.json',
    'attachment-preview-before-restart.json', 'attachment-preview-after-restart.json',
    'attachment-ui.json', 'attachment-edge-cases.json',
    'attachment-ui-1440-light.png', 'attachment-ui-390-dark.png', 'attachment-ui-320-light.png',
    'attachment-provider-limit-ui.png',
    'attachment-codex-preview-after-restart.png', 'attachment-claude-preview-after-restart.png',
]
for name in files:
    shutil.copyfile(ROOT / name, DEST / name)
helpers = ['agenthub-attachment-browser.mjs', 'agenthub-attachment-ui.mjs',
    'agenthub-attachment-edge-cases.mjs', 'agenthub-attachment-preview.mjs',
    'agenthub-attachment-persistence.py', 'agenthub-freeze-attachments.py']
for name in helpers:
    shutil.copyfile(TEMP / name, DEST / name)

outputs = []
with sqlite3.connect(ROOT / 'runtime.sqlite3') as db:
    db.row_factory = sqlite3.Row
    for mode in ('codex', 'claude'):
        proof = json.loads(read(ROOT / f'attachment-{mode}-native.json'))
        run = db.execute('select * from taskrun where id=?', (proof['runId'],)).fetchone()
        message = db.execute('select content_md from message where id=?', (proof['messageId'],)).fetchone()[0]
        assert all(value not in message for value in ('Aurora Workshop 617', 'Cedar Beacon 842'))
        assert run['state'] == 'completed'
        app = Path(run['worktree_path']) / 'apps/demo/src/App.tsx'
        assert sha(app) == proof['appSha256']
        diffs = [dict(row) for row in db.execute('select diff.id,diff.patch_text from diff join artifact on artifact.id=diff.artifact_id where artifact.task_run_id=?', (proof['runId'],))]
        assert any('Aurora Workshop 617' in row['patch_text'] for row in diffs)
        if mode == 'codex': assert any('Cedar Beacon 842' in row['patch_text'] for row in diffs)
        events = [row[0] for row in db.execute('select payload_json from taskrunevent where task_run_id=?', (proof['runId'],))]
        for aid in proof['attachmentIds']:
            row = db.execute('select * from messageattachment where id=?', (aid,)).fetchone()
            assert hashlib.sha256(row['payload']).hexdigest() == row['sha256']
            if row['image_payload']:
                encoded = base64.b64encode(row['image_payload']).decode()
                assert encoded not in run['metrics_json'] and all(encoded not in event for event in events)
        outputs.append({'mode':mode, 'runId':proof['runId'], 'message':message,
            'state':run['state'], 'appSha256':sha(app), 'source':read(app), 'diffs':diffs,
            'eventCount':len(events), 'binaryExcludedFromMetricsAndEvents':True})
(DEST / 'native-output.json').write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding='utf-8')

code_names = ['.gitignore', 'AGENTS.md', 'apps/api/requirements.txt', 'scripts/local-dev.mjs',
    *['apps/api/app/' + name + '.py' for name in (
        'models','schemas','main','attachments','attachment_parser','attachment_context',
        'attachment_inputs','process_input','canonical_context','context_pack','llm_planner',
        'planner_contracts','planner_providers','adapters','codex_adapter','claude_code_adapter',
        'scripted_mock','guardrails','run_engine')],
    'apps/api/app/routes/attachments.py','apps/api/app/routes/messages.py',
    *['apps/api/tests/' + name + '.py' for name in ('test_message_attachments','test_attachment_transports','test_models','test_task_runs')],
    'apps/web/src/lib/api.ts',
    *['apps/web/src/components/' + name for name in ('use-message-attachments.ts','message-attachments.tsx',
        'message-attachments.test.tsx','message-composer.tsx','workspace-shell.tsx','chat-thread.tsx','session-overview.tsx')]]
code = [REPO / name for name in code_names]
docs = [REPO / 'docs' / name for name in ('message-attachments-review.md','project-state.md','change-log.md','local-usage.md','local-project-delivery.md')]
spec = sorted((REPO / 'openspec/changes/agenthub-message-attachments').rglob('*.md'))
previous = json.loads(read(REPO / 'docs/evidence/local-dependency-security/validation-index.json'))
baseline = {**previous['codeSha256'], **previous['unchangedBackendSha256']}
unchanged = {name:digest for name,digest in baseline.items() if name not in code_names}
assert all(sha(REPO / name) == digest for name,digest in unchanged.items()), 'Unexpected baseline change'
evidence = sorted(path for path in DEST.iterdir() if path.is_file() and path.name != 'validation-index.json')
settings = Path('C:/Users/XCC/.claude/settings.json')
private_values = []
if settings.exists():
    env = json.loads(read(settings)).get('env', {})
    private_values = [value for key,value in env.items() if isinstance(value,str) and len(value)>8
        and any(marker in key.upper() for marker in ('KEY','TOKEN','SECRET','PASSWORD','BASE_URL'))]
for path in [*evidence,*code,*docs,*spec]:
    if path.suffix != '.png':
        data = path.read_bytes()
        assert all(value.encode() not in data and json.dumps(value)[1:-1].encode() not in data for value in private_values), f'Private value found in {path.name}'
index = {'scope':'agenthub-message-attachments 1.1','status':'verified_with_provider_capability_and_exit_limit',
    'createdAt':datetime.now(timezone.utc).isoformat(),
    'codeSha256':mapping(code),'unchangedBaselineSha256':unchanged,'documentationSha256':mapping(docs),
    'specSha256':mapping(spec),'evidenceSha256':mapping(evidence),
    'verification':{'apiPassed':int(match[1]),'apiSkipped':int(match[2]),'apiSeconds':float(match[3]),
        'webPassed':242,'localToolsPassed':17,'static':'pnpm check exit 0','build':'Next 16.3.8 build exit 0',
        'browser':'Edge actual upload, history, 6 viewport/theme cases, delayed Session response, no_text PDF, actionable native image failure',
        'native':'Direct Codex used actual text+image; actual Claude planner+writer used text',
        'persistence':'2 run metrics and attachment hashes unchanged; 91 old messages,35 diffs,44 TaskRuns unchanged',
        'restart':'owned temporary runtime required forced process-tree recovery; fresh runtime and 2 Vite/iframe results passed',
        'privateSdkValues':'excluded'},
    'limits':['Current configured Claude model rejects image input; failure is explicit',
        'HTTP image wire-format tests do not prove remote model inference',
        'No OCR, Office/archive/executable inputs or arbitrary host file access',
        'Local single-user, no production runtime or deployment acceptance',
        'Full project remains incomplete; see local-project-delivery.md']}
(DEST / 'validation-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for key,value in index.items():
    if key.endswith('Sha256'): assert all(sha(REPO / name) == digest for name,digest in value.items())
print(json.dumps({'verified':{key:len(value) for key,value in index.items() if key.endswith('Sha256')},'apiPassed':int(match[1])}))
