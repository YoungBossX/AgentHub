import hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path

REPO=Path('X:/Git_Clone/AgentHub')
ROOT=Path(__file__).parent
DEST=REPO/'docs/evidence/chat-markdown-rendering'
DEST.mkdir(parents=True,exist_ok=True)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def hashes(paths): return {str(path.relative_to(REPO)).replace('\\','/'):sha(path) for path in paths}
def log_text(path):
 data=path.read_bytes()
 return data.decode('utf-16' if data.startswith(b'\xff\xfe') else 'utf-8-sig')
logs={
 'web-full.log':'agenthub-chat-markdown-web-full.log',
 'web-related.log':'agenthub-chat-markdown-tests2.log',
 'web-check.log':'agenthub-chat-markdown-check2.log',
 'root-check.log':'agenthub-chat-markdown-check-final.log',
 'production-build.log':'agenthub-chat-markdown-build.log',
 'production-audit.json':'agenthub-chat-markdown-audit.json',
 'baseline-production-audit.json':'agenthub-chat-markdown-baseline-audit.json',
}
assert '233 passed' in log_text(ROOT.parent/logs['web-full.log'])
assert 'Compiled successfully' in log_text(ROOT.parent/logs['production-build.log'])
for target,source in logs.items(): shutil.copyfile(ROOT.parent/source,DEST/target)
for name in ['chat-markdown-session.json','chat-markdown-browser.json','chat-markdown-dependency-comparison.json',
             'chat-markdown-light.png','chat-markdown-dark.png','chat-markdown-narrow.png','chat-markdown-image.png',
             'accept-chat-markdown.mjs','freeze-chat-markdown.py']:
 shutil.copyfile(ROOT/name,DEST/name)
code=[REPO/path for path in ['.gitignore','apps/web/package.json','pnpm-lock.yaml',
 'apps/web/src/components/chat-markdown.tsx','apps/web/src/components/chat-markdown.module.css',
 'apps/web/src/components/copy-text-button.tsx','apps/web/src/components/chat-markdown.test.tsx',
 'apps/web/src/components/chat-thread.tsx','apps/web/src/components/chat-thread.test.tsx']]
docs=[REPO/'docs'/name for name in ['chat-markdown-rendering-review.md','change-log.md','project-state.md','local-project-delivery.md','local-usage.md']]
spec=sorted((REPO/'openspec/changes/agenthub-chat-markdown-rendering').rglob('*.md'))
prior=json.loads((REPO/'docs/evidence/pinned-message-context/validation-index.json').read_text(encoding='utf-8'))
backend={name:digest for name,digest in {**prior['codeSha256'],**prior['unchangedBaselineSha256']}.items() if name.startswith('apps/api/')}
assert all(sha(REPO/name)==digest for name,digest in backend.items())
files=sorted(path for path in DEST.iterdir() if path.is_file() and path.name!='validation-index.json')
index={'status':'verified_with_existing_dependency_advisories','scope':'agenthub-chat-markdown-rendering 1.1',
 'createdAt':datetime.now(timezone.utc).isoformat(),'codeSha256':hashes(code),'unchangedBackendSha256':backend,
 'documentationSha256':hashes(docs),'specSha256':hashes(spec),'evidenceSha256':hashes(files),
 'verification':{'webTests':'233 passed','relatedTests':'19 passed','webCheck':'ESLint and TypeScript exit 0',
 'productionBuild':'Next.js build exit 0','browser':'persisted API samples; light/dark, 1440/390/320px, clipboard, inert HTML/URLs, opt-in images, quote/pin/reload',
 'audit':'12 existing advisories; original lockfile has identical advisory IDs; no new advisories'},
 'boundaries':['Presentation samples are not real model outputs','Windows clipboard read uses CRLF; only newline normalization applied',
 'Dependency safety update is the next focused task; audit is not clean','No binary file attachment or model vision claim']}
(DEST/'validation-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for section in ['codeSha256','unchangedBackendSha256','documentationSha256','specSha256','evidenceSha256']:
 assert all(sha(REPO/name)==digest for name,digest in index[section].items())
print(json.dumps({'verifiedHashes':{key:len(value) for key,value in index.items() if key.endswith('Sha256')},'existingAdvisories':12}))
