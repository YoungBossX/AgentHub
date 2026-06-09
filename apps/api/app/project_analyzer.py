import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.external_workspaces import DEFAULT_EXTERNAL_DENIED_PATHS
from app.project_profiles import ProjectProfile, build_project_profile


PROJECT_TYPES = {
    "vite-react",
    "nextjs",
    "fastapi",
    "node-api",
    "python-package",
    "unknown",
}


@dataclass(frozen=True)
class ProjectAnalysisResult:
    root_path: str
    project_type: str
    detected_framework: str
    package_manager: str
    allowed_paths: tuple[str, ...]
    denied_paths: tuple[str, ...]
    dev_command: Optional[str]
    test_command: Optional[str]
    check_command: Optional[str]
    build_command: Optional[str]
    preview_command: Optional[str]
    analysis_status: str
    analysis_warnings: tuple[str, ...]
    confidence: str
    project_profile: ProjectProfile


def analyze_external_project(root_path: str) -> ProjectAnalysisResult:
    root = Path(root_path).expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        return _unknown_result(
            root,
            warnings=(f"Project root does not exist or is not a directory: {root}",),
        )

    package_json = _read_package_json(root / "package.json")
    scripts = package_json.get("scripts", {}) if isinstance(package_json, dict) else {}
    scripts = scripts if isinstance(scripts, dict) else {}
    dependencies = _package_dependencies(package_json)
    has_pyproject = (root / "pyproject.toml").exists()
    requirements_text = _read_text(root / "requirements.txt")
    pyproject_text = _read_text(root / "pyproject.toml")
    python_markers = " ".join([requirements_text, pyproject_text]).lower()

    package_manager = _detect_package_manager(root, package_json, has_pyproject)
    project_type, framework = _detect_project_type(
        root,
        scripts=scripts,
        dependencies=dependencies,
        python_markers=python_markers,
        has_pyproject=has_pyproject,
    )
    allowed_paths = _infer_allowed_paths(root, project_type)
    commands = _infer_commands(
        root,
        project_type=project_type,
        package_manager=package_manager,
        scripts=scripts,
    )
    warnings = _analysis_warnings(root, project_type, allowed_paths, commands)
    status = "ready" if project_type != "unknown" and allowed_paths and not warnings else "needs_confirmation"
    confidence = "high" if status == "ready" else "low"

    return ProjectAnalysisResult(
        root_path=str(root),
        project_type=project_type,
        detected_framework=framework,
        package_manager=package_manager,
        allowed_paths=tuple(allowed_paths),
        denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
        dev_command=commands.get("dev"),
        test_command=commands.get("test"),
        check_command=commands.get("check"),
        build_command=commands.get("build"),
        preview_command=commands.get("preview"),
        analysis_status=status,
        analysis_warnings=tuple(warnings),
        confidence=confidence,
        project_profile=build_project_profile(
            project_type=project_type,
            detected_framework=framework,
            package_manager=package_manager,
            allowed_paths=tuple(allowed_paths),
            denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
            dev_command=commands.get("dev"),
            test_command=commands.get("test"),
            check_command=commands.get("check"),
            build_command=commands.get("build"),
            preview_command=commands.get("preview"),
            analysis_status=status,
            analysis_warnings=tuple(warnings),
            confidence=confidence,
        ),
    )


def _detect_project_type(
    root: Path,
    *,
    scripts: dict[str, Any],
    dependencies: set[str],
    python_markers: str,
    has_pyproject: bool,
) -> tuple[str, str]:
    script_text = " ".join(str(value).lower() for value in scripts.values())

    if _has_any(root, ("vite.config.ts", "vite.config.js", "vite.config.mjs")) or (
        "vite" in dependencies and "react" in dependencies
    ):
        return "vite-react", "vite-react"
    if _has_any(root, ("next.config.ts", "next.config.js", "next.config.mjs")) or (
        "next" in dependencies or "next" in script_text
    ):
        return "nextjs", "nextjs"
    if "fastapi" in python_markers or _file_contains(root / "app" / "main.py", "FastAPI") or _file_contains(root / "main.py", "FastAPI"):
        return "fastapi", "fastapi"
    if dependencies.intersection({"express", "fastify", "hono", "koa"}) or _has_any(
        root,
        ("server.ts", "server.js", "src/server.ts", "src/server.js"),
    ):
        return "node-api", "node-api"
    if has_pyproject or (root / "requirements.txt").exists():
        return "python-package", "python-package"
    return "unknown", "unknown"


def _detect_package_manager(
    root: Path,
    package_json: dict[str, Any],
    has_pyproject: bool,
) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package-lock.json").exists():
        return "npm"
    if package_json:
        return "npm"
    if (root / "uv.lock").exists():
        return "uv"
    if (root / "poetry.lock").exists():
        return "poetry"
    if has_pyproject or (root / "requirements.txt").exists():
        return "pip"
    return "unknown"


def _infer_commands(
    root: Path,
    *,
    project_type: str,
    package_manager: str,
    scripts: dict[str, Any],
) -> dict[str, Optional[str]]:
    if project_type in {"vite-react", "nextjs", "node-api"}:
        return {
            "dev": _script_command(package_manager, scripts, "dev"),
            "test": _script_command(package_manager, scripts, "test"),
            "check": _script_command(package_manager, scripts, "check")
            or _script_command(package_manager, scripts, "lint"),
            "build": _script_command(package_manager, scripts, "build"),
            "preview": _script_command(package_manager, scripts, "dev"),
        }

    if project_type == "fastapi":
        entrypoint = "app.main:app" if (root / "app" / "main.py").exists() else "main:app"
        return {
            "dev": f"uvicorn {entrypoint} --reload --host 127.0.0.1 --port <port>",
            "test": "pytest" if (root / "tests").exists() else None,
            "check": "python -m compileall .",
            "build": None,
            "preview": None,
        }

    if project_type == "python-package":
        return {
            "dev": None,
            "test": "pytest" if (root / "tests").exists() else None,
            "check": "python -m compileall .",
            "build": None,
            "preview": None,
        }

    return {
        "dev": None,
        "test": None,
        "check": None,
        "build": None,
        "preview": None,
    }


def _infer_allowed_paths(root: Path, project_type: str) -> list[str]:
    candidates_by_type = {
        "vite-react": ("src", "public", "tests", "test"),
        "nextjs": ("app", "pages", "components", "src", "public", "tests", "test"),
        "fastapi": ("app", "src", "tests"),
        "node-api": ("src", "app", "routes", "tests", "test"),
        "python-package": ("src", "app", "tests"),
    }
    candidates = candidates_by_type.get(project_type, ("src", "app", "tests", "test"))
    return [path for path in candidates if (root / path).exists()]


def _analysis_warnings(
    root: Path,
    project_type: str,
    allowed_paths: list[str],
    commands: dict[str, Optional[str]],
) -> list[str]:
    warnings: list[str] = []
    if project_type == "unknown":
        warnings.append("Project type could not be inferred from known markers.")
    if not allowed_paths:
        warnings.append("No safe source or test paths were inferred.")
    if project_type in {"vite-react", "nextjs", "node-api"} and not commands.get("test"):
        warnings.append("No test command was inferred from package scripts.")
    if project_type in {"fastapi", "python-package"} and not (
        root / "tests"
    ).exists():
        warnings.append("No tests directory was found.")
    return warnings


def _script_command(
    package_manager: str,
    scripts: dict[str, Any],
    script_name: str,
) -> Optional[str]:
    if script_name not in scripts:
        return None
    if package_manager == "yarn":
        return f"yarn {script_name}"
    if package_manager == "npm":
        return f"npm run {script_name}"
    if package_manager == "pnpm":
        return f"pnpm {script_name}"
    return f"{package_manager} {script_name}" if package_manager != "unknown" else None


def _read_package_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _package_dependencies(package_json: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies"):
        value = package_json.get(key)
        if isinstance(value, dict):
            names.update(str(name).lower() for name in value)
    return names


def _read_text(path: Path) -> str:
    try:
        return path.read_text() if path.exists() else ""
    except OSError:
        return ""


def _file_contains(path: Path, text: str) -> bool:
    return text in _read_text(path)


def _has_any(root: Path, relative_paths: tuple[str, ...]) -> bool:
    return any((root / path).exists() for path in relative_paths)


def _unknown_result(
    root: Path,
    *,
    warnings: tuple[str, ...],
) -> ProjectAnalysisResult:
    return ProjectAnalysisResult(
        root_path=str(root),
        project_type="unknown",
        detected_framework="unknown",
        package_manager="unknown",
        allowed_paths=(),
        denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
        dev_command=None,
        test_command=None,
        check_command=None,
        build_command=None,
        preview_command=None,
        analysis_status="needs_confirmation",
        analysis_warnings=warnings,
        confidence="low",
        project_profile=build_project_profile(
            project_type="unknown",
            detected_framework="unknown",
            package_manager="unknown",
            allowed_paths=(),
            denied_paths=DEFAULT_EXTERNAL_DENIED_PATHS,
            analysis_status="needs_confirmation",
            analysis_warnings=warnings,
            confidence="low",
        ),
    )
