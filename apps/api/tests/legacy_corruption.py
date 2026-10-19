"""External legacy corruption actor confined to explicitly named test files."""
from pathlib import Path
import sqlite3


def delete_legacy_parent(db, table: str, identifier: str) -> None:
    path = Path(db.get_bind().url.database)
    assert path.name == 'legacy-corruption.sqlite3' and path.is_file()
    assert table in {'task', 'session', 'taskrun', 'memorysnapshot', 'message'}
    db.commit()
    with sqlite3.connect(path) as actor:
        assert actor.execute('PRAGMA foreign_keys').fetchone() == (0,)
        actor.execute(f'DELETE FROM "{table}" WHERE id=?', (identifier,))
    db.expire_all()
    assert db.connection().exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
