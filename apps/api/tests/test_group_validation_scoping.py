import json

import pytest
from sqlmodel import select

from app.models import Task
from app.planning import MentionParseError
from test_group_planning import db, native_provider, plan


def test_group_level_commands_apply_only_to_their_registered_target(db, monkeypatch):
    def expectations(value):
        value["planDraft"]["validationExpectations"] = ["pnpm demo:api:test", "pnpm build", "Keep the contacts contract compatible"]
    native_provider(db, monkeypatch, mutate=expectations)
    tasks = plan(db, "@backend @frontend @qa update the demo app contacts UI and API")
    assert len(tasks) == 4
    for task in tasks:
        item = json.loads(task.plan_json)
        expected = "pnpm demo:api:test" if item["targetId"] == "demo-backend" else "pnpm build"
        other = "pnpm build" if item["targetId"] == "demo-backend" else "pnpm demo:api:test"
        assert expected in item["validationExpectations"]
        assert other not in item["validationExpectations"]
        assert "Keep the contacts contract compatible" in item["validationExpectations"]
        assert "pnpm build" in item["groupValidationExpectations"]


@pytest.mark.parametrize("where", ["global_unknown", "task_wrong_target"])
def test_unknown_global_or_wrong_task_commands_still_reject_atomically(db, monkeypatch, where):
    def expectations(value):
        if where == "global_unknown": value["planDraft"]["validationExpectations"] = ["pnpm install"]
        else: value["planDraft"]["tasks"][0]["validationExpectations"] = ["pnpm build"]
    native_provider(db, monkeypatch, mutate=expectations)
    with pytest.raises(MentionParseError, match="unsupported validation command"):
        plan(db, "@backend @frontend @qa update the demo app contacts UI and API")
    assert db.exec(select(Task)).all() == []


def test_global_command_requires_a_selected_target_that_supports_it(db, monkeypatch):
    def expectations(value):
        value["planDraft"]["validationExpectations"] = ["pnpm build"]
    native_provider(db, monkeypatch, mutate=expectations)
    with pytest.raises(MentionParseError, match="unsupported validation command"):
        plan(db, "@backend @qa update the contacts API")
    assert db.exec(select(Task)).all() == []


def test_allowed_command_notes_and_duplicates_remain_scoped(db, monkeypatch):
    def expectations(value):
        value["planDraft"]["validationExpectations"] = ["pnpm build passes", "pnpm build passes", "pnpm demo:api:test succeeds"]
    native_provider(db, monkeypatch, mutate=expectations)
    tasks = plan(db, "@backend @frontend @qa update the demo app contacts UI and API")
    for task in tasks:
        item = json.loads(task.plan_json)
        expected = "pnpm demo:api:test succeeds" if item["targetId"] == "demo-backend" else "pnpm build passes"
        assert item["validationExpectations"] == [expected]
