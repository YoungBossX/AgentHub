"""Browser request boundaries for the local, single-user control plane."""
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

CONTROL_HEADER = "x-agenthub-control"
CONTROL_VALUE = "local-workspace"
MCP_GATEWAY_PATH = "/mcp/agenthub-docs"


def is_loopback_host(value: str) -> bool:
    try:
        parsed = urlsplit("http://" + value)
        return (
            parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            and parsed.username is None and parsed.password is None
            and not parsed.path and not parsed.query and not parsed.fragment
            and (parsed.port is None or 0 < parsed.port < 65536)
            and not any(character.isspace() for character in value)
        )
    except ValueError:
        return False


class LocalRequestGuard:
    def __init__(self, app, *, frontend_origins: set[str]):
        self.app = app
        self.frontend_origins = frozenset(frontend_origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        hosts = headers.getlist("host")
        reason = None
        if len(hosts) != 1 or not is_loopback_host(hosts[0]):
            reason = "API Host is not an allowed loopback host."
        elif scope["path"] != MCP_GATEWAY_PATH:
            origins = headers.getlist("origin")
            if origins and (len(origins) != 1 or origins[0] not in self.frontend_origins):
                reason = "API request Origin is not allowed."
            elif scope["method"] not in {"GET", "HEAD", "OPTIONS"} and headers.getlist(CONTROL_HEADER) != [CONTROL_VALUE]:
                reason = "Mutation requires X-AgentHub-Control: local-workspace."
        if reason:
            await JSONResponse({"detail": reason}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)
