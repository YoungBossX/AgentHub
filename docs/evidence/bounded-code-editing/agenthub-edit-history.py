import hashlib, json, sqlite3, sys
from pathlib import Path
ROOT = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-edit-20261009')
ROOT.mkdir(exist_ok=True)
DB = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
tables = ['workspace','session','message','task','taskrun','diff','review','messageattachment','agentprofiledraft','agentruntimeconfig']
def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=lambda x: hashlib.sha256(x).hexdigest() if isinstance(x,bytes) else str(x)).encode()).hexdigest()
with sqlite3.connect(DB) as db:
    db.row_factory = sqlite3.Row
    if sys.argv[1] == 'before':
        assert not (ROOT/'before.sqlite3').exists()
        with sqlite3.connect(ROOT/'before.sqlite3') as backup: db.backup(backup)
        rows = {table: {r['id']: digest(dict(r)) for r in db.execute('select * from '+table)} for table in tables}
        (ROOT/'history-before.json').write_text(json.dumps(rows,indent=2))
        print({table:len(value) for table,value in rows.items()})
    else:
        before = json.loads((ROOT/'history-before.json').read_text())
        report = {'passed':True, 'preserved':{}, 'timestampChanges':[]}
        with sqlite3.connect(ROOT/'before.sqlite3') as old:
            old.row_factory = sqlite3.Row
            for table, records in before.items():
                for rid, expected in records.items():
                    row = dict(db.execute('select * from '+table+' where id=?',(rid,)).fetchone())
                    if digest(row) != expected:
                        original = dict(old.execute('select * from '+table+' where id=?',(rid,)).fetchone())
                        fields = [k for k in original if original[k] != row[k]]
                        assert table == 'task' and fields == ['updated_at'], (table,rid,fields)
                        report['timestampChanges'].append({'table':table,'id':rid,'fields':fields})
                report['preserved'][table] = len(records)
        (ROOT/('history-'+sys.argv[1]+'.json')).write_text(json.dumps(report,indent=2))
        print(json.dumps(report))
