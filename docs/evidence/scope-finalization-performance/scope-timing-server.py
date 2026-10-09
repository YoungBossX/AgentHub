import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uvicorn

repo = Path('X:/Git_Clone/AgentHub')
sys.path.insert(0, str(repo / 'apps/api'))
output = Path(sys.argv[1])
import app.task_runs as task_runs
capture = task_runs.capture_worktree_scope_snapshot
def measured_capture(*args, **kwargs):
    start = time.perf_counter()
    result = capture(*args, **kwargs)
    with (output / 'snapshots.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'root': str(args[0]), 'seconds': time.perf_counter()-start, 'available': result.available, 'entries': len(result.entries), 'protected': result.protected_entry_count})+'\n')
    return result
task_runs.capture_worktree_scope_snapshot = measured_capture
(output/'executed-source.json').write_text(json.dumps({name: hashlib.sha256((repo/name).read_bytes()).hexdigest() for name in ['apps/api/app/task_run_scope.py','apps/api/app/task_runs.py','apps/api/app/run_engine.py','apps/api/app/scripted_mock.py']}, indent=2), encoding='utf-8')
server = uvicorn.Server(uvicorn.Config('app.main:app', host='127.0.0.1', port=8007))
async def run():
    async def watch():
        while not (output/'stop').exists():
            await asyncio.sleep(.2)
        server.should_exit=True
    watcher=asyncio.create_task(watch())
    try:
        await server.serve()
    finally:
        watcher.cancel()
asyncio.run(run())
