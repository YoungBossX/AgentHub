"""The same native trusted browser harness for native and verified Docker output."""

import hashlib
import json
from pathlib import Path
import shutil
import stat

from app.container_exports import assert_canonical_directory, portable_path
from app.requirement_validation import VERSION, parse_browser_result
from app.validation_policy import ValidationUnavailable, digest, platform_root


def output_fingerprint(directory):
    directory = assert_canonical_directory(directory)
    pending, files, total, seen = [directory], {}, 0, 0
    while pending:
        path = pending.pop(); seen += 1
        if seen > 1024: raise ValidationUnavailable("Browser input entry budget exceeded.")
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValidationUnavailable("Browser input contains a link.")
        if stat.S_ISDIR(info.st_mode): pending.extend(path.iterdir()); continue
        relative = portable_path(path.relative_to(directory).as_posix())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 5 * 1024 * 1024:
            raise ValidationUnavailable("Browser input is not a bounded regular file.")
        raw = path.read_bytes(); total += len(raw)
        if len(raw) > 5 * 1024 * 1024 or total > 32 * 1024 * 1024 or len(files) >= 512:
            raise ValidationUnavailable("Browser input byte/file budget exceeded.")
        files[relative] = hashlib.sha256(raw).hexdigest()
    return digest(files)


def run_browser_validation(output_dir: Path, contract: dict, cancelled, *, runner=None):
    from app.automatic_validation import run_command, validation_environment
    runner = runner or run_command
    before = output_fingerprint(output_dir)
    execution = {"backend": "native", "inputArtifactFingerprint": before}
    node = shutil.which("node")
    if not node:
        return {"schemaVersion": VERSION, "status": "unavailable", "contract": contract, "checks": [],
                "reason": "Installed Node/browser runtime is unavailable.", "execution": execution}
    env = validation_environment()
    env.update(AGENTHUB_VALIDATION_OUTPUT=str(output_dir), AGENTHUB_REQUIREMENT_CONTRACT=json.dumps(contract, ensure_ascii=True))
    result = runner([node, str(platform_root() / "scripts/demo-requirement-check.mjs")], output_dir.parent, env, cancelled)
    functional = parse_browser_result(result, contract)
    functional["execution"] = execution
    if output_fingerprint(output_dir) != before:
        functional.update(status="unavailable", checks=[], reason="Browser input changed during validation.")
    return functional
