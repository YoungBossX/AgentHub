"""Immutable integrity schema, independent of evolving ORM definitions."""
import json
from pathlib import Path

import sqlalchemy as sa

HEAD = '0002_database_integrity'
SCHEMA = json.loads(Path(__file__).with_name('schema_v2.json').read_text(encoding='utf-8'))


def frozen_metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    types = {'VARCHAR': sa.String, 'INTEGER': sa.Integer, 'DATETIME': sa.DateTime,
             'BOOLEAN': sa.Boolean, 'BLOB': sa.LargeBinary}
    for name, table in SCHEMA.items():
        columns = [sa.Column(c['name'], types[c['type']](),
            *[sa.ForeignKey(ref) for ref in c['references']],
            primary_key=c['primary_key'], nullable=c['nullable']) for c in table['columns']]
        target = sa.Table(name, metadata, *columns)
        for index in table['indexes']:
            sa.Index(index['name'], *[target.c[c] for c in index['columns']], unique=index['unique'])
    return metadata
