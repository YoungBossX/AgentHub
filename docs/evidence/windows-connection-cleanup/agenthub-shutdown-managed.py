"""Controlled failure probe around the real local-api entrypoint, not product routes."""
import asyncio, importlib.util, json, os, sqlite3, sys
from pathlib import Path

BASE=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-shutdown-20261009')
ROOT=Path(sys.argv[2]).resolve()
assert ROOT.is_relative_to(BASE.resolve())
ROOT.mkdir(parents=True,exist_ok=True)
if sys.argv[1]=='prepare':
    source=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3')
    for mode in ('baseline','fixed'):
        with sqlite3.connect(source) as old,sqlite3.connect(ROOT/f'{mode}.sqlite3') as new: old.backup(new)
    print('Independent database copies prepared')
    sys.exit(0)

mode=sys.argv[1]
os.environ['AGENTHUB_DATABASE_URL']='sqlite:///'+(ROOT/f'{mode}.sqlite3').as_posix()
sys.path.insert(0,'X:/Git_Clone/AgentHub/apps/api')
from app import main
if mode=='baseline': main.install_windows_connection_cleanup=lambda _:lambda:None
import uvicorn
from asyncio.proactor_events import _ProactorBasePipeTransport
from app.models import TaskRun,Message,Diff,MessageAttachment

actual=[]
class ObservedServer(uvicorn.Server):
    async def startup(self,*args,**kwargs):
        await super().startup(*args,**kwargs)
        actual.append(self)
uvicorn.Server=ObservedServer
spec=importlib.util.spec_from_file_location('local_api','X:/Git_Clone/AgentHub/scripts/local-api.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)

class ResetSocket:
    closes=0
    def fileno(self): return 123
    def shutdown(self,_):
        error=ConnectionResetError('controlled cleanup failure matching historical 10054')
        error.winerror=10054
        raise error
    def close(self): self.closes+=1

class Protocol(asyncio.Protocol):
    losses=0
    def connection_lost(self,_): self.losses+=1

async def inject():
    while not actual or not (ROOT/f'{mode}.trigger').exists(): await asyncio.sleep(.05)
    server=actual[0].servers[0]
    sock=ResetSocket();protocol=Protocol();loop=asyncio.get_running_loop()
    before=server._active_count
    connection=_ProactorBasePipeTransport(loop,sock,protocol,server=server)
    connection.close()
    await asyncio.sleep(.1)
    report={'mode':mode,'controlledInjection':True,'before':before,'after':server._active_count,
        'socketCloses':sock.closes,'protocolCallbacks':protocol.losses,'cleaned':connection._called_connection_lost}
    (ROOT/f'{mode}-fault.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

async def run():
    injection=asyncio.create_task(inject())
    try: await entry.serve('api',8011,'shutdown-acceptance')
    finally:
        injection.cancel()
        with __import__('contextlib').suppress(asyncio.CancelledError): await injection

asyncio.run(run())
