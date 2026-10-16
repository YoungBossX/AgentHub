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


def select_scenarios(case_id=None):
    selected = [case for case in SCENARIOS if case_id is None or case.id == case_id]
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
