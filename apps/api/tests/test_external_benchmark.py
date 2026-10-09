"""Harness regressions with explicit doubles; not live provider evidence."""
import asyncio
from pathlib import Path

import pytest

import app.external_benchmark as benchmark
import app.run_engine as run_engine
from app.adapters import AgentEvent
from app.provider_gateway import ProviderHealthResult
from app.scripted_mock import ScriptedMockAdapter


VALID = {
    "baselineFailing": True, "state": "completed", "providerTurnObserved": True,
    "postCheck": {"exitCode": 0, "counts": {"tests": 3, "pass": 3, "fail": 0}},
    "expectedTests": 3, "immutableInputs": True, "memoryReceiptValid": True,
    "scope": {"status": "passed"}, "diffValid": True,
}


@pytest.mark.parametrize("change,gate", [
    ({"baselineFailing": False}, "baseline_not_failing"),
    ({"state": "failed"}, "run_not_completed"),
    ({"providerTurnObserved": False}, "provider_turn_unobserved"),
    ({"postCheck": {"exitCode": 1}}, "post_check_failed"),
    ({"immutableInputs": False}, "inputs_modified"),
    ({"memoryReceiptValid": False}, "memory_receipt_invalid"),
    ({"scope": {"status": "unverifiable"}}, "scope_not_passed"),
    ({"diffValid": False}, "diff_invalid"),
])
def test_green_functional_check_does_not_override_failed_evidence(change, gate):
    assert benchmark.score_case({**VALID, **change}) == [gate]


def test_prepare_freezes_three_failing_inputs_without_invoking_worker(tmp_path, monkeypatch):
    async def forbidden(*_args, **_kwargs):
        pytest.fail("prepare-only must not invoke a provider worker")
    monkeypatch.setattr(run_engine.RunWorker, "run_once", forbidden)
    output = tmp_path / "fresh"
    report = asyncio.run(benchmark.run_benchmark(output, prepare_only=True))
    assert len(report["cases"]) == 3
    assert all(case["baselineFailing"] and case["evaluatorHash"] for case in report["cases"])
    assert report["summary"]["successRate"] is None
    assert report["summary"]["providerTurnsObserved"] == 0
    assert (output / "benchmark.sqlite3").is_file()
    assert (output / "report.json").is_file()
    for case in report["cases"]:
        target = output / case["caseId"] / "target"
        assert not (target / "evaluator").exists()
        assert benchmark.git(target, "status", "--porcelain") == ""


def test_rejects_existing_and_checkout_outputs_without_modification(tmp_path):
    sentinel = tmp_path / "sentinel.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        benchmark.reserve_output(tmp_path)
    with pytest.raises(ValueError):
        benchmark.reserve_output(benchmark.REPO_ROOT / "unsafe-benchmark-output")
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not (benchmark.REPO_ROOT / "unsafe-benchmark-output").exists()


def test_unknown_case_does_not_create_output(tmp_path):
    output = tmp_path / "unknown"
    with pytest.raises(ValueError, match="Unknown"):
        asyncio.run(benchmark.run_benchmark(output, case_id="unknown"))
    assert not output.exists()


def test_rejects_system_output(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "is_system_path", lambda _path: True)
    with pytest.raises(ValueError):
        benchmark.reserve_output(tmp_path / "system")
    assert not (tmp_path / "system").exists()


def test_missing_evaluator_runtime_is_a_failure_not_a_negative_baseline(tmp_path, monkeypatch):
    def missing(*_args, **_kwargs):
        raise FileNotFoundError("Node unavailable")
    monkeypatch.setattr(benchmark, "command", missing)
    assert benchmark.evaluate(tmp_path / "missing.test.mjs")["exitCode"] is None


def test_baseline_launch_failure_prevents_live_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "evaluate", lambda _path: {"exitCode": None, "errorType": "FileNotFoundError"})
    async def forbidden(*_args, **_kwargs):
        pytest.fail("invalid baseline must not invoke provider")
    monkeypatch.setattr(run_engine.RunWorker, "run_once", forbidden)
    report = asyncio.run(benchmark.run_benchmark(tmp_path / "invalid", case_id="title-normalization"))
    assert report["cases"][0]["failureGates"] == ["baseline_not_failing"]
    assert report["summary"]["successRate"] == 0


def test_failure_and_unattempted_cases_stay_in_live_denominator():
    cases = [{"verdict": verdict} for verdict in ("passed", "harness_error", "not_attempted")]
    result = benchmark.summary(cases, prepare_only=False)
    assert result["selectedCases"] == 3
    assert result["successRate"] == pytest.approx(1 / 3)
    assert result["failedCases"] == 1
    assert result["notAttemptedCases"] == 1


def test_premature_process_exit_cannot_fabricate_functional_success():
    evidence = {**VALID, "postCheck": {"exitCode": 0, "counts": {"tests": 1, "pass": 1, "fail": 0}}}
    assert benchmark.score_case(evidence) == ["post_check_failed"]


def test_evaluator_cannot_write_files_or_spawn_child_processes(tmp_path):
    fixture = benchmark.prepare_fixture(tmp_path, benchmark.load_suite("title-normalization")[0])
    evaluator = fixture["evaluator"]
    evaluator.write_text("""
import test from 'node:test';
import assert from 'node:assert/strict';
import { writeFileSync, readFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
test('permissions remain constrained', () => {
  assert.throws(() => writeFileSync(new URL('./forged.txt', import.meta.url), 'bad'), {code: 'ERR_ACCESS_DENIED'});
  assert.throws(() => readFileSync(new URL('../../outside.txt', import.meta.url)), {code: 'ERR_ACCESS_DENIED'});
  assert.throws(() => execSync('node --version'), {code: 'ERR_ACCESS_DENIED'});
});
""", encoding="utf-8")
    assert benchmark.evaluate(evaluator)["exitCode"] == 0
    assert not (evaluator.parent / "forged.txt").exists()


class BenchmarkTestDouble(ScriptedMockAdapter):
    observe_turn = True
    damage_evaluator = False
    fail_after_write = False
    no_changes = False
    revert_to_head = False

    async def streamEvents(self, run_id):
        request = self._request_for(run_id)
        target = Path(request.worktree_path)
        if self.revert_to_head:
            (target / benchmark.ALLOWED_FILE).write_text(
                benchmark.git(target, "show", "HEAD:" + benchmark.ALLOWED_FILE) + "\n", encoding="utf-8")
        elif not self.no_changes:
            (target / benchmark.ALLOWED_FILE).write_text(
                "export function slugifyTitle(title) { return title.toLowerCase().replace(/[^\\p{L}\\p{N}]+/gu, '-').replace(/^-|-$/g, ''); }\n",
                encoding="utf-8",
            )
        if self.damage_evaluator:
            # Deliberate out-of-sandbox test attack, never exposed as a runtime adapter.
            (target.parent / "evaluator" / "acceptance.test.mjs").write_text("", encoding="utf-8")
        if self.observe_turn:
            yield AgentEvent(type="task.state", taskRunId=request.task_run_id,
                             payload={"codexEventType": "thread.started", "state": "streaming"})
        if self.fail_after_write:
            yield AgentEvent(type="error", taskRunId=request.task_run_id,
                             payload={"code": "EXPLICIT_TEST_FAILURE", "message": "Test failure after write"})
            return
        yield AgentEvent(type="completed", taskRunId=request.task_run_id,
                         payload={"codexEventType": "turn.completed"} if self.observe_turn else {})


@pytest.mark.parametrize("observed,tampered,expected_gate", [
    (True, False, None), (False, False, "provider_turn_unobserved"), (True, True, "inputs_modified"),
])
def test_worker_path_records_real_git_and_fails_closed_on_missing_turn_or_tampering(
    tmp_path, monkeypatch, observed, tampered, expected_gate,
):
    adapter = BenchmarkTestDouble()
    adapter.observe_turn = observed
    adapter.damage_evaluator = tampered
    monkeypatch.setattr(run_engine, "CodexAdapter", lambda: adapter)
    monkeypatch.setattr(run_engine._provider_health_probe, "check_provider", lambda provider, **_kwargs:
        ProviderHealthResult(provider.provider_id, "codex", "healthy", True, "Explicit test double"))
    report = asyncio.run(benchmark.run_benchmark(tmp_path / "worker", case_id="title-normalization"))
    case = report["cases"][0]
    assert case["state"] == "completed", case
    assert case["memoryReceiptValid"] is True
    assert case["scope"]["status"] == "passed"
    assert case["diffValid"] is True
    assert case["completionValidation"]["status"] == "passed"
    assert case["completionValidation"]["functionalAcceptance"] == "not_evaluated"
    assert case["postCheck"]["exitCode"] == 0
    assert any(item["type"] == "review" for item in case["artifacts"])
    assert case["verdict"] == ("failed" if expected_gate else "passed")
    expected = ["post_check_failed", expected_gate] if tampered else ([expected_gate] if expected_gate else [])
    assert case["failureGates"] == expected


def test_failed_worker_with_green_functional_output_remains_failed(tmp_path, monkeypatch):
    adapter = BenchmarkTestDouble()
    adapter.fail_after_write = True
    monkeypatch.setattr(run_engine, "CodexAdapter", lambda: adapter)
    monkeypatch.setattr(run_engine._provider_health_probe, "check_provider", lambda provider, **_kwargs:
        ProviderHealthResult(provider.provider_id, "codex", "healthy", True, "Explicit test double"))
    report = asyncio.run(benchmark.run_benchmark(tmp_path / "failed-worker", case_id="title-normalization"))
    case = report["cases"][0]
    assert case["state"] == "failed"
    assert case["postCheck"]["exitCode"] == 0
    assert case["verdict"] == "failed"
    assert "run_not_completed" in case["failureGates"]
    assert case["errorCode"] == "EXPLICIT_TEST_FAILURE"
    assert report["summary"]["successRate"] == 0


@pytest.mark.parametrize("dirty,revert,error_code", [
    (False, False, "TASK_RUN_NO_CHANGES"),
    (True, False, "TASK_RUN_NO_CHANGES"),
    (True, True, "TASK_RUN_EMPTY_DIFF"),
])
def test_write_completion_rejects_text_only_old_patch_and_empty_output(tmp_path, monkeypatch, dirty, revert, error_code):
    adapter = BenchmarkTestDouble()
    adapter.no_changes = True
    adapter.revert_to_head = revert
    if dirty:
        prepare = benchmark.prepare_fixture
        def dirty_fixture(*args, **kwargs):
            result = prepare(*args, **kwargs)
            target = result["target"]
            module = target / benchmark.ALLOWED_FILE
            module.write_text(module.read_text(encoding="utf-8") + "\n// preexisting user change\n", encoding="utf-8")
            return result
        monkeypatch.setattr(benchmark, "prepare_fixture", dirty_fixture)
    monkeypatch.setattr(run_engine, "CodexAdapter", lambda: adapter)
    monkeypatch.setattr(run_engine._provider_health_probe, "check_provider", lambda provider, **_kwargs:
        ProviderHealthResult(provider.provider_id, "codex", "healthy", True, "Explicit test double"))
    case = asyncio.run(benchmark.run_benchmark(tmp_path / "no-output", case_id="title-normalization"))["cases"][0]
    assert case["state"] == "failed", case
    assert case["errorCode"] == error_code
    assert case["completionValidation"]["status"] == "failed"
    assert case["scope"]["status"] == "passed"
    assert not any(item["type"] in {"review", "preview", "deployment"} for item in case["artifacts"])


def test_diff_collection_failure_cannot_complete_write_or_create_review(tmp_path, monkeypatch):
    from app.diffs import DiffCollectionError
    adapter = BenchmarkTestDouble()
    monkeypatch.setattr(run_engine, "CodexAdapter", lambda: adapter)
    monkeypatch.setattr(run_engine._provider_health_probe, "check_provider", lambda provider, **_kwargs:
        ProviderHealthResult(provider.provider_id, "codex", "healthy", True, "Explicit test double"))
    def unavailable(*_args):
        raise DiffCollectionError("Controlled collector failure")
    monkeypatch.setattr(run_engine, "collect_task_run_diff", unavailable)
    case = asyncio.run(benchmark.run_benchmark(tmp_path / "missing-diff", case_id="title-normalization"))["cases"][0]
    assert case["state"] == "failed"
    assert case["errorCode"] == "TASK_RUN_OUTPUT_UNVERIFIABLE"
    assert case["completionValidation"]["status"] == "failed"
    assert not any(item["type"] == "review" for item in case["artifacts"])
