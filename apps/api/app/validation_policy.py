"""Local fixed-validation policy. Importing this module performs no I/O."""

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Literal
from uuid import uuid4


FRONTEND_PROFILE = "vite-build-smoke-v1"
BACKEND_PROFILE = "fastapi-contract-v1"
PROFILES = {FRONTEND_PROFILE: "demo-frontend", BACKEND_PROFILE: "demo-backend"}
RUNTIME_POLICY_ID = "container-validation-v1"
IMAGE_ID_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
CONTEXT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
RUNTIME_POLICY = {
    "id": RUNTIME_POLICY_ID, "platform": "linux/amd64", "user": "10001:10001",
    "init": True, "readOnly": True, "network": "none", "capDrop": "ALL",
    "noNewPrivileges": True, "seccomp": "builtin", "cpus": 1,
    "memory": 1024 * 1024 * 1024, "memorySwap": 1024 * 1024 * 1024, "pids": 128,
    "workTmpfs": 512 * 1024 * 1024, "tempTmpfs": 64 * 1024 * 1024,
    "stageSeconds": 60, "profileSeconds": 180, "managementSeconds": 10,
    "capacity": 1, "capacityWaitSeconds": 30, "logBytes": 12000,
    "environment": {"CI": "1", "NODE_ENV": "production", "LANG": "C.UTF-8",
                    "HOME": "/tmp", "TMPDIR": "/tmp", "PYTHONIOENCODING": "utf-8"},
}


class ValidationUnavailable(ValueError):
    """A fixed validation boundary or its prerequisites are unavailable."""


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def platform_root():
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class SourceSnapshot:
    target_id: str
    profile: str
    files: Mapping[str, str]
    contents: Mapping[str, bytes]
    source_fingerprint: str
    policy_inputs: Mapping[str, str]

    def __post_init__(self):
        for name in ("files", "contents", "policy_inputs"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


@dataclass(frozen=True)
class ValidationIdentity:
    task_run_id: str
    adapter_run_id: str
    execution_attempt_id: str
    generation_fingerprint: str


@dataclass(frozen=True)
class ImageBinding:
    image_id: str
    recipe_fingerprint: str
    platform: str
    context_name: str


@dataclass(frozen=True)
class ExecutionBinding:
    backend: Literal["native", "docker"]
    profile: str
    image: ImageBinding | None
    policy_fingerprint: str
    operation_id: str


@dataclass(frozen=True)
class FixedValidationRequest:
    snapshot: SourceSnapshot
    identity: ValidationIdentity
    execution: ExecutionBinding


@dataclass(frozen=True)
class ProfileExecutionResult:
    status: str
    commands: list[dict]
    execution: dict
    output_fingerprint: str | None = None


def resolve_backend_settings():
    from app.config import get_settings
    settings = get_settings()
    return {"backend": settings.validation_backend,
            "contextName": settings.validation_docker_context,
            "imageIds": {FRONTEND_PROFILE: settings.validation_frontend_image_id,
                         BACKEND_PROFILE: settings.validation_backend_image_id}}


def valid_image_id(value):
    return isinstance(value, str) and IMAGE_ID_PATTERN.fullmatch(value) is not None


def valid_context_name(value):
    return isinstance(value, str) and CONTEXT_PATTERN.fullmatch(value) is not None


def recipe_fingerprint(profile):
    if profile not in PROFILES:
        raise ValidationUnavailable("Unsupported automatic validation profile.")
    root = platform_root()
    control = "frontend-control.mjs" if profile == FRONTEND_PROFILE else "backend-control.py"
    dockerfile = "frontend.Dockerfile" if profile == FRONTEND_PROFILE else "backend.Dockerfile"
    names = [f"containers/validation/{name}" for name in ("recipe-lock.json", dockerfile, control)]
    names += (["pnpm-lock.yaml", "pnpm-workspace.yaml", "package.json", "apps/demo/package.json",
               "patches/braces@3.0.3.patch", "patches/monaco-editor@0.56.0.patch",
               "scripts/demo-validation-build.mjs", "scripts/demo-build-smoke.test.mjs"]
              if profile == FRONTEND_PROFILE else
              ["containers/validation/backend-requirements.lock", "scripts/demo-backend-check.py"])
    try:
        hashes = {name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for name in names}
    except OSError as exc:
        raise ValidationUnavailable("Trusted image recipe is unavailable.") from exc
    return digest({"profile": profile, "inputs": hashes})


def bind_execution(snapshot, identity, settings):
    """Freeze policy locally; never probe a CLI or the daemon here."""
    backend = settings.get("backend")
    if backend not in {"native", "docker"}:
        raise ValidationUnavailable("Unsupported validation backend.")
    if snapshot.profile not in PROFILES or PROFILES[snapshot.profile] != snapshot.target_id:
        raise ValidationUnavailable("Unsupported automatic validation profile.")
    image = None
    policy = {"backend": backend, "profile": snapshot.profile, "inputs": dict(snapshot.policy_inputs)}
    if backend == "docker":
        context = settings.get("contextName")
        if not valid_context_name(context):
            raise ValidationUnavailable("An explicit local Docker context is required.")
        image_id = settings.get("imageIds", {}).get(snapshot.profile)
        if not valid_image_id(image_id):
            raise ValidationUnavailable("An immutable validation image ID is required.")
        image = ImageBinding(image_id, recipe_fingerprint(snapshot.profile), "linux/amd64", context)
        policy.update(imageId=image.image_id, recipeFingerprint=image.recipe_fingerprint,
                      contextName=context, runtime=RUNTIME_POLICY)
        module_names = ("automatic_validation.py", "backend_validation.py", "container_runtime.py", "container_lifecycle.py",
                        "container_exports.py", "docker_validation.py", "sandbox_cli.py", "sandbox_prepare.py",
                        "validation_browser.py", "validation_process.py")
        policy["trustedModules"] = {name: hashlib.sha256((platform_root() / "apps/api/app" / name).read_bytes()).hexdigest()
                                    for name in module_names}
        if snapshot.profile == FRONTEND_PROFILE:
            from app.automatic_validation import validation_environment
            policy["nativeBrowserEnvironment"] = digest(validation_environment())
    return ExecutionBinding(backend, snapshot.profile, image, digest(policy), uuid4().hex)


def identity_for_run(run, task, *, launching=False):
    """Read frozen launch evidence; terminal runner/lock changes are irrelevant."""
    try:
        metrics = json.loads(run.metrics_json)
        if "taskRunExecutionAccessBinding" not in metrics:
            return None  # historical/unlaunched native callers retain legacy behavior
        binding = metrics["taskRunExecutionAccessBinding"]
        fields = {"taskRunId", "taskId", "sessionId", "queueEntryId", "accessMode", "runnerId", "executionAttemptId"}
        if (not isinstance(binding, dict) or set(binding) != fields or task is None
                or binding["taskRunId"] != run.id or binding["taskId"] != task.id or binding["sessionId"] != task.session_id
                or binding["accessMode"] not in {"readonly", "write"} or run.started_at is None
                or not isinstance(run.adapter_run_id, str) or not run.adapter_run_id
                or any(not isinstance(binding[k], str) or not 0 < len(binding[k]) <= 256 for k in fields)
                or launching and binding["runnerId"] != run.runner_id):
            raise ValidationUnavailable("Frozen validation launch binding is unavailable.")
        return ValidationIdentity(run.id, run.adapter_run_id, binding["executionAttemptId"], digest(binding))
    except (ValueError, TypeError, KeyError) as exc:
        raise ValidationUnavailable("Frozen validation launch binding is unavailable.") from exc


def execution_receipt(binding, identity):
    image = binding.image
    return {"backend": binding.backend, "operationId": binding.operation_id,
            "imageId": image.image_id if image else None, "recipeFingerprint": image.recipe_fingerprint if image else None,
            "runtimePolicyId": RUNTIME_POLICY_ID if image else "native-fixed-validation-v1",
            "generationFingerprint": identity.generation_fingerprint, "contextFingerprint": None, "commandsBackend": "not_run"}
