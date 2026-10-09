import hashlib,json,os,sys
from pathlib import Path
from uuid import uuid4

ROOT=Path('C:/Users/XCC/AppData/Local/Temp/agenthub-regeneration-20261009')
os.environ['AGENTHUB_DATABASE_URL']='sqlite:///C:/Users/XCC/AppData/Local/Temp/agenthub-local-completion-20261007/runtime.sqlite3'
sys.path.insert(0,'X:/Git_Clone/AgentHub/apps/api')
from sqlmodel import Session as DbSession,select
from app.db import engine
from app.models import Message,Task,TaskRun
from app.message_regeneration import metadata,prepare_regeneration
from app.task_runs import ACTIVE_STATES

proof=json.loads((ROOT/'native.json').read_text(encoding='utf-8'))
sid=proof['session']['id'];phase=sys.argv[1]
digest=lambda value:hashlib.sha256(json.dumps(value,default=str,sort_keys=True,ensure_ascii=True).encode()).hexdigest()
with DbSession(engine) as db:
    assert not db.exec(select(TaskRun).where(TaskRun.state.in_(ACTIVE_STATES))).first()
    all_messages=db.exec(select(Message)).all()
    assert not any(json.loads(m.context_json).get('groupSummary',{}).get('state')=='calling' for m in all_messages), 'A summary is still calling'
    if phase=='before':
        assert not any(metadata(m).get('state')=='preparing' for m in all_messages)
        operation_id=str(uuid4())
        created,job,fresh=prepare_regeneration(db,sid,proof['originalPlan']['id'],operation_id)
        assert fresh and job is None and metadata(created)['state']=='preparing'
        report={'source':'controlled process interruption boundary: claim committed without invoking dispatch',
                'operationId':operation_id,'sessionId':sid,'sourceMessageId':proof['originalPlan']['id'],
                'rows':{}}
        for table in (Message,Task,TaskRun):
            rows=db.exec(select(table).where(table.session_id==sid)).all() if table is not TaskRun else db.exec(select(TaskRun).join(Task).where(Task.session_id==sid)).all()
            report['rows'][table.__name__]={row.id:digest(row.model_dump(exclude={'regeneration_json'} if row.id==operation_id else set())) for row in rows}
        report['sourceSha256']=hashlib.sha256((Path(proof['session']['worktreePath'])/'apps/demo/src/App.tsx').read_bytes()).hexdigest()
        (ROOT/'restart-before.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    else:
        report=json.loads((ROOT/'restart-before.json').read_text(encoding='utf-8'));operation_id=report['operationId']
        for table in (Message,Task,TaskRun):
            for row_id,expected in report['rows'][table.__name__].items():
                row=db.get(table,row_id)
                assert digest(row.model_dump(exclude={'regeneration_json'} if row.id==operation_id else set()))==expected,(table.__name__,row_id)
        row=db.get(Message,operation_id)
        assert metadata(row)['state']=='failed' and metadata(row)['errorCode']=='REGENERATION_PREPARATION_INTERRUPTED'
        assert not db.exec(select(Task).where(Task.created_by_message_id==operation_id)).first()
        assert hashlib.sha256((Path(proof['session']['worktreePath'])/'apps/demo/src/App.tsx').read_bytes()).hexdigest()==report['sourceSha256']
        (ROOT/'restart-after.json').write_text(json.dumps({**report,'passed':True,'recovered':metadata(row),'noTasksCreatedForInterruptedPreparation':True},indent=2),encoding='utf-8')
print(json.dumps({'phase':phase,'operationId':operation_id,'source':report['source']}))
