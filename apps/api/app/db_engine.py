"""Business SQLite connection policy; importing this module opens no database."""
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url


def create_runtime_engine(url: str, **options: Any) -> Engine:
    sqlite = make_url(url).get_backend_name() == 'sqlite'
    if sqlite:
        args = {'check_same_thread': False, 'timeout': 5.0}
        args.update(options.get('connect_args', {}))
        options['connect_args'] = args
    engine = create_engine(url, **options)
    if sqlite:
        event.listen(engine, 'connect', _enable_foreign_keys)
    return engine


def _enable_foreign_keys(connection, _record) -> None:
    previous = getattr(connection, 'autocommit', None)
    try:
        if previous is not None:
            connection.autocommit = True
        cursor = connection.cursor()
        try:
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA foreign_keys')
            if cursor.fetchone() != (1,):
                raise RuntimeError('SQLite foreign key enforcement is unavailable')
        finally:
            cursor.close()
    finally:
        if previous is not None:
            connection.autocommit = previous
