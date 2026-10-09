import base64
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.adapters import AgentRunRequest
from app.attachment_inputs import ImageInput, PlannerPayload
from app.claude_code_adapter import ClaudeCodeAdapter, SubprocessClaudeCodeRunner
from app.codex_adapter import CodexAdapter, SubprocessCodexRunner
from app.guardrails import evaluate_command
from app.planner_providers import (ClaudeCliPlannerProvider, _anthropic_messages_payload,
    _openai_compatible_chat_payload, _openai_responses_payload)
from app.scripted_mock import ScriptedMockAdapter


def image_input():
    output = io.BytesIO(); Image.new("RGB", (20, 20), "blue").save(output, "JPEG")
    data = output.getvalue()
    return ImageInput(attachment_id="image-id", sha256=hashlib.sha256(data).hexdigest(), media_type="image/jpeg", data=data)


def request(tmp_path):
    return AgentRunRequest(taskRunId="run", sessionId="session", workspaceId="workspace", agentId="writer",
        worktreePath=str(tmp_path), adapterType="claude_code", instruction="读取图像和文件\n" * 20000,
        has_attachments=True, images=(image_input(),))


def payload():
    return PlannerPayload({"agentToolPolicy": "planner_no_tools", "originalUserRequest": "Read attachment",
                          "canonicalSharedContext": {"fields": {"attachmentContext": {"value": {"items": [{"id": "image-id"}]}}}}}, (image_input(),))


def test_http_wire_images_are_actual_bytes_and_not_evidence_strings():
    value = payload()
    encoded = base64.b64encode(value.images[0].data).decode()
    assert encoded not in json.dumps(value)
    responses = _openai_responses_payload("vision-model", value)
    chat = _openai_compatible_chat_payload("vision-model", value)
    anthropic = _anthropic_messages_payload("vision-model", value)
    assert responses["input"][1]["content"][-1] == {"type": "input_image", "image_url": "data:image/jpeg;base64," + encoded}
    assert chat["messages"][1]["content"][-1]["image_url"]["url"].endswith(encoded)
    assert anthropic["messages"][0]["content"][-1]["source"]["data"] == encoded
    assert "image-id" in responses["input"][1]["content"][-2]["text"]
    forged = dict(value, images=[{"data": encoded}])
    assert len(_openai_responses_payload("vision-model", forged)["input"][1]["content"]) == 1


def test_claude_planner_uses_stdin_and_extracts_terminal_result():
    class Runner:
        def run(self, command, *, timeout, input_text=None):
            assert "--safe-mode" in command and "--strict-mcp-config" in command
            assert command[command.index("--tools") + 1] == ""
            assert command[command.index("--output-format") + 1] == "stream-json"
            assert command[-2:] == ["--input-format", "stream-json"]
            user = json.loads(input_text)
            assert user["message"]["content"][-1]["source"]["type"] == "base64"
            return subprocess.CompletedProcess(command, 0, json.dumps({"type": "system"}) + "\n" + json.dumps({"type": "result", "result": '{"outcomeType":"assistant_reply","reply":"image observed"}'}), "")
    result = ClaudeCliPlannerProvider(command_runner=Runner(), claude_binary="claude.exe").create_plan(payload())
    assert result.status == "succeeded" and json.loads(result.raw_output)["reply"] == "image observed"


def test_claude_unsupported_image_reports_terminal_error_instead_of_stderr_warning():
    class Runner:
        def run(self, command, **kwargs):
            return subprocess.CompletedProcess(command, 1, json.dumps({"type": "result", "is_error": True,
                "result": "API Error: 400 Model only support text input"}), "unrecognized_model warning")
    result = ClaudeCliPlannerProvider(command_runner=Runner(), claude_binary="claude.exe").create_plan(payload())
    assert result.status == "failed" and result.error_code == "PLANNER_IMAGE_UNSUPPORTED"
    assert "仅支持文本" in result.error_summary and "unrecognized_model" not in result.error_summary


def test_claude_input_acknowledgement_cannot_publish_binary_as_model_output():
    from app.claude_code_adapter import _map_claude_json_event

    event = {"type": "user", "message": {"role": "user", "content": [image_input().anthropic_block()]}}
    assert _map_claude_json_event(event, "run", "", []) is None


@pytest.mark.anyio
async def test_claude_native_stdin_retains_exact_tool_policy(tmp_path):
    class Runner:
        def start(self, command, cwd, *, input_text=None):
            self.command = command
            self.input = json.loads(input_text)
            return SimpleNamespace()
    runner = Runner(); adapter = ClaudeCodeAdapter(process_runner=runner, claude_binary="claude.exe")
    req = request(tmp_path)
    run = await adapter.createRun(req)
    assert evaluate_command(runner.command).allowed
    assert req.instruction not in runner.command and len(" ".join(runner.command)) < 1000
    assert runner.input["message"]["content"][0]["text"] == req.instruction
    assert runner.input["message"]["content"][-1]["source"]["media_type"] == "image/jpeg"
    for flag in ["--restricted", "--safe-mode", "--strict-mcp-config"]:
        altered = list(runner.command); altered.remove(flag)
        assert not evaluate_command(altered).allowed
    assert not evaluate_command([*runner.command, "--dangerously-skip-permissions"]).allowed
    await adapter.cleanup(run.adapter_run_id)


@pytest.mark.anyio
@pytest.mark.parametrize("fail", [False, True])
async def test_codex_images_require_exact_server_paths_and_are_cleaned(tmp_path, fail):
    class Runner:
        def start(self, command, cwd, *, input_text=None):
            self.command = command
            self.paths = [command[i + 1] for i, value in enumerate(command) if value == "--image"]
            assert self.paths and Path(self.paths[0]).read_bytes() == image_input().data
            assert input_text == request(tmp_path).instruction
            if fail: raise RuntimeError("start failed")
            return SimpleNamespace()
    runner = Runner(); adapter = CodexAdapter(process_runner=runner, codex_binary="codex.exe")
    run = await adapter.createRun(request(tmp_path))
    assert evaluate_command(runner.command, expected_cwd=tmp_path, expected_image_paths=runner.paths).allowed
    assert not evaluate_command(runner.command, expected_cwd=tmp_path).allowed
    assert not evaluate_command(runner.command, expected_cwd=tmp_path, expected_image_paths=[str(tmp_path / "foreign.jpg")]).allowed
    altered = list(runner.command); altered.insert(-2, "--add-dir"); altered.insert(-2, str(tmp_path.parent))
    assert not evaluate_command(altered, expected_cwd=tmp_path, expected_image_paths=runner.paths).allowed
    if not fail: assert Path(runner.paths[0]).exists()
    await adapter.cleanup(run.adapter_run_id)
    assert all(not Path(path).exists() for path in runner.paths)


@pytest.mark.anyio
async def test_large_utf8_private_stdin_reaches_real_subprocess(tmp_path):
    # Actual OS handles, not a fake Popen: closing the parent input handle must
    # not discard input or deadlock on pipe capacity.
    text = "输入附件内容 " * 50000
    command = [sys.executable, "-c", "import sys,hashlib; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())"]
    for runner in [SubprocessCodexRunner(), SubprocessClaudeCodeRunner()]:
        process = runner.start(command, tmp_path, input_text=text)
        output = "".join([line async for line in process.stdout_lines()])
        assert await process.wait() == 0
        assert output.strip() == hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.anyio
async def test_codex_interrupt_waits_for_exit_before_removing_input(tmp_path):
    class Process:
        terminated = False
        waited = False
        def terminate(self): self.terminated = True
        async def wait(self):
            assert self.terminated and Path(runner.path).exists()
            self.waited = True
            return 1
    class Runner:
        def start(self, command, cwd, **kwargs):
            self.path = command[command.index("--image") + 1]
            self.process = Process()
            return self.process
    runner = Runner(); adapter = CodexAdapter(process_runner=runner, codex_binary="codex.exe")
    run = await adapter.createRun(request(tmp_path))
    await adapter.interrupt(run.adapter_run_id)
    assert runner.process.waited and not Path(runner.path).exists()
    await adapter.cleanup(run.adapter_run_id)


@pytest.mark.anyio
async def test_mock_does_not_claim_attachment_understanding(tmp_path):
    adapter = ScriptedMockAdapter()
    run = await adapter.createRun(request(tmp_path))
    events = [event async for event in adapter.streamEvents(run.adapter_run_id)]
    assert [event.type for event in events] == ["error"]
    assert events[0].payload["code"] == "ATTACHMENTS_REQUIRE_NATIVE_AGENT"
    assert not list(tmp_path.iterdir())
