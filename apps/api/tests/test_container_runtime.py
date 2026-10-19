import importlib
import os
import sys
import threading

import pytest

from app.validation_policy import (BACKEND_PROFILE, ExecutionBinding, FixedValidationRequest, ImageBinding,
                                   SourceSnapshot, ValidationIdentity)


def request():
    return FixedValidationRequest(SourceSnapshot("demo-backend", BACKEND_PROFILE, {}, {}, "f" * 64, {}),
        ValidationIdentity("run", "adapter", "attempt", "e" * 64),
        ExecutionBinding("docker", BACKEND_PROFILE, ImageBinding("sha256:" + "a" * 64, "b" * 64, "linux/amd64", "local"),
                         "c" * 64, "d" * 32))


def runtime_module(): return importlib.import_module("app.container_runtime")


def test_runtime_uses_exact_profile_flags_and_no_shell(tmp_path):
    directory = tmp_path / "空格 snapshot"
    directory.mkdir()
    argv = runtime_module().create_arguments(request(), directory, {"io.agenthub.operation": "d" * 32})
    assert argv[:2] == ["container", "create"]
    for flag, value in {"--pull": "never", "--user": "10001:10001", "--network": "none", "--cap-drop": "ALL",
                        "--cpus": "1", "--memory": "1073741824", "--memory-swap": "1073741824",
                        "--pids-limit": "128", "--log-driver": "none", "--restart": "no"}.items():
        assert argv[argv.index(flag) + 1] == value
    assert "--init" in argv and "--read-only" in argv
    assert argv.count("--mount") == 1
    assert argv[argv.index("--mount") + 1] == f"type=bind,source={directory},destination=/input,readonly"
    assert "--privileged" not in argv and "--publish" not in argv and "--rm" not in argv
    assert argv[-2:] == ["sha256:" + "a" * 64, "hold"]
    assert "/work:rw,nosuid,nodev,noexec,size=536870912,uid=10001,gid=10001,mode=0700" in argv


@pytest.mark.parametrize("name", ["with,comma", 'with"quote', "with'quote", "with\nline"])
def test_mount_csv_metacharacters_refused(tmp_path, name):
    # Newlines are not valid directory names on Windows; rejection precedes I/O.
    with pytest.raises(ValueError): runtime_module().create_arguments(request(), tmp_path / name, {})


def test_runtime_does_not_inherit_credentials_or_remote_context(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-leak")
    monkeypatch.setenv("DOCKER_HOST", "tcp://example:2375")
    from app.sandbox_cli import docker_client_environment
    assert "OPENAI_API_KEY" not in docker_client_environment()
    assert "DOCKER_HOST" not in docker_client_environment()
    with pytest.raises(ValueError): runtime_module().DockerRuntime.check_context("docker", "local")


def test_windows_plugin_lookup_keeps_only_system_path_not_user_overrides(monkeypatch):
    from app.sandbox_cli import docker_client_environment
    monkeypatch.setenv("PROGRAMFILES", "E:/installed-programs")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-secret")
    monkeypatch.setenv("HTTP_PROXY", "http://synthetic-user:secret@proxy.invalid")
    monkeypatch.setenv("DOCKER_CONFIG", "C:/synthetic-private-config")
    environment = docker_client_environment()
    assert environment["PROGRAMFILES"] == "E:/installed-programs"
    assert not {"OPENAI_API_KEY", "HTTP_PROXY", "DOCKER_CONFIG"} & environment.keys()


def test_runtime_deadlines_and_bounded_logs(tmp_path):
    run = runtime_module().run_cli
    result = run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x'*200000); sys.stdout.flush()"],
                 threading.Event(), timeout=3)
    assert result["status"] == "passed" and len(result["stdout"]) == 12000
    result = run([sys.executable, "-c", "import time; time.sleep(30)"], threading.Event(), timeout=0.15)
    assert result["status"] == "timeout" and result["exitCode"] != 0
    cancelled = threading.Event(); cancelled.set()
    result = run([sys.executable, "-c", "import time; time.sleep(30)"], cancelled, timeout=3)
    assert result["status"] == "cancelled"


def test_export_transport_overflow_is_terminated_without_publishing_payload():
    result = runtime_module().run_cli([sys.executable, "-c", "print('x'*100000); import time; time.sleep(30)"],
        threading.Event(), timeout=3, output_limit=1024, strict_limit=True)
    assert result["status"] == "output_limit" and len(result["stdout"]) <= 1024


def test_exec_exit137_without_daemon_evidence_is_not_confirmed_oom():
    classify = runtime_module().execution_reason
    assert classify({"exitCode": 137, "status": "failed"}, {"OOMKilled": False, "Running": True}) == "process_killed"
    assert classify({"exitCode": 137, "status": "failed"}, {"OOMKilled": True, "Running": False}) == "oom_confirmed"
