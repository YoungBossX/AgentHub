import hashlib, json, sqlite3, sys
from pathlib import Path
root = Path(__file__).parent
phase = sys.argv[1]
with sqlite3.connect(f"file:{(root / 'runtime.sqlite3').as_posix()}?mode=ro", uri=True) as db:
    tables = {}
    for table in ('session', 'message', 'task', 'taskrun', 'diff', 'artifact'):
        rows = db.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
        tables[table] = {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
    if phase == 'recheck-before':
        with sqlite3.connect(root / 'security-runtime-recheck.sqlite3') as backup:
            db.backup(backup)
    if phase == 'recheck-after':
        changes = []
        with sqlite3.connect(root / 'security-runtime-recheck.sqlite3') as before:
            for table in tables:
                columns = [row[1] for row in db.execute(f'PRAGMA table_info({table})')]
                old = {row[0]: row for row in before.execute(f'SELECT * FROM {table}')}
                new = {row[0]: row for row in db.execute(f'SELECT * FROM {table}')}
                assert old.keys() == new.keys()
                for key in old:
                    fields = [columns[i] for i, (a, b) in enumerate(zip(old[key], new[key])) if a != b]
                    if fields:
                        changes.append({'table': table, 'id': key, 'fields': fields})
        assert changes in ([], [{'table': 'task', 'id': 'd9e6e037-46d1-42ef-984e-a473b6bb9e2b', 'fields': ['updated_at']}]), changes
        (root / 'security-runtime-recheck-changes.json').write_text(json.dumps(changes, indent=2))
if phase == 'after':
    assert tables == json.loads((root / 'security-runtime-before.json').read_text())
(root / f'security-runtime-{phase}.json').write_text(json.dumps(tables, indent=2))
print(json.dumps({'phase': phase, 'tables': tables}))
