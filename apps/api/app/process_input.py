"""Bounded per-call stdin without pipe backpressure or Windows argv limits."""

from contextlib import contextmanager
import subprocess
import tempfile


@contextmanager
def private_stdin(text: str | None):
    if text is None:
        yield subprocess.DEVNULL
        return
    with tempfile.TemporaryFile(mode="w+b") as stream:
        stream.write(text.encode("utf-8"))
        stream.seek(0)
        yield stream
