import os
import re
from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import unquote, urlsplit


AdapterEnvironment = Literal["codex", "claude_code"]

REDACTED = "[redacted]"

_PORTABLE_RUNTIME_KEYS = frozenset(
    {
        "APPDATA",
        "CI",
        "COLORTERM",
        "COMSPEC",
        "COREPACK_HOME",
        "FORCE_COLOR",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LOCALAPPDATA",
        "NODE_ENV",
        "NO_COLOR",
        "PATH",
        "PATHEXT",
        "PNPM_HOME",
        "PNPM_STORE_PATH",
        "SHELL",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "TMPDIR",
        "TZ",
        "USERPROFILE",
        "WINDIR",
    }
)

_PROJECT_PUBLIC_PREFIXES = (
    "NEXT_PUBLIC_",
    "PUBLIC_",
    "VITE_",
)

_ADAPTER_COMMON_KEYS = frozenset(
    {
        "ALL_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "NO_PROXY",
        "NODE_EXTRA_CA_CERTS",
        "REQUESTS_CA_BUNDLE",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "XDG_CONFIG_HOME",
    }
)

_ADAPTER_KEYS: dict[AdapterEnvironment, frozenset[str]] = {
    "codex": frozenset(
        {
            "CODEX_API_KEY",
            "CODEX_HOME",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_ORG_ID",
            "OPENAI_PROJECT_ID",
        }
    ),
    "claude_code": frozenset(
        {
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "CLAUDE_CONFIG_DIR",
        }
    ),
}

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b("
    r"api[_-]?key|auth(?:orization)?|client[_-]?secret|credential|"
    r"database[_-]?url|password|passwd|private[_-]?key|secret|token"
    r")(\s*[:=]\s*)[^,\s;]+"
)
_AUTHORIZATION_RE = re.compile(
    r"(?i)\b(authorization\s*[:=]\s*)(?:bearer\s+)?[^,\s;]+"
)
_SENSITIVE_KEY_EXACT = frozenset(
    {
        "authorization",
        "credential",
        "database_url",
        "password",
        "passwd",
        "private_key",
        "secret",
        "token",
    }
)
_SENSITIVE_KEY_SUFFIXES = (
    "_api_key",
    "_access_token",
    "_auth_token",
    "_client_secret",
    "_credential",
    "_database_url",
    "_id_token",
    "_password",
    "_passwd",
    "_private_key",
    "_refresh_token",
    "_secret",
    "_token",
    "_base_url",
)
_SENSITIVE_PROXY_KEYS = frozenset(
    {"all_proxy", "http_proxy", "https_proxy"}
)


def project_process_env(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    return _select_environment(
        os.environ if environ is None else environ,
        allowed_keys=_PORTABLE_RUNTIME_KEYS,
        allowed_prefixes=_PROJECT_PUBLIC_PREFIXES,
    )


def adapter_process_env(
    adapter: AdapterEnvironment,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    try:
        adapter_keys = _ADAPTER_KEYS[adapter]
    except KeyError as exc:  # pragma: no cover - typed internal call sites
        raise ValueError(f"Unsupported adapter environment: {adapter}") from exc
    return _select_environment(
        os.environ if environ is None else environ,
        allowed_keys=_PORTABLE_RUNTIME_KEYS | _ADAPTER_COMMON_KEYS | adapter_keys,
    )


def redact_process_evidence(
    value: Any,
    environ: Mapping[str, str] | None = None,
) -> Any:
    source = os.environ if environ is None else environ
    secret_values = _sensitive_environment_values(source)
    return _redact_value(value, secret_values)


def _select_environment(
    environ: Mapping[str, str],
    *,
    allowed_keys: frozenset[str],
    allowed_prefixes: tuple[str, ...] = (),
) -> dict[str, str]:
    selected: dict[str, str] = {}
    for key, value in environ.items():
        normalized_key = key.upper()
        if normalized_key in allowed_keys or normalized_key.startswith(allowed_prefixes):
            selected[key] = value
    return selected


def _sensitive_environment_values(environ: Mapping[str, str]) -> tuple[str, ...]:
    values: set[str] = set()
    for key, value in environ.items():
        if not _is_sensitive_key(key) or not isinstance(value, str) or not value:
            continue
        values.add(value)
        if key.upper().endswith("_BASE_URL"):
            parsed = urlsplit(value)
            if parsed.username:
                values.add(parsed.username)
                values.add(unquote(parsed.username))
            if parsed.password:
                values.add(parsed.password)
                values.add(unquote(parsed.password))
    return tuple(sorted(values, key=len, reverse=True))


def _redact_value(value: Any, secret_values: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if _is_sensitive_key(str(key))
                else _redact_value(nested, secret_values)
            )
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, secret_values) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item, secret_values) for item in value)
    if isinstance(value, str):
        redacted = value
        for secret in secret_values:
            redacted = redacted.replace(secret, REDACTED)
        redacted = _AUTHORIZATION_RE.sub(
            lambda match: f"{match.group(1)}{REDACTED}",
            redacted,
        )
        return _SECRET_ASSIGNMENT_RE.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
            redacted,
        )
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized).strip("_").lower()
    return (
        normalized in _SENSITIVE_KEY_EXACT
        or normalized in _SENSITIVE_PROXY_KEYS
        or normalized.endswith(_SENSITIVE_KEY_SUFFIXES)
    )
