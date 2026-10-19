"""Explicit fixture-only ordering; never changes policy or creates missing data."""
from sqlalchemy import inspect
from sqlmodel import Session


def flush_fixture_rows(db: Session) -> None:
    pending = list(db.new)
    keys = {(inspect(row).mapper.local_table.name, column.name, getattr(row, column.key)): row
            for row in pending for column in inspect(row).mapper.local_table.primary_key}
    while pending:
        ready = []
        for row in pending:
            table = inspect(row).mapper.local_table
            parents = [keys.get((fk.column.table.name, fk.column.name, getattr(row, column.key)))
                       for column in table.columns for fk in column.foreign_keys]
            if not any(parent is not None and parent is not row and any(parent is p for p in pending)
                       for parent in parents):
                ready.append(row)
        if not ready:
            raise ValueError('Fixture has mutually dependent new rows; create its parents explicitly')
        for row in ready:
            db.flush([row])
            pending = [p for p in pending if p is not row]
    db.flush()
