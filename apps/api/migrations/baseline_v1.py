"""Immutable ea0d3bc schema and explicitly supported legacy variants.

Do not regenerate this file or schema_v1.json when ORM models evolve.
"""
import json
from pathlib import Path
import sqlalchemy as sa

HEAD = '0001_local_baseline'
SCHEMA = json.loads(Path(__file__).with_name('schema_v1.json').read_text(encoding='utf-8'))
LEGACY_COLUMNS = {
    'message': {'context_json': "'{}'", 'regeneration_json': "'{}'", 'pinned_at': None},
    'session': dict.fromkeys(('active_frontend_target_id', 'active_backend_target_id', 'memory_snapshot_id', 'pinned_at', 'archived_at')),
    'externalprojecttarget': {'staging_output_dir': None, 'staging_serve_command': None, 'deploy_provider_ids_json': "'[]'"},
    'artifactversion': {'parent_version_id': None, 'content_md': "''", 'content_hash': "''", 'editor_source': "'system'"},
    'taskrun': dict.fromkeys(('runner_id', 'last_heartbeat_at', 'lease_expires_at', 'stale_detected_at', 'stale_reason')),
    'agentprofiledraft': {'system_prompt': "''", 'mention_alias': None, 'tool_policy': "''"},
}
# These exact historical compatibility fixtures used no FOREIGN KEY clauses.
LEGACY_WITHOUT_FKS = frozenset(('externalprojecttarget', 'artifactversion', 'taskrunevent'))


def frozen_metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    types = {'VARCHAR': sa.String, 'INTEGER': sa.Integer, 'DATETIME': sa.DateTime, 'BOOLEAN': sa.Boolean, 'BLOB': sa.LargeBinary}
    for name, table in SCHEMA.items():
        columns = [sa.Column(c['name'], types[c['type']](),
            *[sa.ForeignKey(ref) for ref in c['references']],
            primary_key=c['primary_key'], nullable=c['nullable']) for c in table['columns']]
        target = sa.Table(name, metadata, *columns)
        for index in table['indexes']:
            sa.Index(index['name'], *[target.c[column] for column in index['columns']], unique=index['unique'])
    return metadata
