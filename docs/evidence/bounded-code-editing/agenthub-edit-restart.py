import hashlib, json, sqlite3, sys
from pathlib import Path
ROOT=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-edit-20261009')
DB=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
report=json.loads((ROOT/'native.json').read_text(encoding='utf-8'))
assert report['passed']
def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
with sqlite3.connect(DB) as db:
    db.row_factory=sqlite3.Row
    sid=report['session']['id']
    rows={}
    for table, query in {
        'session':'id=?', 'message':'session_id=?', 'task':'session_id=?',
        'taskrun':'task_id in (select id from task where session_id=?)',
        'artifact':"artifact_type in ('diff','review','user_code_edit') and task_run_id in (select id from taskrun where task_id in (select id from task where session_id=?))",
        'artifactversion':"artifact_id in (select id from artifact where artifact_type in ('diff','review','user_code_edit') and task_run_id in (select id from taskrun where task_id in (select id from task where session_id=?)))",
        'diff':'artifact_id in (select id from artifact where task_run_id in (select id from taskrun where task_id in (select id from task where session_id=?)))',
    }.items():
        rows[table]={row['id']:digest(dict(row)) for row in db.execute('select * from '+table+' where '+query,(sid,))}
    source=Path(report['session']['worktreePath'])/'apps/demo/src/App.tsx'
    rows['sourceSha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    preview=dict(db.execute('select * from artifact where id=?',(report['preview']['artifactId'],)).fetchone())
    assert json.loads(preview['meta_json'])['providerEvidence']['actor']=='user'
    assert json.loads(preview['meta_json'])['providerEvidence']['userEditId']==report['operation']['id']
    before=ROOT/'restart-before.json'
    if sys.argv[1]=='before': before.write_text(json.dumps(rows,indent=2))
    else:
        assert json.loads(before.read_text())==rows, 'Persisted user/Agent evidence changed across restart'
        (ROOT/'restart-after.json').write_text(json.dumps({'passed':True,'hashes':rows},indent=2))
    print(json.dumps({'phase':sys.argv[1],'sourceSha256':rows['sourceSha256'],'counts':{t:len(v) for t,v in rows.items() if isinstance(v,dict)}}))
