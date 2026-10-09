import asyncio
import sys
from types import MethodType
from unittest.mock import Mock

import pytest

from app import windows_connection_cleanup as cleanup


class ResetSocket:
    def __init__(self, *, close_fails=False):
        self.closes = 0
        self.close_fails = close_fails

    def fileno(self):
        return 123

    def shutdown(self, how):
        error = ConnectionResetError("controlled peer reset")
        error.winerror = 10054
        raise error

    def close(self):
        self.closes += 1
        if self.close_fails:
            raise OSError("controlled close failure")


def transport_fixture(loop, *, close_fails=False, protocol=None):
    from asyncio.proactor_events import _ProactorBasePipeTransport

    # Actual stdlib transport/callback and Server accounting, with only the
    # reset-producing socket operation injected. No real provider is involved.
    server = asyncio.base_events.Server(loop, [], None, None, 1, None)
    protocol = protocol or Mock(spec=asyncio.Protocol)
    sock = ResetSocket(close_fails=close_fails)
    transport = _ProactorBasePipeTransport(loop, sock, protocol, server=server)
    return server, transport, sock, protocol


@pytest.mark.anyio
async def test_stdlib_reset_reproduces_leaked_server_wait_without_recovery():
    loop = asyncio.get_running_loop()
    server, transport, sock, protocol = transport_fixture(loop)
    try:
        transport._closing = True
        with pytest.raises(ConnectionResetError):
            transport._call_connection_lost(None)
        server.close()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(server.wait_closed(), .02)
        assert sock.closes == 0 and transport._server is server
        protocol.connection_lost.assert_called_once_with(None)
    finally:
        # The deliberately broken baseline must not leak into the next test.
        sock.close()
        transport._sock = None
        if sys.version_info >= (3, 13):
            server._detach(transport)
        else:
            server._detach()
        transport._server = None
        transport._called_connection_lost = True


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows Proactor runtime")
async def test_real_callback_recovers_once_and_server_wait_completes(caplog):
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    forwarded = []
    loop.set_exception_handler(lambda _, context: forwarded.append(context))
    restore = cleanup.install_windows_connection_cleanup(loop)
    server, transport, sock, protocol = transport_fixture(loop)
    try:
        transport.close()
        # Repeated scheduled callbacks must not double-close or detach.
        loop.call_soon(transport._call_connection_lost, None)
        server.close()
        await asyncio.wait_for(server.wait_closed(), 2)
        assert sock.closes == 1 and transport._server is None
        assert transport._sock is None and transport._called_connection_lost
        protocol.connection_lost.assert_called_once_with(None)
        assert not forwarded
        assert "Recovered Windows peer-reset" in caplog.text
    finally:
        restore()
        loop.set_exception_handler(previous)


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows Proactor runtime")
async def test_non_matching_errors_reach_original_handler_and_restore_ownership():
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    forwarded = []
    original = lambda _, context: forwarded.append(context)
    loop.set_exception_handler(original)
    restore = cleanup.install_windows_connection_cleanup(loop)
    try:
        for error in [RuntimeError("unrelated"), ConnectionResetError("unknown callback")]:
            error.winerror = 10054
            context = {"exception": error, "message": "_call_connection_lost"}
            loop.call_exception_handler(context)
            assert forwarded[-1] is context
        restore()
        assert loop.get_exception_handler() is original
        restore = cleanup.install_windows_connection_cleanup(loop)
        newer = lambda *_: None
        loop.set_exception_handler(newer)
        restore()
        assert loop.get_exception_handler() is newer
    finally:
        loop.set_exception_handler(previous)


@pytest.mark.anyio
async def test_matching_callback_error_outside_socket_shutdown_is_not_hidden():
    loop = asyncio.get_running_loop()
    from asyncio.proactor_events import _ProactorBasePipeTransport

    class Protocol(asyncio.Protocol):
        def connection_lost(self, exc):
            error = ConnectionResetError("protocol error")
            error.winerror = 10054
            raise error

    server, transport, sock, _ = transport_fixture(loop, protocol=Protocol())
    sock.shutdown = lambda *_: None
    transport._closing = True
    try:
        transport._call_connection_lost(None)
    except ConnectionResetError as error:
        context = {"exception": error, "handle": asyncio.Handle(transport._call_connection_lost, (None,), loop)}
        assert not cleanup._recover_reset(context, _ProactorBasePipeTransport._call_connection_lost)
    else:
        pytest.fail("Protocol exception was lost")
    server.close()
    await asyncio.wait_for(server.wait_closed(), 2)


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows Proactor runtime")
async def test_cleanup_failure_is_observable_instead_of_reported_recovered():
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    forwarded = []
    loop.set_exception_handler(lambda _, context: forwarded.append(context))
    restore = cleanup.install_windows_connection_cleanup(loop)
    server, transport, sock, _ = transport_fixture(loop, close_fails=True)
    try:
        transport.close()
        await asyncio.sleep(0)
        assert len(forwarded) == 1
        assert isinstance(forwarded[0]["exception"], OSError)
        assert isinstance(forwarded[0]["originalException"], ConnectionResetError)
        assert transport._sock is sock and not transport._called_connection_lost
    finally:
        sock.close_fails = False
        transport._called_connection_lost = True
        sock.close()
        transport._sock = None
        if sys.version_info >= (3, 13): server._detach(transport)
        else: server._detach()
        transport._server = None
        server.close()
        restore()
        loop.set_exception_handler(previous)


def test_non_proactor_loop_has_no_handler_change():
    loop = asyncio.SelectorEventLoop()
    try:
        original = lambda *_: None
        loop.set_exception_handler(original)
        cleanup.install_windows_connection_cleanup(loop)()
        assert loop.get_exception_handler() is original
    finally:
        loop.close()


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows Proactor runtime")
@pytest.mark.parametrize("failure", ["fileno", "different_error", "protocol_and_shutdown"])
async def test_similar_failures_do_not_mutate_transport(failure):
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    forwarded = []
    loop.set_exception_handler(lambda _, context: forwarded.append(context))
    restore = cleanup.install_windows_connection_cleanup(loop)
    server, transport, sock, protocol = transport_fixture(loop)
    def fail(*_):
        error = ConnectionResetError("different failure")
        error.winerror = 10053 if failure == "different_error" else 10054
        raise error
    if failure == "fileno": sock.fileno = fail
    elif failure == "different_error": sock.shutdown = fail
    else: protocol.connection_lost.side_effect = RuntimeError("protocol failure")
    try:
        transport.close()
        await asyncio.sleep(0)
        assert len(forwarded) == 1
        assert transport._sock is sock and transport._server is server
        assert sock.closes == 0 and not transport._called_connection_lost
    finally:
        sock.close()
        transport._sock = None
        transport._called_connection_lost = True
        if sys.version_info >= (3, 13): server._detach(transport)
        else: server._detach()
        transport._server = None
        server.close()
        restore()
        loop.set_exception_handler(previous)


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows Proactor runtime")
async def test_detach_signature_passes_the_exact_transport_when_required():
    loop = asyncio.get_running_loop()
    restore = cleanup.install_windows_connection_cleanup(loop)
    server, transport, sock, _ = transport_fixture(loop)
    original_detach = server._detach
    detached = []
    def detach(self, connection):
        detached.append(connection)
        if sys.version_info >= (3, 13): original_detach(connection)
        else: original_detach()
    server._detach = MethodType(detach, server)
    try:
        transport.close()
        server.close()
        await asyncio.wait_for(server.wait_closed(), 2)
        assert detached == [transport] and sock.closes == 1
    finally:
        restore()


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [None, "startup", "shutdown"])
async def test_lifespan_restores_handler_even_when_startup_or_cleanup_fails(monkeypatch, failure):
    from app import main

    restored = Mock()
    monkeypatch.setattr(main, "install_windows_connection_cleanup", lambda loop: restored)
    def initialize(**kwargs):
        if failure == "startup": raise RuntimeError("startup error")
    monkeypatch.setattr(main, "init_database", initialize)
    monkeypatch.setattr(main, "recover_interrupted_requests", lambda bind: 0)
    preview = Mock()
    if failure == "shutdown": preview.shutdown.side_effect = RuntimeError("shutdown error")
    monkeypatch.setattr(main, "get_preview_service", lambda: preview)
    async def idle(): await asyncio.Event().wait()
    monkeypatch.setattr("app.group_execution.group_execution_loop", idle)
    async def exercise():
        async with main.lifespan(main.app): pass
    if failure:
        with pytest.raises(RuntimeError, match=failure): await exercise()
    else:
        await exercise()
    restored.assert_called_once()
    if failure != "startup": preview.shutdown.assert_called_once()
