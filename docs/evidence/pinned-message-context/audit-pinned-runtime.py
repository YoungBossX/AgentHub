import hashlib, json, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).parent
phase = sys.argv[1]
db = sqlite3.connect(f"file:{(ROOT / 'runtime.sqlite3').as_posix()}?mode=ro", uri=True)
tables = {}
for table in ('session', 'message', 'task', 'taskrun'):
    rows = db.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
    tables[table] = {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}
assert not db.execute("SELECT id FROM taskrun WHERE state IN ('running', 'queued')").fetchall(), 'Active execution: do not restart'
if phase in ('before', 'before-restart'):
    with sqlite3.connect(ROOT / f'pinned-{phase}-runtime.sqlite3') as backup:
        db.backup(backup)
if phase in ('activated', 'restarted'):
    prior = 'before' if phase == 'activated' else 'before-restart'
    prior_tables = json.loads((ROOT / f'pinned-history-{prior}.json').read_text())
    if tables != prior_tables:
        with sqlite3.connect(ROOT / f'pinned-{prior}-runtime.sqlite3') as previous:
            changes = []
            for table in tables:
                columns = [row[1] for row in db.execute(f'PRAGMA table_info({table})')]
                old = {row[0]: row for row in previous.execute(f'SELECT * FROM {table}')}
                new = {row[0]: row for row in db.execute(f'SELECT * FROM {table}')}
                assert old.keys() == new.keys()
                for key in old:
                    fields = [columns[i] for i, (a, b) in enumerate(zip(old[key], new[key])) if a != b]
                    if fields:
                        changes.append({'table': table, 'id': key, 'fields': fields})
        assert changes == [{'table': 'task', 'id': 'd9e6e037-46d1-42ef-984e-a473b6bb9e2b', 'fields': ['updated_at']}]
        (ROOT / f'pinned-{phase}-metadata-change.json').write_text(json.dumps(changes, indent=2))
    else:
        assert tables == prior_tables
(ROOT / f'pinned-history-{phase}.json').write_text(json.dumps(tables, indent=2))
print(json.dumps({'phase': phase, 'tables': tables}))
