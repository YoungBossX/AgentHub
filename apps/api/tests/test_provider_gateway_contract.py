import json
from typing import Optional

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session as DbSession, create_engine, select

from app.models import TaskRun, TaskRunEvent
from app.provider_configs import list_provider_configs
from app.provider_gateway import (
    CODING_ADAPTER_TYPES,
    PROVIDER_GATEWAY_EVENT_TYPES,
    CodingProviderMetadata,
    CodingRunContext,
    ProviderCandidateDecision,
    ProviderErrorClassification,
    ProviderFallbackEvidence,
    ProviderGatewayResult,
    ProviderGatewayStatus,
    ProviderHealthResult,
    ProviderHealthProbe,
    ProviderRegistry,
    ProviderResolver,
    ProviderResolutionPlan,
    coding_provider_ids_from_configs,
    is_coding_adapter_type,
    record_provider_health_check,
    record_provider_resolution,
    redact_provider_evidence,
)


def test_gateway_result_evidence_preserves_failure_and_fallback_chain() -> None:
    resolution = ProviderResolutionPlan(
        selected_provider_id="local-codex-cli",
        selected_adapter_type="codex",
        selection_reason="runtime config selected Codex for frontend write mode",
        selected_is_real_provider=True,
        candidates=(
            ProviderCandidateDecision(
                provider_id="local-codex-cli",
                adapter_type="codex",
                accepted=True,
                reason="compatible",
            ),
        ),
        fallback_candidates=(
            ProviderCandidateDecision(
                provider_id="local-scripted-mock",
                adapter_type="scripted_mock",
                accepted=True,
                reason="demo fallback policy allows scripted mock",
            ),
        ),
    )
    result = ProviderGatewayResult(
        task_run_id="run-1",
        status=ProviderGatewayStatus.FALLBACK_SUCCEEDED,
        resolution=resolution,
        final_provider_id="local-scripted-mock",
        final_adapter_type="scripted_mock",
        health=ProviderHealthResult(
            provider_id="local-codex-cli",
            adapter_type="codex",
            status="unavailable",
            available=False,
            reason="Codex CLI auth failed",
            safe_details={"stderr": "token=secret-value"},
        ),
        error=ProviderErrorClassification(
            provider_id="local-codex-cli",
            category="auth",
            retryable=False,
            fallback_eligible=True,
            circuit_breaker_eligible=True,
            user_message="Codex authentication is not available.",
            safe_evidence={"raw": "api_key=sk-test"},
        ),
        fallback_chain=(
            ProviderFallbackEvidence(
                original_provider_id="local-codex-cli",
                fallback_provider_id="local-scripted-mock",
                trigger_category="auth",
                reason="scripted mock selected after auth failure",
                mock=True,
                completed=True,
            ),
        ),
    )

    evidence = result.to_evidence()

    assert evidence["status"] == "fallback_succeeded"
    assert evidence["selectedProviderId"] == "local-codex-cli"
    assert evidence["finalProviderId"] == "local-scripted-mock"
    assert evidence["finalAdapterType"] == "scripted_mock"
    assert evidence["error"]["category"] == "auth"
    assert evidence["error"]["safeEvidence"]["raw"] == "api_key=[redacted]"
    assert evidence["health"]["safeDetails"]["stderr"] == "token=[redacted]"
    assert evidence["fallbackChain"][0]["fallback"] is True
    assert evidence["fallbackChain"][0]["mock"] is True
    assert "provider.resolved" in evidence["eventTypes"]
    assert PROVIDER_GATEWAY_EVENT_TYPES == result.event_types


def test_provider_gateway_redacts_secrets_and_protected_host_paths() -> None:
    evidence = redact_provider_evidence(
        {
            "apiKey": "sk-should-not-leak",
            "summary": (
                "token=abc123 failed under "
                "/Users/demo/project/.env.local and /tmp/safe/file.txt"
            ),
            "nested": {
                "stderr": "credential:xyz in /Users/demo/project/node_modules/pkg",
            },
        }
    )

    assert evidence["apiKey"] == "[redacted]"
    assert "abc123" not in evidence["summary"]
    assert "/Users/demo/project/.env.local" not in evidence["summary"]
    assert "/tmp/safe/file.txt" not in evidence["summary"]
    assert "xyz" not in evidence["nested"]["stderr"]
    assert "/Users/demo/project/node_modules/pkg" not in evidence["nested"]["stderr"]


def test_coding_gateway_excludes_planner_providers() -> None:
    provider_ids = coding_provider_ids_from_configs(list_provider_configs())

    assert "local-claude-code-cli" in provider_ids
    assert "local-codex-cli" in provider_ids
    assert "local-scripted-mock" in provider_ids
    assert "claude-cli-planner" not in provider_ids
    assert is_coding_adapter_type("claude_cli") is False
    assert is_coding_adapter_type("openai_responses") is False
    assert CODING_ADAPTER_TYPES == frozenset(
        {"claude_code", "codex", "scripted_mock"}
    )


def test_provider_registry_derives_safe_coding_metadata_only() -> None:
    registry = ProviderRegistry()
    providers = {provider.provider_id: provider for provider in registry.list_providers()}

    assert set(providers) == {
        "local-claude-code-cli",
        "local-codex-cli",
        "local-scripted-mock",
    }
    assert providers["local-codex-cli"].adapter_type == "codex"
    assert providers["local-codex-cli"].is_real_provider is True
    assert providers["local-scripted-mock"].is_mock_provider is True
    assert providers["local-scripted-mock"].is_fallback_provider is True
    assert "planner" not in providers["local-scripted-mock"].supported_roles
    assert "orchestrator" not in providers["local-scripted-mock"].supported_roles
    assert "Codex CLI" in providers["local-codex-cli"].display_name
    assert "/Users/" not in providers["local-codex-cli"].to_evidence()[
        "safeLaunchSummary"
    ]


def test_provider_resolver_uses_default_runtime_and_explicit_provider() -> None:
    resolver = ProviderResolver()

    default_plan = resolver.resolve(_context(role="frontend"))
    assert default_plan.selected_provider_id == "local-codex-cli"
    assert default_plan.selected_adapter_type == "codex"
    assert default_plan.selected_is_real_provider is True
    assert default_plan.should_fail is False

    runtime_plan = resolver.resolve(
        _context(
            role="frontend",
            runtime_provider_id="local-claude-code-cli",
            runtime_adapter_type="claude_code",
        )
    )
    assert runtime_plan.selected_provider_id == "local-claude-code-cli"
    assert runtime_plan.selection_reason == (
        "Runtime coding provider configuration is compatible."
    )

    explicit_plan = resolver.resolve(
        _context(role="backend", requested_provider_id="local-claude-code-cli")
    )
    assert explicit_plan.selected_provider_id == "local-claude-code-cli"
    assert explicit_plan.selection_reason == "Explicit provider request is compatible."


def test_provider_resolver_rejects_unavailable_provider_and_lists_fallback() -> None:
    registry = ProviderRegistry(
        providers=[
            _provider(
                provider_id="local-codex-cli",
                adapter_type="codex",
                availability="unavailable",
                is_real_provider=True,
            ),
            _provider(
                provider_id="local-scripted-mock",
                adapter_type="scripted_mock",
                is_real_provider=False,
                is_mock_provider=True,
                is_fallback_provider=True,
            ),
        ]
    )
    resolver = ProviderResolver(registry)

    plan = resolver.resolve(
        _context(
            role="frontend",
            requested_provider_id="local-codex-cli",
            fallback_policy="scripted_mock",
        )
    )

    assert plan.selected_provider_id == "local-scripted-mock"
    assert plan.selected_adapter_type == "scripted_mock"
    assert plan.selected_is_real_provider is False
    assert plan.should_fail is False
    assert plan.rejected_candidates[0].provider_id == "local-codex-cli"
    assert plan.rejected_candidates[0].reason == "Provider availability is unavailable."
    assert plan.fallback_candidates[0].provider_id == "local-scripted-mock"


def test_provider_resolver_does_not_use_planner_runtime_provider() -> None:
    resolver = ProviderResolver()

    plan = resolver.resolve(
        _context(
            role="frontend",
            runtime_provider_id="claude-cli-planner",
            runtime_adapter_type="claude_cli",
        )
    )

    assert plan.selected_provider_id == "local-codex-cli"
    assert all(
        candidate.provider_id != "claude-cli-planner"
        for candidate in plan.candidates
    )


def test_record_provider_resolution_event_updates_task_run_metrics() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    plan = ProviderResolver().resolve(_context(role="frontend"))

    with DbSession(engine) as db:
        task_run = TaskRun(
            task_id="task-1",
            agent_id="agent-1",
            state="queued",
            worktree_path=".worktrees/session",
            metrics_json="{}",
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        record_provider_resolution(db, task_run_id=task_run.id, plan=plan)

        event = db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.task_run_id == task_run.id,
                TaskRunEvent.event_type == "provider.resolved",
            )
        ).one()
        stored = db.get(TaskRun, task_run.id)
        metrics = json.loads(stored.metrics_json)
        payload = json.loads(event.payload_json)

    assert payload["selectedProviderId"] == "local-codex-cli"
    assert payload["selectionReason"] == "Default coding provider is compatible."
    assert metrics["providerGateway"]["resolution"]["selectedProviderId"] == (
        "local-codex-cli"
    )


def test_provider_health_probe_reports_healthy_cli_without_leaking_path() -> None:
    provider = ProviderRegistry().get("local-codex-cli")
    probe = ProviderHealthProbe(
        command_lookup=lambda command: "/Users/demo/.env/bin/codex",
        version_runner=lambda executable: (
            True,
            {"output": "codex 1.0 token=secret-value", "executable": executable},
        ),
    )

    health = probe.check_provider(provider)
    evidence = health.to_evidence()

    assert health.status == "healthy"
    assert health.available is True
    assert evidence["safeDetails"]["command"] == "codex"
    assert "secret-value" not in evidence["safeDetails"]["output"]
    assert "/Users/demo/.env/bin/codex" not in json.dumps(evidence)


def test_provider_health_probe_reports_unavailable_cli() -> None:
    provider = ProviderRegistry().get("local-claude-code-cli")
    probe = ProviderHealthProbe(command_lookup=lambda command: None)

    health = probe.check_provider(provider)

    assert health.status == "unavailable"
    assert health.available is False
    assert health.safe_details["fallbackDoesNotImplyHealthy"] is True


def test_provider_health_probe_reports_unknown_for_unhandled_provider() -> None:
    provider = _provider(
        provider_id="local-custom",
        adapter_type="codex",
        is_real_provider=True,
    )
    object.__setattr__(provider, "adapter_type", "custom")
    probe = ProviderHealthProbe()

    health = probe.check_provider(provider)

    assert health.status == "unknown"
    assert health.available is False


def test_provider_health_probe_checks_scripted_mock_demo_boundary(tmp_path) -> None:
    provider = ProviderRegistry().get("local-scripted-mock")
    app_path = tmp_path / "apps/demo/src/App.tsx"
    app_path.parent.mkdir(parents=True)
    app_path.write_text("export default function App() { return null }")
    probe = ProviderHealthProbe()

    healthy = probe.check_provider(
        provider,
        context=_context(role="frontend", worktree_path=str(tmp_path)),
    )
    missing = probe.check_provider(
        provider,
        context=_context(role="frontend", worktree_path=str(tmp_path / "missing")),
    )
    unknown = probe.check_provider(provider)

    assert healthy.status == "healthy"
    assert healthy.available is True
    assert healthy.to_evidence()["safeDetails"]["demoBoundary"] == (
        "apps/demo/src/App.tsx"
    )
    assert str(tmp_path) not in json.dumps(healthy.to_evidence())
    assert missing.status == "unavailable"
    assert unknown.status == "unknown"


def test_record_provider_health_check_event_updates_task_run_metrics() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    health = ProviderHealthResult(
        provider_id="local-codex-cli",
        adapter_type="codex",
        status="unavailable",
        available=False,
        reason="CLI missing",
        safe_details={"stderr": "api_key=secret"},
    )

    with DbSession(engine) as db:
        task_run = TaskRun(
            task_id="task-1",
            agent_id="agent-1",
            state="queued",
            worktree_path=".worktrees/session",
            metrics_json="{}",
        )
        db.add(task_run)
        db.commit()
        db.refresh(task_run)

        record_provider_health_check(db, task_run_id=task_run.id, health=health)

        event = db.exec(
            select(TaskRunEvent).where(
                TaskRunEvent.task_run_id == task_run.id,
                TaskRunEvent.event_type == "provider.health_checked",
            )
        ).one()
        stored = db.get(TaskRun, task_run.id)
        metrics = json.loads(stored.metrics_json)
        payload = json.loads(event.payload_json)

    assert payload["status"] == "unavailable"
    assert payload["safeDetails"]["stderr"] == "api_key=[redacted]"
    assert metrics["providerGateway"]["health"]["providerId"] == "local-codex-cli"


def _context(
    *,
    role: str,
    requested_provider_id: Optional[str] = None,
    runtime_provider_id: Optional[str] = None,
    runtime_adapter_type: Optional[str] = None,
    fallback_policy: str = "environment_default",
    worktree_path: Optional[str] = None,
) -> CodingRunContext:
    return CodingRunContext(
        workspace_id="workspace-1",
        session_id="session-1",
        task_id="task-1",
        task_run_id="run-1",
        role=role,
        mode="write",
        required_capabilities=("file_edit",),
        worktree_path=worktree_path,
        requested_provider_id=requested_provider_id,
        runtime_provider_id=runtime_provider_id,
        runtime_adapter_type=runtime_adapter_type,
        fallback_policy=fallback_policy,
    )


def _provider(
    *,
    provider_id: str,
    adapter_type: str,
    availability: str = "available",
    is_real_provider: bool,
    is_mock_provider: bool = False,
    is_fallback_provider: bool = False,
) -> CodingProviderMetadata:
    return CodingProviderMetadata(
        provider_id=provider_id,
        display_name=provider_id,
        adapter_type=adapter_type,
        supported_roles=("frontend", "backend", "review"),
        supported_targets=("*",),
        supported_modes=("write", "review"),
        capabilities=("file_edit", "diff_artifact", "preview_artifact"),
        availability=availability,
        is_real_provider=is_real_provider,
        is_mock_provider=is_mock_provider,
        is_fallback_provider=is_fallback_provider,
    )
