import base64
import hashlib
import importlib
import json

import pytest


SOURCE = "f" * 64
INPUTS = {"apps/demo/src/App.tsx": "a" * 64}


def envelope(path="index.html", raw=b"<div/>"):
    return {"schemaVersion": "agenthub.container_export.v1", "sourceFingerprint": SOURCE,
            "sourceFiles": dict(INPUTS), "files": [{"path": path, "sha256": hashlib.sha256(raw).hexdigest(),
                                                     "base64": base64.b64encode(raw).decode()}]}


def materialize(value, destination, **kwargs):
    raw = value if isinstance(value, bytes) else json.dumps(value).encode()
    return importlib.import_module("app.container_exports").materialize_export(
        raw, destination, SOURCE, expected_files=INPUTS, **kwargs)


@pytest.mark.parametrize("mutation", ["duplicate_json", "nonfinite", "bad_utf8", "hash", "base64", "source",
                                    "schema", "extra", "count", "transport", "file_size", "total_size"])
def test_export_rejects_invalid_envelope_or_budget(tmp_path, mutation):
    value = envelope()
    if mutation == "duplicate_json": value = json.dumps(value).replace('"files":', '"files":[],"files":').encode()
    if mutation == "nonfinite": value = json.dumps(value).replace('"files":', '"extra":NaN,"files":').encode()
    if mutation == "bad_utf8": value = b'\xff'
    if mutation == "hash": value["files"][0]["sha256"] = "0" * 64
    if mutation == "base64": value["files"][0]["base64"] = "!!bad!!"
    if mutation == "source": value["sourceFingerprint"] = "0" * 64
    if mutation == "schema": value["schemaVersion"] = "untrusted.v1"
    if mutation == "extra": value["files"][0]["symlink"] = "/host"
    if mutation == "count": value["files"] = [envelope(str(i))["files"][0] for i in range(513)]
    if mutation == "transport": value = b" " * (48 * 1024 * 1024 + 1)
    if mutation == "file_size": value = envelope(raw=b"x" * (5 * 1024 * 1024 + 1))
    if mutation == "total_size": value["files"] = [envelope(str(i), b"x" * (5 * 1024 * 1024))["files"][0] for i in range(7)]
    output = tmp_path / "output"
    with pytest.raises(ValueError): materialize(value, output)
    assert not output.exists()


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/drive", "x:y", "x\\y", "a//b", "a/./b",
    "a/../b", "a\x00b", "CON", "con.txt", "a/LPT9.js", "a.", "a ", "e\u0301.html", ".git/config", ".env",
    "node_modules/x", "/".join(["a"] * 17), "a" * 121, "/".join(["a" * 100] * 3)])
def test_export_paths_are_portable_and_exclusive(tmp_path, path):
    with pytest.raises(ValueError): materialize(envelope(path), tmp_path / "output")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("other", ["INDEX.html", "index.html", "index.html/nested"])
def test_duplicate_case_and_file_directory_collisions_are_refused(tmp_path, other):
    value = envelope()
    value["files"].append(envelope(other)["files"][0])
    with pytest.raises(ValueError): materialize(value, tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("paths", [
    ("Assets/a.js", "assets/b.js"),
    ("assets/Icons/a.js", "assets/icons/b.js"),
    ("Assets/a.js", "assets/nested/b.js"),
    ("assets/nested/b.js", "Assets/a.js"),
    ("assets/nested/a.js", "ASSETS"),
])
def test_directory_case_aliases_are_rejected_before_any_output(tmp_path, paths):
    value = envelope()
    value["files"] = [envelope(path)["files"][0] for path in paths]
    with pytest.raises(ValueError, match="collision"):
        materialize(value, tmp_path / "output")
    assert list(tmp_path.iterdir()) == []


def test_files_may_share_an_exactly_spelled_directory(tmp_path):
    value = envelope()
    value["files"] = [envelope(path)["files"][0] for path in ("Assets/a.js", "Assets/nested/b.js")]
    materialize(value, tmp_path / "output")
    assert (tmp_path / "output/Assets/a.js").read_bytes() == b"<div/>"
    assert (tmp_path / "output/Assets/nested/b.js").read_bytes() == b"<div/>"


def test_export_source_hashes_cover_exact_copied_inputs(tmp_path):
    for inputs in ({}, {**INPUTS, "extra": "b" * 64}, {"apps/demo/src/App.tsx": "b" * 64}):
        value = envelope()
        value["sourceFiles"] = inputs
        with pytest.raises(ValueError): materialize(value, tmp_path / "output")


def test_valid_export_is_exclusive_and_hashes_actual_bytes(tmp_path):
    output = tmp_path / "output"
    fingerprint = materialize(envelope("assets/中文.js", b"export default 1"), output)
    assert len(fingerprint) == 64
    assert (output / "assets/中文.js").read_bytes() == b"export default 1"
    with pytest.raises((OSError, ValueError)): materialize(envelope(), output)
    assert not (output / "index.html").exists()


def test_output_below_link_never_writes_outside_server_directory(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises((OSError, ValueError)): materialize(envelope(), link / "output")
    assert list(actual.iterdir()) == []
