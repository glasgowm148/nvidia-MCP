# Operation diagnostics (development capability)

Use `shield_support_bundle` for bounded readiness, versions, access flags, classified failures,
selected operation history and recovery references. It performs existing read-only readiness
probes and cached Manager diagnostics; it never plays media, runs providers, retries writes or
uploads the bundle. Missing information is unavailable rather than healthy.

Tools return additive `operation` v1 metadata and `history_recorded` alongside existing dictionary
results. Error text includes a stable reason code, operation reference, correlation ID and next step
for MCP SDK 1.x/2.x clients. MCP validation errors before tool invocation and process termination
may have no operation record. Queued work's success means accepted, not independently verified.

A tool generates an opaque correlation ID and forwards it as `X-Correlation-ID` on Manager
requests. Compatible Manager responses appear in `manager_operations` with the same correlation
ID and their own operation IDs. The history retains only fixed operation names, allow/refuse
decisions, stable codes, durations, outcomes and opaque backup/undo IDs. It excludes arguments,
targets, credentials, paths, profiles, log text, media items and personal viewing history.

The stdlib v1 contract is vendored unchanged from Kodi Manager's `operation_records.py` so neither
package needs the other at runtime. The sibling integration test checks source parity. The full
contract and limits are documented in Kodi Manager's `docs/operation-records.md`.

History replaces new appends to the old unbounded `audit.jsonl`; existing legacy files are left
intact. `history.sqlite3` lives in the private MCP state directory (0700 directory, 0600 database
on POSIX; use appropriate user filesystem permissions on other platforms). SQLite serializes
writers across threads/processes. At most 256 records / 1 MiB are retained for seven days;
bundles select 20 per service and counts cover at most the latest 50. Corrupt/unwritable history
is reported unavailable without turning a completed action into failure. This is not an execution
journal or a guarantee that every operation survived a process crash.

Connection failure, authentication refusal, write/playback/allowlist refusal, missing APIs,
invalid response and ambiguous write outcome retain distinct codes/outcomes. A timeout, lost
reply or invalid write reply can mean **the change already completed**. Inspect current state and
recovery references before any retry; no automatic write repeat occurs. Correlation IDs are
references, not deduplication/idempotency keys.

The Manager bundle is optional: `/api/health` must advertise `support_bundle_version: 1` before
collection. Older Managers, including the unchanged pinned 0.7.23 companion, retain their existing
tools and return `unsupported` for this optional capability. No bundled ZIP, write gate,
authentication, playback guard, profile protection or checksum requirement is relaxed.

## Verify generated artifacts together

Build each project into a new output directory to preserve prior packages. Wheel smoke checks
accept `--dist <directory>`. Then run from nvidia-MCP with its dependency environment:

```sh
python -I scripts/test_manager_interface.py --wheel <built-mcp.whl> --manager-zip <built-manager.zip>
```

This imports the actual wheel and extracted Manager ZIP, checks source boundaries, and exercises
correlation, permission refusal, backup/undo IDs and redacted diagnostics over local HTTP with
synthetic mutation handlers. It never connects to a TV. Standalone CI still runs each project's
existing replay, safety, packaging and UI checks; sibling integration tests skip when the other
checkout is absent. A coordinated artifact check is needed before a future companion update.
