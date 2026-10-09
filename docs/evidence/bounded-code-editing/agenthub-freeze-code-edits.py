import hashlib, json, os, shutil
from pathlib import Path
repo=Path('X:/Git_Clone/AgentHub').resolve()
temp=Path('C:/Users/XCC/AppData/Local/Temp')
source=temp/'agenthub-edit-20261009'
out=repo/'docs/evidence/bounded-code-editing'
assert out.resolve().is_relative_to(repo)
out.mkdir(parents=True,exist_ok=True)
for name in ['native.json','native-first-failure.json','native-cli-failure.json','argv-probe.json',
             'history-before.json','history-before-restart.json','history-after-restart.json',
             'restart-before.json','restart-after.json','restart-browser.json',
             'applied-source.txt','continued-source.txt','proposed-light.png','proposed-dark.png',
             'proposed-390-dark.png','proposed-320-dark.png','applied-preview.png','continued-preview.png','restart-workbench.png']:
    shutil.copyfile(source/name,out/name)
scripts=['agenthub-edit-native.mjs','agenthub-edit-restart-browser.mjs','agenthub-edit-history.py',
         'agenthub-edit-restart.py','agenthub-edit-argv-probe.py','agenthub-freeze-code-edits.py']
for name in scripts: shutil.copyfile(temp/name,out/name)
logs={
 'patch-initial-failure':'agenthub-edit-patch-1.log', 'service-fixture-initial-failure':'agenthub-edit-service-1.log',
 'web-fixture-initial-failure':'agenthub-edit-web-new-1.log', 'new-api':'agenthub-edit-new-3.log',
 'execution-baseline':'agenthub-edit-continuation-1.log','related-api':'agenthub-edit-related-1.log',
 'full-api-stage':'agenthub-edit-full-1.log','late-api':'agenthub-edit-late-1.log','windows-stream':'agenthub-edit-ads-1.log',
 'web-final':'agenthub-edit-web-full-final.log','check-final':'agenthub-edit-check-final.log',
 'build-final':'agenthub-edit-build-final.log','openspec':'agenthub-edit-openspec.log','diff-check':'agenthub-edit-diff-check.log',
 'native-first-failure':'agenthub-edit-native.log','native-cli-failure':'agenthub-edit-native-resume.log',
 'native-continuation':'agenthub-edit-native-continuation.log','restart-browser':'agenthub-edit-restart-browser.log',
}
for dest,name in logs.items(): shutil.copyfile(temp/name,out/(dest+'.txt'))
assert '1942 passed, 1 skipped' in (out/'full-api-stage.txt').read_text(encoding='utf-8')
assert '132 passed' in (out/'late-api.txt').read_text(encoding='utf-8')
assert '263 passed' in (out/'web-final.txt').read_text(encoding='utf-8')
assert json.loads((out/'native.json').read_text(encoding='utf-8'))['passed']
assert json.loads((out/'restart-after.json').read_text(encoding='utf-8'))['passed']
assert json.loads((out/'restart-browser.json').read_text(encoding='utf-8'))['passed']
code=[
 'AGENTS.md','.gitignore','apps/api/app/user_patch.py','apps/api/app/user_edit_files.py',
 'apps/api/app/user_edit_fences.py','apps/api/app/user_code_edits.py','apps/api/app/routes/user_code_edits.py',
 'apps/api/app/main.py','apps/api/app/task_runs.py','apps/api/app/dag_integration.py','apps/api/app/diffs.py',
 'apps/api/app/previews.py','apps/api/app/deployments.py','apps/api/app/artifact_workbench.py','apps/api/app/planner_providers.py',
 'apps/api/tests/test_user_patch.py','apps/api/tests/test_user_code_edits.py','apps/api/tests/test_planner_providers.py',
 'apps/web/src/lib/api.ts','apps/web/src/components/user-code-editor.tsx','apps/web/src/components/user-code-edit-context.tsx',
 'apps/web/src/components/local-code-editor.tsx','apps/web/src/components/user-code-editor.test.tsx',
 'apps/web/src/components/diff-card.tsx','apps/web/src/components/preview-card.tsx','apps/web/src/components/workspace-shell.tsx',
]
docs=['docs/bounded-code-editing-review.md','docs/change-log.md','docs/project-state.md','docs/local-project-delivery.md','docs/local-usage.md']
specs=[str(p.relative_to(repo)).replace('\\','/') for p in (repo/'openspec/changes/agenthub-bounded-code-editing').rglob('*.md')]
hashfile=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
evidence={str(p.relative_to(repo)).replace('\\','/'):hashfile(p) for p in out.iterdir() if p.name!='validation-index.json'}
manifest={'task':'agenthub-bounded-code-editing 1.1','status':'verified_local_uncommitted',
 'verification':{'apiFullStage':{'passed':1942,'skipped':1},'lateRelatedApi':132,'namedStream':1,'web':263,
 'boundary':'The API full stage started before the final stdin/workbench changes; those were verified separately, not represented as a final full-suite rerun.'},
 'code':{name:hashfile(repo/name) for name in code},'docs':{name:hashfile(repo/name) for name in docs},
 'specs':{name:hashfile(repo/name) for name in specs},'evidence':evidence}
for path in out.iterdir():
    if path.suffix in {'.json','.txt','.py','.mjs'}:
        data=path.read_text(encoding='utf-8')
        for key,value in os.environ.items():
            if any(marker in key.upper() for marker in ['TOKEN','SECRET','PASSWORD','API_KEY']) and len(value)>=12:
                assert value not in data, f'Private environment value found in {path.name}, key={key}'
(out/'validation-index.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
for group in ['code','docs','specs','evidence']:
    for name,expected in manifest[group].items(): assert hashfile(repo/name)==expected,name
print(json.dumps({'passed':True,'counts':{g:len(manifest[g]) for g in ['code','docs','specs','evidence']}}))
