from dataclasses import dataclass
from typing import Optional

from app.external_workspaces import DEFAULT_EXTERNAL_DENIED_PATHS


PROJECT_PROFILE_IDS = {
    "vite-react",
    "nextjs-react",
    "fastapi-python",
    "generic-repo",
}


@dataclass(frozen=True)
class ProjectProfileCommands:
    dev: Optional[str] = None
    test: Optional[str] = None
    check: Optional[str] = None
    build: Optional[str] = None
    preview: Optional[str] = None

    def as_dict(self) -> dict[str, str]:
        return {
            name: value
            for name, value in {
                "dev": self.dev,
                "test": self.test,
                "check": self.check,
                "build": self.build,
                "preview": self.preview,
            }.items()
            if value
        }


@dataclass(frozen=True)
class ProjectProfile:
    profile_id: str
    display_name: str
    project_type: str
    detected_framework: str
    package_manager: str
    allowed_paths: tuple[str, ...]
    denied_paths: tuple[str, ...]
    commands: ProjectProfileCommands
    preview_strategy: str
    confidence: str
    status: str
    warnings: tuple[str, ...]

    def summary(self) -> dict[str, object]:
        return {
            "profileId": self.profile_id,
            "displayName": self.display_name,
            "projectType": self.project_type,
            "detectedFramework": self.detected_framework,
            "packageManager": self.package_manager,
            "allowedPaths": list(self.allowed_paths),
            "deniedPaths": list(self.denied_paths),
            "commands": self.commands.as_dict(),
            "previewStrategy": self.preview_strategy,
            "confidence": self.confidence,
            "status": self.status,
            "warnings": list(self.warnings),
        }


def build_project_profile(
    *,
    project_type: str,
    detected_framework: str,
    package_manager: str,
    allowed_paths: tuple[str, ...],
    denied_paths: tuple[str, ...] = DEFAULT_EXTERNAL_DENIED_PATHS,
    dev_command: Optional[str] = None,
    test_command: Optional[str] = None,
    check_command: Optional[str] = None,
    build_command: Optional[str] = None,
    preview_command: Optional[str] = None,
    analysis_status: str,
    analysis_warnings: tuple[str, ...],
    confidence: str,
) -> ProjectProfile:
    profile_id = profile_id_for_project_type(project_type)
    return ProjectProfile(
        profile_id=profile_id,
        display_name=display_name_for_profile(profile_id),
        project_type=project_type,
        detected_framework=detected_framework,
        package_manager=package_manager,
        allowed_paths=allowed_paths,
        denied_paths=denied_paths,
        commands=ProjectProfileCommands(
            dev=dev_command,
            test=test_command,
            check=check_command,
            build=build_command,
            preview=preview_command,
        ),
        preview_strategy=preview_strategy_for_project_type(project_type),
        confidence=confidence,
        status=analysis_status,
        warnings=analysis_warnings,
    )


def profile_id_for_project_type(project_type: str) -> str:
    if project_type == "vite-react":
        return "vite-react"
    if project_type == "nextjs":
        return "nextjs-react"
    if project_type == "fastapi":
        return "fastapi-python"
    return "generic-repo"


def display_name_for_profile(profile_id: str) -> str:
    return {
        "vite-react": "Vite / React",
        "nextjs-react": "Next.js / React",
        "fastapi-python": "FastAPI / Python",
        "generic-repo": "Generic Repo",
    }.get(profile_id, "Generic Repo")


def preview_strategy_for_project_type(project_type: str) -> str:
    if project_type == "vite-react":
        return "vite-dev-server"
    if project_type == "nextjs":
        return "next-dev-server"
    if project_type == "fastapi":
        return "python-api"
    return "none"
