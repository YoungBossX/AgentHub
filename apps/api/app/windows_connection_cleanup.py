"""Recover one CPython Proactor cleanup failure without changing loop policy."""

import asyncio
import inspect
import linecache
import logging
import sys
from collections.abc import Callable

logger = logging.getLogger(__name__)


def _recover_reset(context: dict, cleanup: Callable) -> bool:
    error = context.get("exception")
    callback = getattr(context.get("handle"), "_callback", None)
    transport = getattr(callback, "__self__", None)
    if (
        not isinstance(error, ConnectionResetError)
        or getattr(error, "winerror", None) != 10054
        or error.__context__ is not None
        or getattr(callback, "__func__", None) is not cleanup
        or not getattr(transport, "_closing", False)
        or getattr(transport, "_called_connection_lost", True)
        or getattr(transport, "_sock", None) is None
    ):
        return False

    # Match the failing operation, not merely an exception class or log text.
    # A protocol.connection_lost error must remain visible. Unknown/frozen
    # stdlib layouts fall back to the existing handler without guessing.
    trace = error.__traceback__
    while trace is not None:
        if (trace.tb_frame.f_code is cleanup.__code__
                and linecache.getline(cleanup.__code__.co_filename, trace.tb_lineno).strip()
                == "self._sock.shutdown(socket.SHUT_RDWR)"):
            break
        trace = trace.tb_next
    if trace is None:
        return False

    server = getattr(transport, "_server", None)
    detach_args = ()
    if server is not None:
        if not isinstance(server, asyncio.base_events.Server):
            return False
        signature = inspect.signature(server._detach)
        try:
            signature.bind(transport)  # CPython 3.13+ tracks transports.
            detach_args = (transport,)
        except TypeError:
            try:
                signature.bind()  # CPython 3.11/3.12 tracks a count.
            except TypeError:
                return False

    # The protocol callback already ran. Finish only the skipped cleanup tail;
    # calling the original callback again would notify the protocol twice.
    transport._sock.close()
    transport._sock = None
    if server is not None:
        server._detach(*detach_args)
        transport._server = None
    transport._called_connection_lost = True
    logger.warning("Recovered Windows peer-reset connection cleanup (10054).")
    return True


def install_windows_connection_cleanup(loop: asyncio.AbstractEventLoop) -> Callable[[], None]:
    """Install for this lifespan only and return an ownership-aware restorer."""
    if sys.platform != "win32" or not isinstance(loop, asyncio.ProactorEventLoop):
        return lambda: None
    from asyncio.proactor_events import _ProactorBasePipeTransport

    cleanup = _ProactorBasePipeTransport._call_connection_lost
    previous = loop.get_exception_handler()

    def handle(current_loop: asyncio.AbstractEventLoop, context: dict) -> None:
        try:
            if _recover_reset(context, cleanup):
                return
        except Exception as error:
            context = {**context, "message": "Windows connection cleanup recovery failed",
                       "exception": error, "originalException": context.get("exception")}
        if previous is not None:
            previous(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(handle)

    def restore() -> None:
        if loop.get_exception_handler() is handle:
            loop.set_exception_handler(previous)

    return restore
