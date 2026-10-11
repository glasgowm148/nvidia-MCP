# Library API

Other tools on the same computer (for example a household deploy script) can drive the Shield
with nvidia-MCP's own device code instead of copying it. `nvidia_mcp.Shield` wraps the transport
and operations the MCP tools use: the viewing guard, the quit-then-force-stop rule and the
checksum-verified file push are the same code, not re-implementations.

```python
from nvidia_mcp import Config, Shield, ShieldError

config = Config(host="192.168.1.50", password="...", allow_writes=True)
with Shield(config, kodi_route="auto") as tv:
    state = tv.viewing_state()
    if state["verdict"] in ("idle", "screensaver", "asleep"):
        tv.quit_kodi(wait=30)
        tv.push_verified(
            "build/relaunch.sh",
            "/sdcard/Android/data/org.xbmc.kodi/files/.kodi/addons/script.example/relaunch.sh",
        )
        tv.start_kodi(wait=60)
```

`Shield.from_env()` reads the same environment variables as the server (`SHIELD_HOST`,
`KODI_PASSWORD`, `NVIDIA_MCP_ALLOW_WRITES`, ...; see [configuration](configuration.md)).

## Stability

The names below, their parameters and the result keys documented here follow semantic
versioning from 0.4.6: a minor release may add parameters with defaults, result keys, error kinds
and verdicts; anything removed or changed incompatibly waits for the next major version (or, while
the version is 0.x, the next minor version, announced in the changelog). Everything else in
`nvidia_mcp` (the `transport`, `operations`, `files` modules and so on) is internal and may change
in any release.

## Reference

`Shield(config: Config, *, kodi_route: str = "direct", transport=None)`

- `kodi_route`: `"direct"` sends Kodi JSON-RPC over the LAN to `config.host`; `"forward"` asks
  the adb server for `adb forward tcp:0 tcp:<kodi_port>` and talks to `127.0.0.1` instead
  (macOS Local Network permission blocks direct LAN HTTP from some processes, but not from the
  adb server); `"auto"` uses direct when Kodi answers there and otherwise forward, decided once.
  The forward is removed by `close()` / leaving the `with` block. The MCP server always uses
  direct.
- Use it as a context manager or call `close()`.

| Method | Returns | Notes |
| --- | --- | --- |
| `adb(args: list[str], *, timeout=30, limit=1_000_000)` | `bytes` | `adb -s <serial> ...`; bounded output |
| `shell(args: list[str], *, timeout=30, limit=1_000_000)` | `str` | `adb shell`, each argument quoted |
| `rpc(method: str, params: dict \| None = None)` | Kodi's `result` | Over the chosen route |
| `viewing_state()` | `dict` | Below; reads only |
| `kodi_alive()` | `bool` | Kodi process running (`pidof`) |
| `quit_kodi(wait: float = 30)` | `dict` | Same as `kodi_lifecycle stop`; needs `allow_writes` |
| `start_kodi(wait: float = 0)` | `dict` | Same as `kodi_lifecycle start`; with `wait`, `ready` says whether JSON-RPC answered; needs `allow_writes` |
| `pull(path, local=None, *, limit=50_000_000)` | `bytes`, or byte count | With `local`, streams to a new 0600 file |
| `push_verified(local, remote, *, mode: str \| None = None)` | `{"remote", "sha256", "bytes"}` | Atomic, checksum-verified; needs `allow_writes` |
| `memory()` | `dict` | `mem_total_kb`, `mem_available_kb`, `swap_total_kb`, `swap_free_kb`, `swap_used_percent`, `kodi` (`pss_kb`, `native_heap_kb`, `rss_kb`, or `None` when Kodi is not running) |
| `process_deaths(package="org.xbmc.kodi", lines=2000)` | `list[dict]` | `am_proc_died`/`am_kill` records from Android's event log: `time`, `event`, `pid`, `oom_adj`, `proc_state` or `reason` |

Failures raise `nvidia_mcp.ShieldError`; `.kind` is a stable short code (`unreachable`,
`timeout`, `authorization_required`, `rpc_error`, `exit_hung`, `restarted`, `respawned`,
`verify_failed`, `not_found`,
`invalid_request`, ...), `.message` is readable text. Programming mistakes (`adb("shell ls")`
instead of a list, an unknown `kodi_route`) raise `TypeError`/`ValueError`.

### `viewing_state()`

```python
{
    "verdict": "idle",  # idle | playing | paused | other_app | screensaver | asleep | unknown
    "players": [],  # Player.GetActivePlayers, or None when Kodi could not be asked
    "media_sessions": [{"package": "org.xbmc.kodi", "state": 1}],  # Android PlaybackState, or None
    "foreground": "org.xbmc.kodi",  # resumed package, or None
    "screen": "app",  # app | screensaver | asleep, or None
    "wakefulness": "Awake",  # dumpsys power: Awake | Dreaming | Dozing | Asleep, or None
    "kodi_running": True,
    "unavailable": {},  # signal -> ShieldError kind for anything that could not be read
}
```

`idle`, `screensaver` and `asleep` are exactly the verdicts under which the guarded methods go
ahead (`nvidia_mcp.device.UNATTENDED`); the others are refused. A paused film (Kodi or another
app's media session at `state=2`) is `paused`/`other_app`, never idle. A signal that cannot be
read gives `unknown`, not `idle`. The guarded methods check again themselves, so a verdict read a
moment earlier is advice, not permission.

### `quit_kodi(wait=30)`

Refuses (ShieldError) unless nobody is watching, then sends `Application.Quit` and waits up to
`wait` seconds. A Kodi that is still running after that is force-stopped only when the current
`kodi.log` shows "Stopping the application...", "Saving settings", "Saving skin settings" and
"Stopping all" and the guard still passes on Android's media sessions and foreground app; the
result then has `stopped_by: "force-stop after a hung exit"` and the `exit_evidence` lines.
Otherwise it raises `exit_hung` and leaves Kodi for the person at the TV. Returns
`stopped_by: None` when Kodi was not running.

The wait follows the processes that were running when `Application.Quit` was sent, not just
the package name: Android can start a new, empty `org.xbmc.kodi` process seconds after Kodi
exits. Once the quitting Kodi has gone, such a process is force-stopped while Kodi is not the
app in front (`respawned_process_stopped` lists its pid); a Kodi that is on screen again raises
`restarted`, and one whose foreground app cannot be read raises `respawned`, both leaving it
running.

### `push_verified(local, remote, mode=None)`

`remote` must be an absolute file path under `/sdcard`, `/storage/emulated/0` or
`/data/local/tmp`. The file is pushed to a unique temporary name beside `remote`, its SHA-256 is
computed on the Shield and compared with the local file, and only then moved over `remote`; the
result is checked again. A failed check leaves the previous file in place (`verify_failed`); the
temporary file is always removed. `mode` (octal string such as `"644"`) defaults to the existing
file's permissions. Stopping Kodi first, if it could overwrite the file, is the caller's job.

## Safety

`adb`, `shell` and `rpc` are unrestricted: they exist for programs. Never expose them to a model
as tools; the MCP server offers only its fixed, guarded tool set. Mutating helpers need
`Config(allow_writes=True)`, as the server's write tools need `NVIDIA_MCP_ALLOW_WRITES=1`, and
run the same TV guard. They have no override flags.
