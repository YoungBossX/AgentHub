## 1. Bound Session SSE subscriber memory

- [x] 1.1 Coalesce local notifications into one payload-free wake, replay
  SQLite events in fixed cursor batches without loss or reordering, preserve
  polling/heartbeat/reconnect behavior, add regressions, update documentation,
  run relevant gates, and clean verification artifacts.
