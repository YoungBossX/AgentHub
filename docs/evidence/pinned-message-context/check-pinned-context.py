import hashlib, json, sys
from pathlib import Path
from sqlmodel import create_engine, Session
from app.models import Message, Task, TaskRun
from app.context_pack import build_session_context_pack
from app.llm_planner import build_llm_planner_input

ROOT = Path(__file__).parent
phase = sys.argv[1]
proof = json.loads((ROOT / 'pinned-context-native.json').read_text(encoding='utf-8'))
engine = create_engine('sqlite:///' + (ROOT / 'runtime.sqlite3').as_posix())
with Session(engine) as db:
    run = db.get(TaskRun, proof['runId'])
    task = db.get(Task, proof['taskId'])
    request = db.get(Message, task.created_by_message_id)
    metrics = json.loads(run.metrics_json)
    canonical = metrics['canonicalContextSnapshot']
    selected = canonical['fields']['pinnedMessageContext']
    assert selected['trustLevel'] == 'conversation_reference'
    assert selected['value']['messages'][0]['id'] == proof['noteId']
    assert selected['value']['messages'][0]['senderType'] == 'agent'
    assert proof['marker'] in selected['value']['messages'][0]['contentMd']
    assert proof['noteId'] not in [m['id'] for m in canonical['fields']['recentMessages']['value']]
    digest = hashlib.sha256(run.metrics_json.encode()).hexdigest()
    task_digest = hashlib.sha256(task.plan_json.encode()).hexdigest()
    if phase != 'pinned':
        before = json.loads((ROOT / 'pinned-context-snapshot-pinned.json').read_text())
        assert digest == before['runMetricsSha256']
        assert task_digest == before['taskPlanSha256']
    coding = build_session_context_pack(db, task)
    planner = build_llm_planner_input(db, request)['canonicalSharedContext']['fields']
    assert coding['pinnedMessageContext'] == planner['pinnedMessageContext']['value']
    if phase == 'unpinned':
        assert coding['pinnedMessageContext']['messages'] == []
    else:
        assert coding['pinnedMessageContext']['messages'][0]['id'] == proof['noteId']
    artifact = {'phase': phase, 'runId': run.id, 'runMetricsSha256': digest,
                'taskPlanSha256': task_digest, 'persistedPinnedField': selected,
                'freshPinnedField': coding['pinnedMessageContext'],
                'checks': ['persisted native request contains old pin with original attribution',
                           'recent messages exclude selected pin', 'planner and coding agree',
                           'prior TaskRun metrics and plan unchanged' if phase != 'pinned' else 'captured original snapshot']}
    (ROOT / f'pinned-context-snapshot-{phase}.json').write_text(json.dumps(artifact, indent=2))
print(json.dumps({'phase': phase, 'runMetricsSha256': digest, 'freshReferences': len(coding['pinnedMessageContext']['messages'])}))
