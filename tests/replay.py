"""Replay a Shield from real captures in tests/fixtures/real at the ``adb``/HTTP boundary.

Only ``Transport.adb`` and ``Transport.request`` are replaced, so shell quoting, exec-out exit
status trailers, JSON-RPC envelopes and every parser run as they do against the device.

Provenance (all from the household's reference Shield: Android 11, Kodi 22.0 RC1, Projectivy):

- ``activities-*.txt``: ``dumpsys activity activities`` resumed-activity lines recorded by the
  deployment tool on 2026-10-11 (Kodi ``.Main``, Projectivy, Backdrop ``DreamActivity``).
- ``media_session-netflix-paused.txt``: a complete ``dumpsys media_session`` (2026-10-10).
  ``media_session-kodi-*.txt`` put Kodi's session lines captured on 2026-10-11 (``state=2``
  paused, ``state=1`` lingering after stop) into that same Android 11 frame;
  ``media_session-none.txt`` is the frame with no sessions (Kodi killed).
- ``kodi-exit-hang-after-playback.txt`` (14:07) and ``kodi-exit-hang-idle.txt`` (17:45):
  kodi.log excerpts of the two hung exits on 2026-10-11. ``kodi-exit-clean.txt``: a clean
  exit on 2026-10-10 (Kodi 22 beta 2, same Shield) that goes on past "Stopping all" to
  "Application stopped".
- ``dumpsys-meminfo-kodi-after-playback.txt``: Kodi after an hour of a film (2026-10-10).
- ``proc-meminfo-low.txt``: a real /proc/meminfo layout from this Shield (2026-10-09) with
  MemAvailable and SwapFree set to the values read on 2026-10-11 at 16:16 (467 MB; swap 96%).
- ``power-*.txt`` and ``logcat-events-kodi-killed.txt``: the ``mWakefulness`` values and the
  ``am_proc_died [0,10785,org.xbmc.kodi,200,2]`` record noted on 2026-10-11, in the dumps'
  line format (the event line's timestamp is approximate).
- JSON-RPC answers in ``scenarios/*.json`` are the responses recorded on 2026-10-10/11
  (``Application.GetProperties`` version, ``Player.GetActivePlayers``, paused player speed 0).

Anonymised: the Shield's LAN address is 192.168.0.20; no serials, MACs, accounts, tokens or IPTV
URLs are kept.
"""

import json
import shlex
from hashlib import sha256
from pathlib import Path

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.transport import Transport

REAL = Path(__file__).parent / "fixtures" / "real"
SCENARIOS = sorted(p.stem for p in (REAL / "scenarios").glob("*.json"))
KODI_ROOT = "/sdcard/Android/data/org.xbmc.kodi/files/.kodi"
PROFILES = (
    "<profiles><lastloaded>0</lastloaded><profile><id>0</id><name>Adults</name>"
    "<directory>special://masterprofile/</directory></profile><profile><id>1</id><name>Kids"
    "</name><directory>profiles/Kids/</directory></profile></profiles>"
)


def capture(name):
    return (REAL / "captures" / name).read_text(encoding="utf-8")


def load(name):
    return json.loads((REAL / "scenarios" / (name + ".json")).read_text(encoding="utf-8"))


def config(tmp_path, **overrides):
    values = dict(host="192.168.0.20", state=tmp_path / "private", allow_writes=True)
    values.update(overrides)
    return Config(**values)


class ReplayShield(Transport):
    """A Shield in one recorded scenario. ``calls`` lists (kind, detail) for every request."""

    def __init__(self, cfg, scenario, kodi_route="direct"):
        super().__init__(cfg, kodi_route)
        self.scenario = load(scenario) if isinstance(scenario, str) else scenario
        kodi = self.scenario["kodi"]
        self.kodi_running, self.http_up = kodi["running"], kodi["http"]
        self.activities = capture(self.scenario["activities"])
        self.media = capture(self.scenario["media_session"])
        self.power = capture(self.scenario["power"])
        self.answers_rpc = dict(self.scenario["rpc"])
        self.calls = []
        self.files = {
            f"{KODI_ROOT}/userdata/profiles.xml": PROFILES.encode(),
            f"{KODI_ROOT}/userdata/guisettings.xml": b'<settings version="2"></settings>',
        }
        if "kodi_log" in self.scenario:
            self.files[f"{KODI_ROOT}/temp/kodi.log"] = capture(self.scenario["kodi_log"]).encode()
        self.settings = {}
        self.corrupt_next_push = False
        self.lan_blocked = False  # Direct HTTP refused (macOS Local Network permission).

    # What changes on the TV once Application.Quit is sent, before the process ends.
    def after_quit(self):
        pass

    # --- adb ---------------------------------------------------------------------------------
    def adb(self, *args, limit=1_000_000, timeout=30, device=True):
        self.calls.append(("adb", args))
        if args[0] == "shell":
            return self.run(shlex.split(args[1])).encode()
        if args[0] == "exec-out":
            command, trailer = args[1].split(" 2>/dev/null; echo; echo ")
            token = trailer.removesuffix("$?")
            try:
                payload, code = self.run_bytes(shlex.split(command)), 0
            except FileNotFoundError:
                payload, code = b"", 1
            return payload + b"\n" + token.encode() + str(code).encode() + b"\n"
        if args[0] == "push":
            data = Path(args[1]).read_bytes()
            if self.corrupt_next_push:
                self.corrupt_next_push, data = False, data[:-1] + b"?"
            self.files[args[2]] = data
            return b"1 file pushed\n"
        if args[:2] == ("forward", "tcp:0"):
            return b"41234\n"
        if args[:2] == ("forward", "--remove"):
            return b""
        if args == ("get-state",):
            return b"device\n"
        raise AssertionError(f"unexpected adb call {args}")

    def run_bytes(self, argv):
        if argv[0] in ("cat", "head", "tail"):
            data = self.files.get(argv[-1])
            if data is None:
                raise FileNotFoundError(argv[-1])
            if argv[0] == "tail":
                count = int(argv[2])
                return b"\n".join(data.splitlines()[-count:])
            if argv[0] == "head":
                return data[: int(argv[2])]
            return data
        return self.run(argv).encode()

    def run(self, argv):
        if argv[:2] == ["sh", "-c"] and "pidof" in argv[2]:
            return "10785\n" if self.kodi_running else ""
        if argv[:2] == ["sh", "-c"] and "[ -f" in argv[2]:
            return "present\n" if argv[-1] in self.files else "missing\n"
        if argv == ["dumpsys", "activity", "activities"]:
            return self.activities
        if argv == ["dumpsys", "media_session"]:
            return self.media
        if argv == ["dumpsys", "power"]:
            return self.power
        if argv == ["dumpsys", "meminfo", "org.xbmc.kodi"]:
            name = self.scenario.get("kodi_meminfo")
            return (
                capture(name)
                if name and self.kodi_running
                else "No process found for: org.xbmc.kodi\n"
            )
        if argv == ["cat", "/proc/meminfo"]:
            return capture(self.scenario.get("meminfo", "proc-meminfo-low.txt"))
        if argv[:4] == ["logcat", "-b", "events", "-d"]:
            name = self.scenario.get("events")
            return capture(name) if name else ""
        if argv[:2] == ["am", "force-stop"]:
            self.kodi_running = self.http_up = False
            return ""
        if argv[:2] == ["am", "start"]:
            self.kodi_running = self.http_up = True
            self.activities = capture("activities-kodi.txt")
            return "Starting: Intent { cmp=org.xbmc.kodi/.Splash }\n"
        if argv[0] == "readlink":
            return argv[-1] + "\n"
        if argv[0] == "sha256sum":
            data = self.files.get(argv[1])
            return f"{sha256(data).hexdigest()}  {argv[1]}\n" if data is not None else ""
        if argv[:2] == ["stat", "-c"]:
            return "644\n"
        if argv[:2] == ["mv", "-f"]:
            self.files[argv[3]] = self.files.pop(argv[2])
            return ""
        if argv[:2] == ["rm", "-f"]:
            self.files.pop(argv[2], None)
            return ""
        if argv[0] in ("chmod", "input", "getprop", "df", "dumpsys", "cat"):
            return ""
        raise AssertionError(f"unexpected shell call {argv}")

    # --- Kodi HTTP -----------------------------------------------------------------------------
    def request(self, url, method="POST", body=None, manager=False):
        self.calls.append(("http", url, (body or {}).get("method")))
        if not self.http_up or (self.lan_blocked and not url.startswith("http://127.0.0.1:")):
            raise ShieldError(
                "Cannot reach device HTTP service: check IP, port and Kodi HTTP control",
                "unreachable",
            )
        name, params = body["method"], body.get("params") or {}
        if name == "Application.Quit":
            quit_ = self.scenario["on_quit"]
            self.http_up = False  # Kodi closes its web server while exiting.
            self.after_quit()
            if quit_["exits"]:
                self.kodi_running = False
                self.media = capture("media_session-none.txt")
                self.activities = capture("activities-projectivy.txt")
            if not quit_["http_answers"]:
                raise ShieldError("Cannot reach device HTTP service: request timed out", "timeout")
            return {"jsonrpc": "2.0", "id": 1, "result": "OK"}
        if name == "Settings.SetSettingValue":
            self.settings[params["setting"]] = params["value"]
            return {"jsonrpc": "2.0", "id": 1, "result": True}
        if name == "Settings.GetSettingValue":
            return {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"value": self.settings.get(params["setting"], False)},
            }
        if name in self.answers_rpc:
            return {"jsonrpc": "2.0", "id": 1, "result": self.answers_rpc[name]}
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32601, "message": "Method not found."},
        }

    def stream_to_file(self, command, destination, limit, timeout):
        """``download`` streams ``adb exec-out``; replay the same exec-out into a private file."""
        data = self.adb(*command[3:])
        if len(data) > limit:
            raise ShieldError("Device download exceeds the byte limit")
        with Path(destination).open("xb") as target:
            Path(destination).chmod(0o600)
            target.write(data)
        return len(data)

    def sent(self, *prefix):
        """adb shell commands sent, as argv lists, that start with ``prefix``."""
        found = []
        for kind, *detail in self.calls:
            if kind == "adb" and detail[0][0] == "shell":
                argv = shlex.split(detail[0][1])
                if tuple(argv[: len(prefix)]) == prefix:
                    found.append(argv)
        return found

    def rpc_sent(self, method):
        return [c for c in self.calls if c[0] == "http" and c[2] == method]
