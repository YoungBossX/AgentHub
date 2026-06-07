from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.pool import StaticPool
from sqlmodel import Session as DbSession
from sqlmodel import SQLModel, create_engine

from app.live_memory_compliance import (
    P18C_LIBRARY_APP_USER_PROMPT,
    P18C_MEMORY_RULES,
    LiveMemoryComplianceEvidence,
    ProviderEvidence,
    check_live_memory_compliance,
    ensure_p18c_memory_rules,
    prepare_p18c_session_setup,
)
from app.memory_store import MemoryFilter, list_memory_items
from app.models import ExternalProjectTarget, MemorySnapshot, Session, Workspace


def test_compliant_changed_files_pass_and_report_active_memory_rules() -> None:
    report = check_live_memory_compliance(_compliant_evidence())

    assert report.passed is True
    assert report.violations == ()
    assert report.memory_snapshot_id == "snapshot-1"
    assert report.active_memory_rule_ids == tuple(rule.key for rule in P18C_MEMORY_RULES)
    assert report.docs_change_log_updated is True
    assert report.forbidden_platform_paths_touched is False
    assert report.unexpected_backend_or_database_created is False
    assert report.provider_evidence_exists is True
    assert report.to_payload()["summary"] == "passed"


def test_missing_docs_change_log_is_flagged() -> None:
    evidence = _compliant_evidence(
        changed_files=(
            "~/Desktop/agenthub-rehearsals/library-app/src/App.tsx",
            "~/Desktop/agenthub-rehearsals/library-app/package.json",
        )
    )

    report = check_live_memory_compliance(evidence)

    assert "memory_compliance_violation" in report.violations
    assert report.docs_change_log_updated is False
    assert report.passed is False


def test_apps_api_modification_is_flagged() -> None:
    evidence = _compliant_evidence(
        changed_files=(
            "~/Desktop/agenthub-rehearsals/library-app/src/App.tsx",
            "apps/api/app/main.py",
            "docs/change-log.md",
        )
    )

    report = check_live_memory_compliance(evidence)

    assert "target_boundary_violation" in report.violations
    assert report.forbidden_platform_paths_touched is True


def test_backend_or_database_creation_is_flagged_when_not_requested() -> None:
    evidence = _compliant_evidence(
        changed_files=(
            "~/Desktop/agenthub-rehearsals/library-app/src/App.tsx",
            "~/Desktop/agenthub-rehearsals/library-app/server/index.ts",
            "docs/change-log.md",
        ),
        persistence="backend_database",
    )

    report = check_live_memory_compliance(evidence)

    assert "persistence_memory_violation" in report.violations
    assert report.unexpected_backend_or_database_created is True


def test_wrong_project_location_is_flagged() -> None:
    evidence = _compliant_evidence(
        project_root="~/Desktop/library-app",
        changed_files=(
            "~/Desktop/library-app/src/App.tsx",
            "~/Desktop/library-app/package.json",
            "docs/change-log.md",
        ),
    )

    report = check_live_memory_compliance(evidence)

    assert "project_location_memory_violation" in report.violations
    assert report.expected_target_path == "~/Desktop/agenthub-rehearsals/"


def test_missing_frontend_stack_is_flagged() -> None:
    evidence = _compliant_evidence(frontend_stack=("vite", "react"))

    report = check_live_memory_compliance(evidence)

    assert "frontend_stack_memory_violation" in report.violations


def test_missing_provider_evidence_is_flagged() -> None:
    evidence = _compliant_evidence(
        provider_evidence=ProviderEvidence(
            provider_id="local-codex-cli",
            adapter_type="codex",
            task_run_id=None,
            diff_artifact_id="diff-1",
            build_or_validation_evidence_id="build-1",
        )
    )

    report = check_live_memory_compliance(evidence)

    assert "provider_evidence_violation" in report.violations
    assert report.provider_evidence_exists is False


def test_mismatched_memory_snapshot_id_is_flagged() -> None:
    evidence = _compliant_evidence(
        snapshot_ids_by_source={
            "planner": "snapshot-1",
            "coding_agent": "snapshot-2",
            "review": "snapshot-1",
        }
    )

    report = check_live_memory_compliance(evidence)

    assert "snapshot_consistency_violation" in report.violations
    assert report.snapshot_consistency_rate < 1.0


def test_business_prompt_does_not_restate_memory_rules() -> None:
    assert P18C_LIBRARY_APP_USER_PROMPT == (
        "帮我在桌面开发一个简单的图书管理系统。有登录页面，初始账户和密码是 "
        "18088888888 / 888888。登录后进入管理页面，只需要有图书管理功能："
        "加入图书、删除图书、修改图书、查询图书。"
    )

    forbidden_fragments = (
        "agenthub-rehearsals",
        "Vite",
        "React",
        "TypeScript",
        "localStorage",
        "docs/change-log.md",
        "AgentHub platform",
        "TaskRun",
        "diff",
    )
    assert all(fragment not in P18C_LIBRARY_APP_USER_PROMPT for fragment in forbidden_fragments)


def test_ensure_p18c_memory_rules_creates_active_canonical_memory() -> None:
    with _db() as db:
        workspace = _workspace(db)
        created = ensure_p18c_memory_rules(db, workspace_id=workspace.id)
        reused = ensure_p18c_memory_rules(db, workspace_id=workspace.id)
        active = list_memory_items(
            db,
            MemoryFilter(workspace_id=workspace.id, status="active"),
        )

    assert len(created) == len(P18C_MEMORY_RULES)
    assert [item.id for item in reused] == [item.id for item in created]
    assert {item.title for item in active} == {rule.title for rule in P18C_MEMORY_RULES}
    assert all(item.trust_level == "user_confirmed" for item in active)
    assert all("demo frontend" not in item.content_md for item in active)
    assert all("simple demo apps" not in item.content_md for item in active)
    assert any("若无特殊说明" in item.content_md for item in active)


def test_ensure_p18c_memory_rules_archives_obsolete_active_rules() -> None:
    with _db() as db:
        workspace = _workspace(db)
        old_rule = ensure_p18c_memory_rules(db, workspace_id=workspace.id)[0]
        old_rule.content_md = "New demo frontend projects should use the old wording."
        db.add(old_rule)
        db.commit()

        refreshed = ensure_p18c_memory_rules(db, workspace_id=workspace.id)
        all_items = list_memory_items(db, MemoryFilter(workspace_id=workspace.id))
        active = list_memory_items(
            db,
            MemoryFilter(workspace_id=workspace.id, status="active"),
        )

    archived = [item for item in all_items if item.status == "archived"]
    assert len(refreshed) == len(P18C_MEMORY_RULES)
    assert any(item.id == old_rule.id for item in archived)
    assert {item.title for item in active} == {rule.title for rule in P18C_MEMORY_RULES}
    assert all("old wording" not in item.content_md for item in active)


def test_prepare_p18c_session_setup_creates_target_session_and_snapshot(
    tmp_path,
) -> None:
    with _db() as db:
        workspace = _workspace(db)
        setup = prepare_p18c_session_setup(
            db,
            workspace=workspace,
            rehearsal_root=tmp_path / "agenthub-rehearsals",
        )
        session = db.get(Session, setup.session_id)
        snapshot = db.get(MemorySnapshot, setup.memory_snapshot_id)
        target = db.get(ExternalProjectTarget, setup.external_target_db_id)

    assert setup.rehearsal_root == str((tmp_path / "agenthub-rehearsals").resolve())
    assert setup.project_root.endswith("agenthub-rehearsals/p18c-library-app")
    assert setup.target_id == "external-p18c-library-app"
    assert setup.allowed_paths == ("src",)
    assert setup.active_memory_rule_ids == tuple(rule.key for rule in P18C_MEMORY_RULES)
    assert setup.agents_md_hash
    assert setup.claude_md_hash
    assert setup.target_registry_version
    assert setup.runtime_config_version
    assert setup.context_pack_hash
    assert session is not None
    assert session.memory_snapshot_id == setup.memory_snapshot_id
    assert session.active_frontend_target_id == setup.target_id
    assert snapshot is not None
    assert target is not None
    assert target.target_id == setup.target_id


def test_prepare_p18c_session_setup_reuses_existing_target(tmp_path) -> None:
    with _db() as db:
        workspace = _workspace(db)
        first = prepare_p18c_session_setup(
            db,
            workspace=workspace,
            rehearsal_root=tmp_path / "agenthub-rehearsals",
        )
        second = prepare_p18c_session_setup(
            db,
            workspace=workspace,
            rehearsal_root=tmp_path / "agenthub-rehearsals",
            session_title="P18c second setup",
        )

    assert first.target_id == second.target_id
    assert first.external_target_db_id == second.external_target_db_id
    assert first.session_id != second.session_id


def _compliant_evidence(**overrides: object) -> LiveMemoryComplianceEvidence:
    values: dict[str, object] = {
        "memory_snapshot_id": "snapshot-1",
        "active_memory_rule_ids": tuple(rule.key for rule in P18C_MEMORY_RULES),
        "changed_files": (
            "~/Desktop/agenthub-rehearsals/library-app/package.json",
            "~/Desktop/agenthub-rehearsals/library-app/src/App.tsx",
            "~/Desktop/agenthub-rehearsals/library-app/tsconfig.json",
            "~/Desktop/agenthub-rehearsals/library-app/vite.config.ts",
            "docs/change-log.md",
        ),
        "project_root": "~/Desktop/agenthub-rehearsals/library-app",
        "frontend_stack": ("vite", "react", "typescript"),
        "persistence": "localStorage",
        "provider_evidence": ProviderEvidence(
            provider_id="local-codex-cli",
            adapter_type="codex",
            task_run_id="run-1",
            diff_artifact_id="diff-1",
            build_or_validation_evidence_id="build-1",
        ),
        "snapshot_ids_by_source": {
            "planner": "snapshot-1",
            "coding_agent": "snapshot-1",
            "review": "snapshot-1",
        },
        "user_requested_backend_or_database": False,
        "platform_maintenance_mode": False,
    }
    values.update(overrides)
    return LiveMemoryComplianceEvidence(**values)


@contextmanager
def _db() -> Iterator[DbSession]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with DbSession(engine) as session:
        yield session


def _workspace(db: DbSession) -> Workspace:
    workspace = Workspace(
        name="P18c Memory Compliance",
        repo_url="local://agenthub-rehearsals",
        root_path="~/Desktop/agenthub-rehearsals",
        default_branch="main",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace
