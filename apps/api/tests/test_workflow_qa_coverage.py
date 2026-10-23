"""Immutable review tests must exercise the actual v3 backend boundaries."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.workflow_suite import prepare_source, select_scenarios

TEST_FILE = "apps/demo-api/tests/test_contacts_boundaries.py"


@pytest.mark.parametrize("case", ["contacts-boundaries", "coordinated-contacts", "backend-repair"])
def test_only_v3_fixtures_seed_readonly_regression_tests(tmp_path, case):
    from app.workflow_suite import permitted
    scenario = select_scenarios(case)[0]
    root = prepare_source(tmp_path, scenario)
    assert (root / TEST_FILE).exists() is (case == "contacts-boundaries")
    assert not permitted(scenario, TEST_FILE)


@pytest.mark.parametrize("fault", [None, "case", "whitespace", "domain", "persistence"])
def test_seeded_tests_detect_actual_backend_defects(tmp_path, fault):
    scenario = select_scenarios("contacts-boundaries")[0]
    root = prepare_source(tmp_path, scenario)
    assert (root / TEST_FILE).is_file()
    path = root / "apps/demo-api/app/main.py"
    text = path.read_text(encoding="utf-8").replace("pass  # missing persistence", "_contacts.append(contact)")
    text = text.replace("contact.email == payload.email", "contact.email.casefold() == payload.email.casefold()")
    text = text.replace("    if any(", '    if not payload.name.strip():\n        raise HTTPException(status_code=422, detail="姓名不能为空白")\n    if any(')
    if fault == "case":
        text = text.replace("contact.email.casefold() == payload.email.casefold()", "contact.email == payload.email")
    if fault == "whitespace":
        text = text.replace('    if not payload.name.strip():\n        raise HTTPException(status_code=422, detail="姓名不能为空白")\n', "")
    if fault == "domain":
        text = text.replace("contact.email.casefold() == payload.email.casefold()", "contact.email.split('@')[0].casefold() == payload.email.split('@')[0].casefold()")
    if fault == "persistence":
        text = text.replace("_contacts.append(contact)", "pass  # missing persistence")
    path.write_text(text, encoding="utf-8")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-m", "pytest", "tests/test_contacts_boundaries.py", "-q", "-p", "no:cacheprovider",
        "--basetemp", str(tmp_path / "nested-temp")], cwd=root / "apps/demo-api", env=env, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == (0 if fault is None else 1), result.stdout + result.stderr
