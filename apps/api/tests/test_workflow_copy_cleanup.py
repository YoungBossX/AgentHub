from pathlib import Path
import shutil

import pytest

from app import workflow_acceptance as acceptance


def copy_scope():
    factory = getattr(acceptance, 'workflow_copy', None)
    if factory is None:
        pytest.fail('浏览器临时文件占用会掩盖业务验收结果，缺少有界清理与保留回执')
    return factory()


def busy():
    error = PermissionError('owned browser temporary file is busy')
    error.winerror = 32
    return error


def test_transient_windows_share_lock_retries_and_actually_removes_owned_copy(monkeypatch):
    original = shutil.rmtree
    attempts = []
    def remove(path):
        attempts.append(path)
        if len(attempts) == 1: raise busy()
        return original(path)
    monkeypatch.setattr(acceptance.shutil, 'rmtree', remove)
    with copy_scope() as (root, receipt):
        (root/'owned.txt').write_text('actual evidence', encoding='utf-8')
    assert not root.exists()
    assert receipt['status'] == 'removed' and receipt['attempts'] == 2


def test_persistent_share_lock_retains_only_owned_copy_and_reports_it(monkeypatch):
    original = shutil.rmtree
    def remove(path): raise busy()
    monkeypatch.setattr(acceptance.shutil, 'rmtree', remove)
    with copy_scope() as (root, receipt):
        (root/'owned.txt').write_text('retained evidence', encoding='utf-8')
    assert receipt['status'] == 'retained_busy' and receipt['attempts'] == 3
    assert (root/'owned.txt').read_text(encoding='utf-8') == 'retained evidence'
    assert receipt['directoryName'] == root.name
    assert root.resolve().parent == Path(acceptance.tempfile.gettempdir()).resolve()
    original(root)


def test_other_cleanup_errors_remain_visible(monkeypatch):
    original = shutil.rmtree
    def remove(path): raise PermissionError('not a sharing violation')
    monkeypatch.setattr(acceptance.shutil, 'rmtree', remove)
    root = None
    try:
        with pytest.raises(PermissionError):
            with copy_scope() as (root, _): pass
    finally:
        if root is not None:
            assert root.resolve().parent == Path(acceptance.tempfile.gettempdir()).resolve()
            original(root)
