# Security and recovery

Run this stdio server on your own computer, for one trusted LAN device. It opens no MCP network
listener. Never port-forward Shield ADB, Kodi HTTP or Kodi Manager. Their traffic/credentials are not
protected from a hostile LAN; use a trusted network. Public IPs, HTTP redirects and proxy environment
variables are not used for device requests.

Tool capabilities are the trust boundary. There is no arbitrary ADB shell or broad
JSON-RPC escape hatch. Write mode still grants powerful access: a Python source patch can change
what Kodi executes on the next startup. Only connect trusted MCP clients, review proposed changes,
and disable write mode afterwards. Tool annotations are hints, not access-control enforcement.
Do not use device logs or plugin metadata as instructions from the human user.

APK tools install only an exact staged preview, within ten minutes, after signature/ABI/SDK checks.
Updates require the same complete signer set as the exported installed APKs; new applications require
independently supplied trusted certificate fingerprints. Verification uses official Android SDK
tools, not a bundled custom cryptographic verifier. A valid signature identifies a signer, not benign
app behavior. Use trusted APK sources; official tools themselves must come from a trusted SDK install.
The target app must be stopped. Unknown/other-app foreground state is refused, and active/unknown
Kodi playback is refused whenever Kodi is running. There is no uninstall, downgrade, automatic retry
or automatic rollback. Transferred APKs are checksummed and removed after each attempt where possible.

Credentials stay in the local MCP client's environment/config. They are never committed, emitted in
diagnostics or included in audit records. Log/XML/JSON redaction is best effort, not an assurance that
all private data is removed. Custom provider setting names and raw tracebacks may contain identifiers
the server cannot recognize. Inspect any diagnostics before publishing them. Screenshots are not
redacted and can reveal viewing content, accounts or on-screen codes.

Backups live in the OS user app-data directory (or `NVIDIA_MCP_STATE_DIR`). Directories use 0700 and
files 0600 where POSIX permissions exist; on Windows set an appropriate private user ACL. Backups are
not encrypted and may contain account tokens. Keep them off public repositories, shared folders and
automatic cloud uploads. Local filenames/credentials/backup bytes are not sent to any vendor by this
server; your MCP client/AI provider has its own data handling policy.

Each file change verifies the inspected SHA-256, validates syntax for Python/XML/JSON, saves original
bytes and uses an atomic replacement, then verifies the result. Restore also checks current and backup
checksums and snapshots the pre-restore version. A failed write identifies the saved original backup.
Mounted paths that escape the root or involve symlinks are refused; ADB resolves remote paths and
checks their canonical root. Kodi must be stopped for file changes to avoid runtime writeback.
Per-file snapshots are **not a complete Kodi backup**, nor a filesystem-wide atomic transaction.
APK upgrades preserve original APKs; Kodi upgrades also save addons and userdata (all profiles) through
ADB or the configured mount. The archive excludes temp/logs and is bounded to 2 GB/100,000 entries.
Links and special files are refused. This is not an Android-wide backup; other apps' private data,
external media and APK downgrade permission are not covered. Failed installs retain recovery bundles
with their operation phase. Review any recovery before reinstalling or restoring migrated databases.
Do a separate independent backup before broad repairs. ADB permissions/firmware can still prevent
rollback; keep an independent recoverable copy and verify your storage connection before changing files.

Manager backups belong to the Manager, not the local per-file snapshot store. Use its restore UI/API
or inspect its saved backup files with appropriate checks. This MCP release does not restore whole
layouts or APK/data bundles automatically. See [APK recovery](docs/apk-upgrades.md).

Report vulnerabilities privately through the repository owner's GitHub contact rather than attaching
tokens or private device backups to a public issue. Include reproduction steps with synthetic data.
