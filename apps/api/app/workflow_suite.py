"""Immutable, built-in workflow scenarios. Expectations are never model output."""

from dataclasses import dataclass
from pathlib import Path
import shutil

from app.external_benchmark import git
from app.worktrees import repo_root


@dataclass(frozen=True)
class Scenario:
    id: str
    prompts: tuple[str, ...]
    headings: tuple[str, ...] = ()
    backend: bool = False
    frontend: bool = False
    integration: bool = False
    multi_file: bool = False
    fault_injection: bool = False
    contacts_contract: str = "contacts-create-v1"


RULE = "Keep all changes inside the assigned demo target. Do not install dependencies, edit configuration, or execute project tests. Preserve existing API contracts."
SCENARIOS = (
    Scenario("backend-repair", (
        "@backend @qa Fix apps/demo-api/app/main.py: GET /health must return status 'ok' and service 'agenthub-demo-api'. Preserve all existing contacts/CORS/OpenAPI behavior. Review the actual diff.",
    ), backend=True),
    Scenario("multi-file", (
        "@frontend @qa In the demo app, repair the heading implementation across apps/demo/src/App.tsx and apps/demo/src/workflow-copy.ts. Keep the title defined in the separate workflow-copy module and imported by App.tsx. Render exactly 'Workflow ready' in h1#demo-heading, with no broken suffix. Both source files need fixes. Preserve the other demo UI and review the diff.",
    ), ("Workflow ready",), frontend=True, multi_file=True),
    Scenario("coordinated-contacts", (
        "@backend @frontend @qa In the demo app, fix contact creation in apps/demo-api/app/main.py so POST /contacts persists a valid new contact and subsequent GET /contacts returns it, preserving validation, duplicate rejection and health. In the demo frontend add a contact form with labels 'Name' and 'Email' and a button 'Create contact'. Fetch GET /api/contacts on load and POST /api/contacts on submit, then refresh the list. Show names in a list with aria-label='Contacts'; render each contact name as visible text. Do not hardcode seed or submitted contacts. Use relative /api/contacts (the trusted evaluation transport supplies the backend). Preserve h1#demo-heading, avoid external requests, and support desktop and 390px width. Review both actual diffs. "
        "Require Name and a valid Email before submitting. For duplicate-email rejection and a temporary server failure, show a visible accessible alert and keep the entered Name/Email and existing list unchanged. Allow a subsequent successful retry without reloading; clear the error after success and persist the result across reload. These are the fixed contacts-resilience-v2 acceptance requirements.",
    ), backend=True, frontend=True, integration=True, contacts_contract="contacts-resilience-v2"),
    Scenario("follow-up", (
        "@frontend @qa In the demo app change only h1#demo-heading to exactly 'First revision'. Preserve the existing login slot, button and styles. Review the diff.",
        "@frontend @qa In the same demo app change h1#demo-heading again to exactly 'Second revision'. Preserve the prior unrelated UI and review this follow-up diff.",
    ), ("First revision", "Second revision"), frontend=True),
    Scenario("retry-recovery", (
        "@frontend @qa In the demo app change h1#demo-heading to exactly 'Recovered workflow'. Preserve unrelated UI and review the diff.",
    ), ("Recovered workflow",), frontend=True, fault_injection=True),
)


CONTACTS_BOUNDARIES = Scenario('contacts-boundaries', (
    '@backend @frontend @qa 请完善演示应用的中文联系人功能，仅修改 apps/demo-api/app/main.py 和 apps/demo/src/App.tsx。'
    '后端 POST /contacts 保存联系人，GET /contacts 返回已保存结果；完整邮箱忽略大小写判重并返回409，不同域名允许创建。'
    '姓名仅含ASCII、制表符或全角空格时返回422且不写入。保留现有健康检查、API和CORS。'
    '前端使用相对 /api/contacts，标签为姓名、邮箱，按钮为新增联系人，列表 aria-label 为联系人列表；保留 h1#demo-heading。'
    '姓名必填且不能仅含空白，邮箱格式有效；重复或临时POST失败时以可访问的中文alert提示，保留表单与列表，允许重试。'
    'POST确认201后立即按真实id保留联系人并清空表单；随后GET刷新失败仍显示已保存结果，用中性role=status中文说明已保存但刷新失败。'
    '成功后清除旧错误，刷新页面后保持数据；适配桌面与390px窄屏，无外部请求。QA只读审查双方真实Diff。',
), backend=True, frontend=True, integration=True, contacts_contract='contacts-boundaries-v3')


# Trusted fixture-only regression material. Agents may read, never edit/run it.
# Presence is not an execution receipt; fixed independent acceptance still runs.
CONTACTS_BOUNDARY_TESTS = '''"""中文联系人边界回归；由平台固定提供，QA仅可读取。"""
import pytest
from fastapi.testclient import TestClient
from app.main import app, reset_contacts_for_tests


@pytest.fixture
def api():
    reset_contacts_for_tests()
    with TestClient(app) as client:
        yield client
    reset_contacts_for_tests()


@pytest.mark.parametrize("email", ["ADA@example.com", "ada@EXAMPLE.COM", "ADA@EXAMPLE.COM"])
def test_full_email_case_insensitive_duplicate_keeps_records(api, email):
    before = api.get("/contacts").json()
    assert api.post("/contacts", json={"name": "重复联系人", "email": email}).status_code == 409
    assert api.get("/contacts").json() == before


def test_new_contact_persists_and_case_variant_is_duplicate(api):
    payload = {"name": "中文新联系人", "email": "Unique.Person@Example.COM"}
    before = api.get("/contacts").json()
    response = api.post("/contacts", json=payload)
    assert response.status_code == 201
    stable = api.get("/contacts").json()
    assert stable == before + [response.json()]
    assert api.post("/contacts", json={**payload, "email": "unique.person@example.com"}).status_code == 409
    assert api.get("/contacts").json() == stable


def test_same_local_part_different_domain_is_distinct(api):
    before = api.get("/contacts").json()
    response = api.post("/contacts", json={"name": "不同域名联系人", "email": "ada@other.example.com"})
    assert response.status_code == 201
    assert api.get("/contacts").json() == before + [response.json()]


@pytest.mark.parametrize("name", ["   ", "\\t", "\\u3000", " \\t\\u3000 "])
def test_whitespace_name_is_422_and_never_writes(api, name):
    before = api.get("/contacts").json()
    response = api.post("/contacts", json={"name": name, "email": "blank@example.com"})
    assert response.status_code == 422
    assert api.get("/contacts").json() == before
'''


def select_scenarios(case_id=None):
    candidates = SCENARIOS if case_id is None else (*SCENARIOS, CONTACTS_BOUNDARIES)
    selected = [case for case in candidates if case_id is None or case.id == case_id]
    if not selected:
        raise ValueError("Unknown workflow scenario.")
    return selected


def prepare_source(directory: Path, scenario: Scenario):
    """Fresh fixture-only Git baseline; never modify or commit the checkout."""
    root = directory / "target"
    root.mkdir(parents=True)
    platform = repo_root()
    for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml"):
        shutil.copyfile(platform / name, root / name)
    for name in ("demo", "demo-api"):
        shutil.copytree(platform / "apps" / name, root / "apps" / name,
                        ignore=shutil.ignore_patterns("node_modules", "dist", "__pycache__", ".pytest_cache", ".env*"))
    if scenario.contacts_contract == "contacts-boundaries-v3":
        (root / "apps/demo-api/tests/test_contacts_boundaries.py").write_text(CONTACTS_BOUNDARY_TESTS, encoding="utf-8")
    if scenario.id == "backend-repair":
        path = root / "apps/demo-api/app/main.py"
        path.write_text(path.read_text(encoding="utf-8").replace('status="ok"', 'status="broken"'), encoding="utf-8")
    if scenario.integration:
        path = root / "apps/demo-api/app/main.py"
        path.write_text(path.read_text(encoding="utf-8").replace("_contacts.append(contact)", "pass  # missing persistence"), encoding="utf-8")
    if scenario.multi_file:
        path = root / "apps/demo/src/App.tsx"
        original = path.read_text(encoding="utf-8")
        import re
        original = re.sub(r'(<h1 id="demo-heading">).*?(</h1>)', r'\1{workflowTitle} broken\2', original)
        path.write_text("import { workflowTitle } from './workflow-copy'\n" + original, encoding="utf-8")
        (path.parent / "workflow-copy.ts").write_text('export const workflowTitle = "Broken title"\n', encoding="utf-8")
    git(root, "init", "-b", "main")
    git(root, "add", ".")
    git(root, "-c", "user.name=AgentHub Workflow Evaluation", "-c", "user.email=workflow@example.invalid",
        "commit", "-m", "Frozen workflow fixture")
    return root


def permitted(scenario, path):
    return (scenario.frontend and path.startswith("apps/demo/src/")) or (
        scenario.backend and path.startswith("apps/demo-api/app/") and path.endswith(".py"))
