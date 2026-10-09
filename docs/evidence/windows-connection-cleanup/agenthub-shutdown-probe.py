import asyncio, json, os, socket, struct, sys, time
from pathlib import Path

ROOT=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-shutdown-20261009')
ROOT.mkdir(exist_ok=True)
mode=sys.argv[1]
os.environ['AGENTHUB_DATABASE_URL']='sqlite:///'+(ROOT/f'{mode}.sqlite3').as_posix()
sys.path.insert(0,'X:/Git_Clone/AgentHub/apps/api')
import uvicorn
from sqlmodel import Session as DbSession,select
from app.models import Session,Workspace
from app.db import engine

async def run():
    errors=[]
    loop=asyncio.get_running_loop()
    def record_error(loop,context):
        exc=context.get('exception');tb=getattr(exc,'__traceback__',None)
        while tb and tb.tb_next: tb=tb.tb_next
        errors.append({'type':type(exc).__name__,'winerror':getattr(exc,'winerror',None),
            'callback':getattr(getattr(context.get('handle'),'_callback',None),'__qualname__',None),
            'tail':tb.tb_frame.f_code.co_name if tb else None})
        loop.default_exception_handler(context)
    loop.set_exception_handler(record_error)
    server=uvicorn.Server(uvicorn.Config('app.main:app',host='127.0.0.1',port=8011,access_log=False,timeout_graceful_shutdown=2))
    serving=asyncio.create_task(server.serve())
    while not server.started:
        if serving.done(): await serving
        await asyncio.sleep(.05)
    with DbSession(engine) as db:
        workspace=db.exec(select(Workspace)).first()
        session=Session(workspace_id=workspace.id,title='shutdown transport probe',bound_branch='fixture-only',worktree_path=str(ROOT/mode))
        db.add(session);db.commit();sid=session.id
    def burst():
        paths=['/health',f'/sessions/{sid}/events?stream=true']
        counts={path:0 for path in paths}
        for i in range(200):
            path=paths[i%len(paths)]
            client=socket.create_connection(('127.0.0.1',8011),timeout=3)
            client.sendall(f'GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n'.encode())
            data=client.recv(4096)
            assert b'200 OK' in data,data
            client.setsockopt(socket.SOL_SOCKET,socket.SO_LINGER,struct.pack('hh',1,0))
            client.close();counts[path]+=1
        return counts
    requests=await asyncio.to_thread(burst)
    await asyncio.sleep(.3)
    before={'activeCounts':[s._active_count for s in server.servers],
        'uvicornConnections':len(server.server_state.connections),'uvicornTasks':len(server.server_state.tasks)}
    start=time.perf_counter();server.should_exit=True
    await asyncio.wait_for(serving,timeout=10)
    report={'mode':mode,'requests':requests,'errors':errors,'beforeShutdown':before,
        'afterShutdown':{'activeCounts':[s._active_count for s in server.servers]},'shutdownSeconds':round(time.perf_counter()-start,3)}
    (ROOT/f'{mode}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report))

asyncio.run(run())
