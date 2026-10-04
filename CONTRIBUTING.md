# Contributing

Keep one configured Shield, stdio-only transport, read-only defaults, bounded output and private
backups. No arbitrary shell/RPC or device discovery. Use synthetic tests/local HTTP; never commit
personal settings/history, credentials, device logs/screenshots, backups, SDK/APKs or vendor patches.

Real TV mutations need authorization plus a known playback/foreground state, including other apps.
Never make CI contact a household TV. Report vulnerabilities via
[private reporting](https://github.com/glasgowm148/nvidia-MCP/security/advisories/new).

```sh
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest -q
python -m build
python scripts/test_wheel.py
python scripts/check_release.py dist/nvidia_shield_mcp-0.3.1-py3-none-any.whl dist/nvidia_shield_mcp-0.3.1.tar.gz --write-checksums dist/SHA256SUMS
```

Update version/changelog/docs together. Release Manager first; verify its published ZIP before updating
the pinned bundle/manifest as described in [companion](docs/companion.md). Include every distributed
wheel/source/companion in `SHA256SUMS`, inspect archive contents and verify CI. Checksums detect changed
bytes; they are not an independent publisher signature. Keep prerelease status and actual
[compatibility limits](docs/compatibility.md) until live-install/recovery checks pass.
