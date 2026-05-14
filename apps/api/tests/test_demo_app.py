from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_ROOT = REPO_ROOT / "apps" / "demo"


def test_vite_react_demo_app_has_deterministic_mutation_targets() -> None:
    assert (DEMO_ROOT / "package.json").exists()
    assert (DEMO_ROOT / "index.html").exists()

    app_source = (DEMO_ROOT / "src" / "App.tsx").read_text()
    assert 'data-agenthub-target="login-page-slot"' in app_source
    assert 'data-agenthub-target="primary-action-button"' in app_source
    assert "Build the login page" in app_source


def test_demo_app_documents_setup_and_start_commands() -> None:
    readme = (DEMO_ROOT / "README.md").read_text()

    assert "pnpm demo:setup" in readme
    assert "pnpm --filter @agenthub/demo dev --host 127.0.0.1 --port <port>" in readme
    assert "apps/demo" in readme
