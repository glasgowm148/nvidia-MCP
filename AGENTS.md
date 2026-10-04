# Contributor instructions

Keep output and device reads bounded; prefer targeted searches over dumping logs/schemas.
For onboarding, the user follows docs/setup.md on the TV; the agent performs docs/agent-setup.md on
the computer. Handle dependency installation, config merging and verification instead of handing
computer commands back to the user. Wait for the user to approve the Shield's first debugging prompt.
Preserve one explicitly configured Shield, stdio transport, read-only defaults and private backups.
Do not introduce arbitrary shell/RPC passthrough or auto-discover/manage other network devices.
Never test mutations on a real TV without permission and a known playback/foreground state.
Use synthetic credentials in tests. Do not commit private logs, screenshots, configs or snapshots.
Run the focused tests, ruff and package build for code changes. Add checks for actual failure modes,
especially profile selection, stale state, rollback and privacy. Avoid tests mirroring implementation.
Update capability/compatibility documentation when tool contracts change. Keep prompts concise.
