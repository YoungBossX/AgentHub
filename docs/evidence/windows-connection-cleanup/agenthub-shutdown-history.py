import hashlib,json,sqlite3,sys
from pathlib import Path

ROOT=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-shutdown-20261009')
DB=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
phase=sys.argv[1]
if len(sys.argv)>2: DB=Path(sys.argv[2])
report={}
with sqlite3.connect(DB) as db:
    db.row_factory=sqlite3.Row
    active=[dict(row) for row in db.execute("select id,state from taskrun where state not in ('completed','failed','interrupted','cancelled')")]
    assert not active,active
    for table in ('session','message','taskrun','diff','messageattachment'):
        rows=[]
        for row in db.execute(f'select * from {table} order by id'):
            value={key:hashlib.sha256(v).hexdigest() if isinstance(v,bytes) else v for key,v in dict(row).items()}
            rows.append(value)
        report[table]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,ensure_ascii=True,sort_keys=True).encode()).hexdigest()}
if phase!='before':
    before=json.loads((ROOT/'history-before.json').read_text(encoding='utf-8'))
    assert before==report,(before,report)
(ROOT/f'history-{phase}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
