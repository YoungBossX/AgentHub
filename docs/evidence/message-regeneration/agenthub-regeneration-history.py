import hashlib, json, sqlite3, sys
from pathlib import Path

ROOT = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-regeneration-20261009')
ROOT.mkdir(exist_ok=True)
DB = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
phase = sys.argv[1]
def digest(value): return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
with sqlite3.connect(DB) as db:
    db.row_factory = sqlite3.Row
    active = list(db.execute("SELECT id FROM taskrun WHERE state NOT IN ('completed','failed','interrupted','cancelled')"))
    assert not active, 'There are active runs; do not restart'
    if phase == 'before':
        with sqlite3.connect(ROOT / 'before.sqlite3') as backup: db.backup(backup)
        report = {}
        for table in ('session','message','task','taskrun','diff','messageattachment'):
            rows = [dict(row) for row in db.execute(f'SELECT * FROM {table}')]
            columns = [key for key in rows[0] if key != 'regeneration_json'] if rows else []
            report[table] = {'columns':columns, 'rows':{row['id']:digest({k:hashlib.sha256(row[k]).hexdigest() if isinstance(row[k],bytes) else row[k] for k in columns}) for row in rows}}
        (ROOT / 'history-before.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    else:
        report = json.loads((ROOT / 'history-before.json').read_text(encoding='utf-8'))
        timestamp_changes = []
        baseline = sqlite3.connect(ROOT / 'before.sqlite3'); baseline.row_factory = sqlite3.Row
        for table, before in report.items():
            for key, expected in before['rows'].items():
                row = dict(db.execute(f'SELECT * FROM {table} WHERE id=?',(key,)).fetchone())
                actual = digest({k:hashlib.sha256(row[k]).hexdigest() if isinstance(row[k],bytes) else row[k] for k in before['columns']})
                if actual != expected:
                    old = dict(baseline.execute(f'SELECT * FROM {table} WHERE id=?',(key,)).fetchone())
                    changes = [k for k in before['columns'] if row[k] != old[k]]
                    assert table == 'task' and changes == ['updated_at'], (table,key,changes)
                    timestamp_changes.append({'taskId':key,'before':old['updated_at'],'after':row['updated_at'],'unchangedOtherFields':True})
        baseline.close()
        (ROOT / f'history-{phase}.json').write_text(json.dumps({'phase':phase,'preserved':{t:len(v['rows']) for t,v in report.items()},'messageAddedColumnIgnored':'regeneration_json','existingSchedulerTimestampChanges':timestamp_changes},indent=2),encoding='utf-8')
print(json.dumps({'phase':phase, 'rows':{table:len(value['rows']) for table,value in report.items()}}))
