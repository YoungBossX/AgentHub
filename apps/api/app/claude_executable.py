import os
import shutil
from collections.abc import Callable
from pathlib import Path


def resolve_claude_executable(
    command: str,
    *,
    windows: bool | None = None,
    lookup: Callable[[str], str | None] | None = None,
) -> str:
    """Resolve npm's native Windows launcher without executing a shell shim."""
    if not (os.name == "nt" if windows is None else windows):
        return command
    installed = (lookup or shutil.which)(command)
    if not installed:
        return command
    path = Path(installed)
    if path.suffix.lower() == ".exe":
        return str(path)
    for relative in (
        "node_modules/@anthropic-ai/claude-code/bin/claude.exe",
        "node_modules/@anthropic-ai/claude-code/node_modules/"
        "@anthropic-ai/claude-code-win32-x64/claude.exe",
    ):
        native = path.parent / relative
        if native.is_file():
            return str(native)
    return command
