"""Operator-only container utilities. No database or application startup imports."""

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

from app.validation_policy import (
    PROFILES, ValidationUnavailable, digest, recipe_fingerprint,
    resolve_backend_settings, valid_context_name, valid_image_id,
)

SCHEMA = "agenthub.container_doctor.v1"
DOCKER_ENV_KEYS = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE",
                   "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "TEMP", "TMP", "LANG", "LC_ALL"}


def docker_client_environment():
    return {key: value for key, value in os.environ.items() if key.upper() in DOCKER_ENV_KEYS}


def context_is_local(endpoint):
    if not isinstance(endpoint, str) or any(ord(c) < 32 for c in endpoint):
        return False
    value = urlsplit(endpoint)
    if value.scheme == "unix":
        return not value.netloc and value.path.startswith("/") and not value.query and not value.fragment
    return (endpoint.startswith("npipe:////./pipe/") and len(endpoint) > len("npipe:////./pipe/")
            and not any(c in endpoint[len("npipe:////./pipe/"):] for c in "/\\?#"))


@contextmanager
def docker_endpoint_arguments(executable, endpoint):
    """Pin a local transport and keep user proxies/auth out of daemon operations."""
    if not context_is_local(endpoint):
        raise ValidationUnavailable("context_refused")
    with tempfile.TemporaryDirectory(prefix="agenthub-docker-client-") as directory:
        path = Path(directory)
        path.chmod(0o700)
        config = path / "config.json"
        with config.open("x", encoding="utf-8") as stream:
            stream.write("{}")
        config.chmod(0o600)
        yield [executable, "--config", directory, "--host", endpoint]


def docker_json(executable, context_name, *args, endpoint=None):
    def invoke(argv):
        return subprocess.run(argv, shell=False, env=docker_client_environment(), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
    if endpoint is None:
        # The only command allowed to read the user's context store is local
        # metadata resolution; it cannot contact or mutate a daemon.
        if args != ("context", "inspect", context_name):
            raise ValidationUnavailable("An inspected local endpoint is required.")
        result = invoke([executable, "--context", context_name, *args])
    else:
        with docker_endpoint_arguments(executable, endpoint) as prefix:
            result = invoke([*prefix, *args])
    if result.returncode != 0 or len(result.stdout) > 1024 * 1024:
        raise ValidationUnavailable("Docker metadata is unavailable.")
    return json.loads(result.stdout)


def _inspect_context_metadata(executable, context_name):
    if not valid_context_name(context_name) or any(key.upper().startswith("DOCKER_") for key in os.environ):
        raise ValidationUnavailable("context_refused")
    contexts = docker_json(executable, context_name, "context", "inspect", context_name)
    context = contexts[0]
    endpoint = context["Endpoints"]["docker"]["Host"]
    if len(contexts) != 1 or context["Name"] != context_name or not context_is_local(endpoint):
        raise ValidationUnavailable("context_refused")
    docker_json(executable, context_name, "version", "--format", "{{json .}}", endpoint=endpoint)
    info = docker_json(executable, context_name, "info", "--format", "{{json .}}", endpoint=endpoint)
    if info["OSType"] != "linux" or info["Architecture"] not in {"amd64", "x86_64"}:
        raise ValidationUnavailable("platform_unsupported")
    if (not all(info.get(key) is True for key in ("MemoryLimit", "SwapLimit", "PidsLimit"))
            or "name=seccomp,profile=builtin" not in info.get("SecurityOptions", []) or not info.get("ID")):
        raise ValidationUnavailable("capability_unsupported")
    return {"contextFingerprint": digest({"context": context_name, "endpoint": endpoint, "daemon": info["ID"]}),
            "daemonFingerprint": digest({"daemon": info["ID"]}), "endpoint": endpoint}


def inspect_context(executable, context_name):
    try:
        return _inspect_context_metadata(executable, context_name)
    except ValidationUnavailable:
        raise
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError) as exc:
        raise ValidationUnavailable("metadata_unavailable") from exc


def doctor(*, context_name: str | None, image_ids: dict[str, str]) -> dict:
    report = {"schemaVersion": SCHEMA, "status": "unavailable", "reasonCodes": [],
              "checks": [], "runtimeIsolationVerified": False}
    def stop(status, reason):
        report.update(status=status, reasonCodes=[reason])
        return report
    if not valid_context_name(context_name):
        return stop("unavailable", "context_missing")
    if set(image_ids) != set(PROFILES) or not all(valid_image_id(v) for v in image_ids.values()):
        return stop("unavailable", "image_missing")
    if any(key.upper().startswith("DOCKER_") for key in os.environ):
        return stop("unsupported", "context_refused")
    executable = shutil.which("docker")
    if not executable:
        return stop("unavailable", "docker_missing")
    try:
        context = inspect_context(executable, context_name)
        endpoint = context["endpoint"]
        report["checks"].append({"id": "local_context", "status": "passed"})
        report["checks"].append({"id": "daemon_capabilities", "status": "passed"})
        for profile, image_id in image_ids.items():
            images = docker_json(executable, context_name, "image", "inspect", image_id, endpoint=endpoint)
            image = images[0]
            config = image["Config"]
            labels = config.get("Labels") or {}
            if (len(images) != 1 or image["Id"] != image_id or image["Os"] != "linux"
                    or image["Architecture"] != "amd64" or config["User"] != "10001:10001"
                    or config["Entrypoint"] != ["/opt/agenthub/control"] or config["Cmd"] != ["hold"]
                    or labels.get("io.agenthub.validation.profile") != profile
                    or labels.get("io.agenthub.validation.recipe") != recipe_fingerprint(profile)):
                return stop("unsupported", "image_refused")
            report["checks"].append({"id": profile, "status": "passed"})
        # Fingerprint endpoint/daemon identity; never publish client paths/configuration.
        report["contextFingerprint"] = context["contextFingerprint"]
        report["status"] = "metadata_ready"
        return report
    except ValidationUnavailable as exc:
        reason = str(exc)
        return stop("unsupported" if reason in {"context_refused", "platform_unsupported", "capability_unsupported"}
                    else "unavailable", reason if reason in {"context_refused", "platform_unsupported", "capability_unsupported"}
                    else "metadata_unavailable")
    except (OSError, ValueError, subprocess.SubprocessError, KeyError, IndexError, TypeError):
        return stop("unavailable", "metadata_unavailable")


def main(argv=None):
    parser = argparse.ArgumentParser(description="AgentHub fixed validation container utilities")
    parser.add_argument("command", choices=["doctor", "prepare"])
    parser.add_argument("--output", type=str)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        from pathlib import Path
        from app.sandbox_prepare import prepare_images
        if not args.output:
            parser.error("prepare requires --output <new external absolute directory>")
        try:
            report = prepare_images(Path(args.output))
        except (OSError, ValueError, subprocess.SubprocessError):
            print(json.dumps({"schemaVersion": "agenthub.container_images.v1", "status": "unavailable",
                              "reasonCode": "preparation_unavailable", "runtimeIsolationVerified": False}))
            return 1
        print(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
        return 0
    try:
        settings = resolve_backend_settings()
        report = doctor(context_name=settings["contextName"], image_ids=settings["imageIds"])
    except ValueError:
        report = {"schemaVersion": SCHEMA, "status": "unavailable", "reasonCodes": ["configuration_invalid"],
                  "checks": [], "runtimeIsolationVerified": False}
    print(json.dumps(report, ensure_ascii=True, separators=(",", ":")))
    return 0 if report["status"] == "metadata_ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
