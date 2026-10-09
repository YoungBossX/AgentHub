import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('X:/Git_Clone/AgentHub')
ROOT = Path(__file__).parent
DEST = REPO / 'docs/evidence/pinned-message-context'
DEST.mkdir(parents=True, exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mapping(paths):
    return {str(path.relative_to(REPO)).replace('\\', '/'): sha(path) for path in paths}

logs = {
    'reproduction.log': ROOT.parent / 'agenthub-pinned-context-before-20261008.log',
    'related-final.log': ROOT.parent / 'agenthub-pin-related-final-20261008.log',
    'full-final.log': ROOT.parent / 'agenthub-pin-full-final-20261008.log',
    'check-final.log': ROOT.parent / 'agenthub-pin-check-final-20261008.log',
    'full-initial-failure.log': ROOT.parent / 'agenthub-pin-full-20261008.log',
}
# PowerShell redirection may produce UTF-16 or UTF-8 depending on its version.
raw = logs['full-final.log'].read_bytes()
report = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
assert '1780 passed, 1 skipped' in report and 'FAILED ' not in report
for target, source in logs.items():
    shutil.copyfile(source, DEST / target)
names = [
    'pinned-context-session.json', 'pinned-context-native.json',
    'pinned-context-snapshot-pinned.json', 'pinned-context-snapshot-unpinned.json',
    'pinned-context-snapshot-repinned.json', 'pinned-context-snapshot-restarted.json',
    'pinned-context-unpin.json', 'pinned-context-repin.json',
    'pinned-context-preview-before-restart.json', 'pinned-context-preview-restarted.json',
    'pinned-context-ui.png', 'pinned-context-completed.png',
    'pinned-context-preview-restarted.png',
    'pinned-history-before-restart.json', 'pinned-history-restarted.json',
    'pinned-restarted-metadata-change.json',
    'pinned-planner-rejected-session.json', 'pinned-planner-rejected.log',
    'accept-pinned-context.mjs', 'unpin-context-ui.mjs', 'preview-pinned-context.mjs',
    'check-pinned-context.py', 'audit-pinned-runtime.py', 'freeze-pinned-context.py',
]
for name in names:
    shutil.copyfile(ROOT / name, DEST / name)

code = [REPO / path for path in (
    '.gitignore',
    'apps/api/app/pinned_context.py', 'apps/api/app/canonical_context.py',
    'apps/api/app/context_pack.py', 'apps/api/app/llm_planner.py',
    'apps/api/tests/test_pinned_message_context.py',
)]
docs = [REPO / 'docs' / name for name in (
    'pinned-message-context-review.md', 'change-log.md', 'project-state.md',
    'local-usage.md', 'local-project-delivery.md',
)]
spec = sorted((REPO / 'openspec/changes/agenthub-pinned-message-context').rglob('*.md'))
previous = json.loads((REPO / 'docs/evidence/scope-finalization-performance/validation-index.json').read_text(encoding='utf-8'))
unchanged = {**previous['codeSha256'], **previous['unchangedBaselineSha256']}
unchanged.pop('.gitignore', None)
for name, digest in unchanged.items():
    assert sha(REPO / name) == digest, f'Baseline changed: {name}'

evidence = sorted(path for path in DEST.iterdir() if path.is_file() and path.name != 'validation-index.json')
private_settings = Path('C:/Users/XCC/.claude/settings.json')
private_values = []
if private_settings.exists():
    env = json.loads(private_settings.read_text(encoding='utf-8')).get('env', {})
    private_values = [value for key, value in env.items() if isinstance(value, str) and len(value) > 8
                      and any(marker in key.upper() for marker in ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'BASE_URL'))]
for path in [*evidence, *code, *docs, *spec]:
    if path.suffix != '.png':
        data = path.read_bytes()
        for value in private_values:
            assert value.encode() not in data and json.dumps(value)[1:-1].encode() not in data, f'Private value in {path.name}'
index = {
    'status': 'verified', 'scope': 'agenthub-pinned-message-context 1.1',
    'createdAt': datetime.now(timezone.utc).isoformat(),
    'codeSha256': mapping(code), 'unchangedBaselineSha256': unchanged,
    'documentationSha256': mapping(docs), 'specSha256': mapping(spec), 'evidenceSha256': mapping(evidence),
    'verification': {'related': '56 passed', 'fullApi': '1780 passed, 1 POSIX-only skipped',
                     'static': 'pnpm check exit 0', 'native': 'real Claude CLI planner and Claude code; old pinned reference; actual Vite DOM',
                     'restart': 'pin survives; previous metrics and plan unchanged; one old task updated_at refreshed',
                     'privateSdkValues': 'excluded'},
    'boundaries': ['Local single-user only; no production deployment',
                   'Bounded reference selection is not an unlimited conversation memory',
                   'Full project PDF gaps remain listed in local-project-delivery.md'],
}
(DEST / 'validation-index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
for section in ('codeSha256', 'unchangedBaselineSha256', 'documentationSha256', 'specSha256', 'evidenceSha256'):
    assert all(sha(REPO / name) == digest for name, digest in index[section].items())
print(json.dumps({'verified': {key: len(index[key]) for key in index if key.endswith('Sha256')}}))
