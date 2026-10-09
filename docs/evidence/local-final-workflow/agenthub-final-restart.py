import hashlib, json, sqlite3, sys
from pathlib import Path
root = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-final-local-20261009')
database = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
native = json.loads((root/'native.json').read_text(encoding='utf-8'))
recovery = json.loads((root/'recovery.json').read_text(encoding='utf-8'))
sessions = [*native['sessions'].values(), recovery['session']]
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=lambda v:hashlib.sha256(v).hexdigest() if isinstance(v,bytes) else str(v)).encode()).hexdigest()
with sqlite3.connect(database) as db:
    db.row_factory=sqlite3.Row
    result={}
    for session in sessions:
        sid=session['id']
        rows={}
        for table,condition in {
            'session':'id=?','message':'session_id=?','task':'session_id=?','messageattachment':'session_id=?',
            'taskrun':'task_id in (select id from task where session_id=?)',
            'diff':'artifact_id in (select id from artifact where task_run_id in (select id from taskrun where task_id in (select id from task where session_id=?)))',
            'artifact':"artifact_type not in ('preview','deployment') and task_run_id in (select id from taskrun where task_id in (select id from task where session_id=?))",
        }.items():
            rows[table]={row['id']:digest(dict(row)) for row in db.execute('select * from '+table+' where '+condition,(sid,))}
        rows['sourceSha256']=hashlib.sha256((Path(session['worktreePath'])/'apps/demo/src/App.tsx').read_bytes()).hexdigest()
        result[sid]=rows
    name=sys.argv[1]
    if name=='before':
        assert not (root/'restart-before.json').exists()
        (root/'restart-before.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    else:
        assert json.loads((root/'restart-before.json').read_text(encoding='utf-8'))==result,'Frozen runtime history changed on restart'
        (root/'restart-after.json').write_text(json.dumps({'passed':True,'hashes':result},indent=2),encoding='utf-8')
    print(json.dumps({'phase':name,'counts':{sid:{k:len(v) for k,v in rows.items() if isinstance(v,dict)} for sid,rows in result.items()}}))
