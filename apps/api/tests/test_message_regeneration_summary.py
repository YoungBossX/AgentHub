import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import select

from test_group_auto_execution import runtime  # noqa: F401
from test_group_result_summary import native, settled, summaries
from app.group_summaries import execute_group_summary, prepare_group_summary, public_group_summary
from app.message_regeneration import prepare_regeneration, public_regeneration
from app.models import Message, Task, TaskRun


def test_summary_regeneration_reinterprets_evidence_without_rerunning_tasks(runtime, monkeypatch):
    db, _ = runtime; gid = settled(db); calls = native(db, gid, monkeypatch)
    first = prepare_group_summary(db, gid)
    asyncio.run(execute_group_summary(db.get_bind(), first))
    original = summaries(db)[0]; old = original.model_dump()
    before = {table.__name__: [row.model_dump() for row in db.exec(select(table)).all()] for table in (Task, TaskRun)}
    operation = str(uuid4())
    created, job, fresh = prepare_regeneration(db, original.session_id, original.id, operation)
    assert fresh and job and job.policy == first.policy and job.evidence == first.evidence
    replay, no_job, fresh = prepare_regeneration(db, original.session_id, original.id, operation)
    assert replay.id == created.id and not fresh and no_job is None
    with pytest.raises(HTTPException) as error:
        prepare_regeneration(db, original.session_id, original.id, str(uuid4()))
    assert error.value.status_code == 409
    db.rollback()
    asyncio.run(execute_group_summary(db.get_bind(), job)); db.expire_all()
    assert len(calls) == 2
    assert db.get(Message, original.id).model_dump() == old
    assert before == {table.__name__: [row.model_dump() for row in db.exec(select(table)).all()] for table in (Task, TaskRun)}
    rows = summaries(db)
    assert [public_group_summary(db, row)['current'] for row in rows] == [False, True]
    lineage, action = public_regeneration(db, rows[-1])
    assert lineage['state'] == 'completed' and lineage['sourceMessageId'] == original.id
    assert action['available'] and action['kind'] == 'summary'
