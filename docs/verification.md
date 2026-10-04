# Verification — initial 0.1.0 release

31 automated tests passed locally on macOS / Python 3.14:

- MCP SDK 1.30.0: real stdio subprocess initialization, 25-tool discovery, structured tool output,
  resource/prompt discovery and explicit refusal of disabled writes/unrestricted RPC.
- Local HTTP server and mock HTTP transport: request/auth plumbing, redirects refused, response bounds,
  and error bodies withheld.
- Synthetic Kodi storage: exact patch preview/application, conflicting hashes/anchors, invalid syntax,
  preserved backups, integrity checks, restore/undo, and symlink/traversal refusal.
- Fake device/service responses: busy/unknown playback refusal, other-app interruption refusal,
  active-profile selection, add-on version checks, and immutable/expiring/profile-bound layout previews.
- Wheel and source distribution build; no credentials, backups or device logs in package contents.

Real Shield checks during packaging:

- ADB authorization and device access worked; the Kodi process was present.
- Real MCP stdio calls for Shield diagnostics, bounded redacted Android Kodi logs, and Kodi source-file
  reads passed. A disabled remote-control call was refused without sending input.
- No remote input, app launch, restart, source edit or configuration change was performed.
- Kodi's HTTP endpoint was unavailable during this check. Live JSON-RPC/provider previews and live
  Manager layout changes therefore **were not verified through this new MCP server** in this session.
  Their protocol/adapter behaviour is tested with synthetic services; broader firmware/client testing
  is still needed. Existing Manager behaviour was developed and exercised separately before this repo.

Linux/Windows Python 3.11–3.13 checks run in the repository's GitHub Actions matrix.
Read the actual CI result before claiming a particular platform is verified. Tests deliberately do not
connect to household devices in CI. An alpha release is not a universal Kodi compatibility guarantee.
