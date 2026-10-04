# Contributor instructions

Keep output and device reads bounded; prefer targeted searches over dumping logs/schemas.
Preserve one explicitly configured Shield, stdio transport, read-only defaults and private backups.
Do not introduce arbitrary shell/RPC passthrough or auto-discover/manage other network devices.
Never test mutations on a real TV without permission and a known playback/foreground state.
Use synthetic credentials in tests. Do not commit private logs, screenshots, configs or snapshots.
Run the focused tests, ruff and package build for code changes. Add checks for actual failure modes,
especially profile selection, stale state, rollback and privacy. Avoid tests mirroring implementation.
Update capability/compatibility documentation when tool contracts change. Keep prompts concise.
