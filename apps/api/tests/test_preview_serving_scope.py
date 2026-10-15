"""Real HTTP/module boundary checks against installed Vite, no mock server."""
import json
import os
import subprocess
import shutil
import time
from pathlib import Path

import httpx

from app.previews import SubprocessPreviewRunner, preview_command, reserve_preview_port

PLATFORM = Path(__file__).resolve().parents[3]


def vite_fs_url(path):
    # Match Vite's actual POSIX URL, not only the double-slash variant.
    return "/@fs/" + path.as_posix().lstrip("/")


def test_real_preview_denies_unrelated_protected_and_alias_reads(tmp_path):
    project = tmp_path / "workspace/apps/demo"
    project.mkdir(parents=True)
    # Workspace auto-detection would expose this sibling with the old profile.
    (tmp_path / "workspace/pnpm-workspace.yaml").write_text("packages: ['apps/*']\n")
    unrelated = tmp_path / "workspace/apps/api/main.py"
    unrelated.parent.mkdir()
    unrelated.write_text("PRIVATE_BACKEND_MARKER")
    unrelated_css = unrelated.with_suffix(".css")
    unrelated_css.write_text("/* PRIVATE_BACKEND_CSS */ body { color: red; }")
    (project / "package.json").write_text(json.dumps({"type": "module", "scripts": {"dev": "vite"}}))
    (project / "index.html").write_text('<div id="root"></div><script type="module" src="/src/main.tsx"></script>')
    (project / "src").mkdir()
    (project / "src/main.tsx").write_text('import React from "react"; import { createRoot } from "react-dom/client"; import "./style.css"; createRoot(document.getElementById("root")).render(<h1>Preview ready</h1>)')
    (project / "src/style.css").write_text('@import "./base.css"; h1 { font-size: 24px; }')
    (project / "src/base.css").write_text('body { margin: 0; }')
    (project / "node_modules").symlink_to(PLATFORM / "apps/demo/node_modules", target_is_directory=True)
    workspace_dependencies = tmp_path / "workspace/node_modules"
    workspace_dependencies.symlink_to(PLATFORM / "node_modules", target_is_directory=True)
    (project / ".env").write_text("PRIVATE_ENV_MARKER")
    (project / "secrets").mkdir()
    (project / "secrets/token.txt").write_text("PRIVATE_SECRET_MARKER")
    (project / "public").mkdir()
    (project / "public/.env").write_text("PRIVATE_PUBLIC_ENV_MARKER")
    (project / "src/denied.txt").write_text("PRIVATE_TARGET_DENIED_MARKER")
    alias = project / "src/alias.txt"
    alias.symlink_to(unrelated)
    hardlink = project / "src/hardlink.txt"
    os.link(unrelated, hardlink)
    (project / "src/escape.ts").write_text(f'import value from {json.dumps(unrelated.as_posix() + "?raw")}; export default value;')
    (project / "src/escape.css").write_text('@import "../../api/main.css";')
    runner = SubprocessPreviewRunner()
    port = reserve_preview_port()
    process = runner.start_bounded(preview_command(port), project, denied_paths=["src/denied.txt"])
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10, trust_env=False) as client:
            for _ in range(100):
                assert runner.diagnostics(process.pid).running, runner.diagnostics(process.pid).output_tail
                try:
                    if client.get("/").status_code == 200: break
                except httpx.ConnectError:
                    pass
                time.sleep(0.1)
            else: raise AssertionError("Preview did not start within its startup budget.")
            main = client.get("/src/main.tsx")
            assert main.status_code == 200, main.text[:2000]
            for url in [vite_fs_url(unrelated), f"/@fs/{unrelated.as_posix()}", "/.env", "/secrets/token.txt", "/public/.env", "/src/denied.txt",
                        "/src/alias.txt", "/src/hardlink.txt", f"/@fs/{unrelated.as_posix()}?raw", "/%2eenv"]:
                response = client.get(url)
                assert response.status_code == 403, (url, response.status_code)
                assert "PRIVATE_" not in response.text
            # The transform may emit an import, but loading that module cannot
            # acquire a new filesystem permission through Vite safeModulePaths.
            client.get("/src/escape.ts")
            escaped = client.get(vite_fs_url(unrelated) + "?raw")
            assert escaped.status_code == 403 and "PRIVATE_BACKEND_MARKER" not in escaped.text
            css = client.get("/src/escape.css")
            assert css.status_code >= 400 and "PRIVATE_BACKEND_CSS" not in css.text
            assert client.get("/src/style.css").status_code == 200
            # Direct React modules and Vite's runtime still load normally.
            assert client.get("/@vite/client").status_code == 200
            react = PLATFORM / "apps/demo/node_modules/react/index.js"
            assert client.get(vite_fs_url(react)).status_code == 200
            browser = subprocess.run([shutil.which("node"), "--input-type=module", "-e", """
import { chromium } from 'playwright';
const browser = await chromium.launch({headless:true, chromiumSandbox:true,
  ...(process.env.AGENTHUB_VALIDATION_BROWSER_CHANNEL === 'chromium' ? {} :
    {channel:process.env.AGENTHUB_VALIDATION_BROWSER_CHANNEL || (process.platform==='win32'?'msedge':undefined)}), timeout:30000});
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => { if(errors.length<20) errors.push(error.message); });
  page.on('response', response => { if(response.status()>=400 && errors.length<20) errors.push(`${response.status()} ${response.url()}`); });
  try {
    await page.goto(process.argv[1]);
    await page.getByRole('heading', {name:'Preview ready',exact:true}).waitFor({timeout:10000});
    if(await page.locator('h1').evaluate(el=>getComputedStyle(el).fontSize)!=='24px') throw Error('Styles failed');
  } catch(error) {
    console.error('Preview browser diagnostics:', JSON.stringify(errors));
    throw error;
  }
  console.log('React preview rendered with scoped dependencies and CSS imports');
} finally { await browser.close(); }
""", str(client.base_url)], cwd=PLATFORM, capture_output=True, text=True, encoding="utf-8", timeout=45)
            assert browser.returncode == 0, browser.stderr + "\nVite: " + runner.diagnostics(process.pid).output_tail
    finally:
        runner.close()
        # Explicitly unlink the known installed dependency link before pytest cleanup.
        (project / "node_modules").unlink()
        workspace_dependencies.unlink()
