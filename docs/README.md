# nvidia-MCP documentation

nvidia-MCP runs on your computer; optional Kodi Manager runs inside Kodi.
Start with read-only access on one explicitly configured device.

## Start here

1. [Prepare the TV](setup.md): debugging, Kodi HTTP and the prompt to give your agent.
2. [Agent setup](agent-setup.md): dependencies, private configuration, MCP registration and verification.
3. [Troubleshooting](troubleshooting.md): authorization, network access and missing tools.

For other devices, use [Android TV / Google TV / Fire OS](android-tv.md) or the
experimental [Apple TV guide](apple-tv.md). Kodi must already be installed on Apple TV.

## Use and repair

| Guide | Contents |
| --- | --- |
| [Tool reference](tools.md) | Generated tool catalogue, access modes and platform differences |
| [Agent skill](../skills/nvidia-shield-kodi/SKILL.md) | SKILL.md that guides agents through triage, recipes and safe changes |
| [Configuration](configuration.md) | Environment variables, private storage, playback guards and opt-ins |
| [Kodi Manager companion](companion.md) | Repository installation, live settings/dashboard, profile tokens and capability boundaries |
| [Repair workflows](repairs.md) | Diagnose, preview, apply, verify and undo configuration changes |
| [APK upgrades and recovery](apk-upgrades.md) | SDK tooling, signer checks, previews and recovery bundles |
| [Compatibility](compatibility.md) | Tested devices/versions and remaining hardware checks |
| [Verification history](verification.md) | Evidence from release audits and reference-device checks |

## Develop and contribute

- [Python library](library.md): reuse the device operations in your own tools.
- [Profile-relaunch source kit](../contrib/profile-relaunch/README.md): separately deployed Android workaround.
- [Contributing](../CONTRIBUTING.md): tests, generated docs, builds and releases.
- [Changelog](../CHANGELOG.md) · [Security and private reports](../SECURITY.md).

[Back to the project](../README.md).

Agent reference: [Android connection commands and limits](android-tv-connection.md).
