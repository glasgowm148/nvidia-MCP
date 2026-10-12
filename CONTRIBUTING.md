# Contributing

Keep one explicitly configured device, stdio-only transport, read-only defaults, bounded output and private
backups. No arbitrary shell/RPC or device discovery. Use synthetic tests/local HTTP; never commit
personal settings/history, credentials, device logs/screenshots, backups, SDK/APKs or vendor patches.

Real TV mutations need authorization plus a known playback/foreground state, including other apps.
Never make CI contact a household TV. Report vulnerabilities via
[private reporting](https://github.com/glasgowm148/nvidia-MCP/security/advisories/new).

Use a virtual environment with Python 3.11+. Run these checks from the repository root.
The archive globs below use a POSIX shell; in PowerShell, pass the actual archive filenames.
Keep only the current build in `dist/` (move older artifacts elsewhere before building).

```sh
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest -q
python scripts/gen_tool_docs.py --check
python -m build
python scripts/test_wheel.py
python scripts/check_release.py dist/*.whl dist/*.tar.gz --write-checksums dist/SHA256SUMS
```

Update version/changelog/docs together. Release Manager first; verify its published ZIP before updating
the pinned bundle/manifest as described in [companion](docs/companion.md). Include every distributed
wheel/source/companion in `SHA256SUMS`, inspect archive contents and verify CI. Checksums detect changed
bytes; they are not an independent publisher signature. Keep prerelease status and actual
[compatibility limits](docs/compatibility.md) until live-install/recovery checks pass.

The tool catalogue in [docs/tools.md](docs/tools.md) comes from `list_tools()`. After changing tools,
run `python scripts/gen_tool_docs.py` and commit the updated catalogue; the docs test checks it.
See the [documentation index](docs/README.md) for setup, platform and operation guides.
