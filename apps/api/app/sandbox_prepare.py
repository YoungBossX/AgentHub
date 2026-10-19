"""Explicit operator image preparation using a clean, enumerated build context."""

import hashlib
import json
from pathlib import Path
import shutil
import stat
import threading

from app.container_runtime import run_cli
from app.sandbox_cli import docker_endpoint_arguments, docker_json, inspect_context
from app.validation_policy import (
    BACKEND_PROFILE, FRONTEND_PROFILE, PROFILES, ValidationUnavailable,
    platform_root, recipe_fingerprint, resolve_backend_settings, valid_context_name, valid_image_id,
)


def context_inputs(profile):
    common = ["containers/validation/recipe-lock.json"]
    if profile == FRONTEND_PROFILE:
        return common + ["containers/validation/frontend.Dockerfile", "containers/validation/frontend-control.mjs",
            "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "apps/demo/package.json",
            "patches/braces@3.0.3.patch", "patches/monaco-editor@0.56.0.patch",
            "scripts/demo-validation-build.mjs", "scripts/demo-build-smoke.test.mjs"]
    if profile == BACKEND_PROFILE:
        return common + ["containers/validation/backend.Dockerfile", "containers/validation/backend-control.py",
                         "containers/validation/backend-requirements.lock", "scripts/demo-backend-check.py"]
    raise ValidationUnavailable("Unsupported automatic validation profile.")


def trusted_bytes(relative):
    root = platform_root()
    path = root / relative
    for parent in (path, *path.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValidationUnavailable("Linked trusted recipe input is unavailable.")
        if parent == root: break
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 5 * 1024 * 1024:
        raise ValidationUnavailable("Trusted recipe file is unavailable.")
    return path.read_bytes().replace(b"\r\n", b"\n")


def build_context(destination, profile):
    destination.mkdir(mode=0o700)
    hashes = {}
    for relative in context_inputs(profile):
        raw = trusted_bytes(relative)
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream: stream.write(raw)
        hashes[relative] = hashlib.sha256(raw).hexdigest()
    return hashes


def validate_output(output):
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValidationUnavailable("Image receipts require a new external absolute directory.")
    for parent in output.parents:
        if not parent.exists():
            raise ValidationUnavailable("Image receipt parent must already exist.")
        info = parent.lstat()
        if (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
                or (parent / ".git").exists()):
            raise ValidationUnavailable("Image receipts cannot be inside managed or linked directories.")
    if output.resolve() != output:
        raise ValidationUnavailable("Image receipt directory must be canonical.")


def inspect_built_image(executable, context_name, image_id, profile, recipe, *, endpoint):
    if not valid_image_id(image_id):
        raise ValidationUnavailable("Build did not produce an immutable local image ID.")
    images = docker_json(executable, context_name, "image", "inspect", image_id, endpoint=endpoint)
    try:
        image = images[0]
        config = image["Config"]
        labels = config.get("Labels") or {}
        if (len(images) != 1 or image["Id"] != image_id or image["Os"] != "linux" or image["Architecture"] != "amd64"
                or config["User"] != "10001:10001" or config["Entrypoint"] != ["/opt/agenthub/control"]
                or config["Cmd"] != ["hold"] or labels.get("io.agenthub.validation.profile") != profile
                or labels.get("io.agenthub.validation.recipe") != recipe):
            raise ValidationUnavailable("Built image metadata does not match the approved recipe.")
    except (KeyError, IndexError, TypeError) as exc:
        raise ValidationUnavailable("Built image metadata is incomplete.") from exc
    return {"imageId": image_id, "recipeFingerprint": recipe, "platform": "linux/amd64", "contextName": context_name}


def prepare_images(output_dir: Path):
    validate_output(output_dir)
    settings = resolve_backend_settings()
    context_name = settings["contextName"]
    if not valid_context_name(context_name):
        raise ValidationUnavailable("An explicit local Docker context is required.")
    executable = shutil.which("docker")
    if not executable:
        raise ValidationUnavailable("Docker is unavailable; install/start it separately.")
    context = inspect_context(executable, context_name)
    output_dir.mkdir(mode=0o700)
    receipt = {"schemaVersion": "agenthub.container_images.v1", "profiles": {}, "inputs": {},
               "contextFingerprint": context["contextFingerprint"],
               "recipeLock": json.loads(trusted_bytes("containers/validation/recipe-lock.json")),
               "runtimeIsolationVerified": False}
    for profile in PROFILES:
        recipe = recipe_fingerprint(profile)
        build_dir = output_dir / profile
        manifest = build_context(build_dir, profile)
        dockerfile = "frontend.Dockerfile" if profile == FRONTEND_PROFILE else "backend.Dockerfile"
        iidfile = output_dir / (profile + ".image-id")
        # Network/download is confined to this explicitly invoked preparation step.
        args = ["buildx", "build", "--load", "--platform", "linux/amd64", "--pull",
                "--file", str(build_dir / "containers/validation" / dockerfile),
                "--build-arg", "AGENTHUB_RECIPE=" + recipe, "--iidfile", str(iidfile), str(build_dir)]
        with docker_endpoint_arguments(executable, context["endpoint"]) as prefix:
            result = run_cli([*prefix, *args], threading.Event(), timeout=900, output_limit=12000)
        with (output_dir / (profile + ".build.log")).open("xb") as stream:
            stream.write((result["stdout"] + result["stderr"])[-12000:])
        if result["status"] != "passed":
            raise ValidationUnavailable("Image preparation failed; external bounded log retained.")
        image_id = iidfile.read_text(encoding="utf-8").strip()
        # Recheck the daemon identity after every build before accepting its ID.
        if inspect_context(executable, context_name)["contextFingerprint"] != context["contextFingerprint"]:
            raise ValidationUnavailable("Docker context changed during preparation.")
        receipt["profiles"][profile] = inspect_built_image(executable, context_name, image_id, profile, recipe,
                                                          endpoint=context["endpoint"])
        receipt["inputs"][profile] = manifest
    with (output_dir / "images.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=True, indent=2)
        stream.write("\n")
    return receipt
