import cProfile
import hashlib
import io
import json
import pstats
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path('X:/Git_Clone/AgentHub')
sys.path.insert(0, str(REPO / 'apps/api'))
from app.task_run_scope import capture_worktree_scope_snapshot, new_scope_control_key

base = Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007')
database = base / 'copy-literal-verified/fresh.sqlite3'
with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
    row = db.execute('SELECT worktree_path FROM taskrun WHERE id=?', ('8c1740a4-c753-4adc-9c54-736bf21fad3b',)).fetchone()
root = Path(row[0])
assert root.is_relative_to(REPO / '.worktrees')
output = base / 'scope-profile-before'
output.mkdir(exist_ok=True)
profiler = cProfile.Profile()
start = time.perf_counter()
snapshot = profiler.runcall(capture_worktree_scope_snapshot, root, control_key=new_scope_control_key())
seconds = time.perf_counter() - start
profiler.dump_stats(output / 'snapshot.prof')
stream = io.StringIO()
pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(30)
report = {'available': snapshot.available, 'reason': snapshot.reason, 'seconds': seconds, 'scopeEntryCount': len(snapshot.entries), 'protectedEntryCount': snapshot.protected_entry_count, 'root': str(root), 'sourceSha256': hashlib.sha256((REPO / 'apps/api/app/task_run_scope.py').read_bytes()).hexdigest()}
(output / 'profile.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
(output / 'top.txt').write_text(stream.getvalue(), encoding='utf-8')
print(json.dumps(report))
print(stream.getvalue())
assert snapshot.available
