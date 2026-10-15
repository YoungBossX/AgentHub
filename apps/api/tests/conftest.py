import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def local_control_client_defaults(monkeypatch):
    """Exercise the real guard using valid local clients, never disable it."""
    original = TestClient.__init__

    def initialize(client, *args, **kwargs):
        kwargs.setdefault("base_url", "http://127.0.0.1:8000")
        kwargs.setdefault("headers", {"X-AgentHub-Control": "local-workspace"})
        original(client, *args, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", initialize)


@pytest.fixture
def anyio_backend() -> str:
    # The local dispatcher, SSE wakeups, execution leases and CLI adapters use
    # asyncio primitives. Trio is not a supported AgentHub execution runtime.
    return "asyncio"
