import pytest


@pytest.fixture
def anyio_backend() -> str:
    # The local dispatcher, SSE wakeups, execution leases and CLI adapters use
    # asyncio primitives. Trio is not a supported AgentHub execution runtime.
    return "asyncio"
