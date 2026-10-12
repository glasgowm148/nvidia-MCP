"""Bounded HTTP requests and shell-quoted ADB operations on one configured Shield."""

import json
import re
import shlex
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

import httpx

from . import privacy
from .config import Config, ShieldError

KODI_ROUTES = ("direct", "forward", "auto")


class Transport:
    def __init__(self, config: Config, kodi_route=None):
        """``kodi_route`` overrides config.http_route for Kodi and Manager: ``direct`` (LAN HTTP to the
        configured host), ``forward`` (through an ``adb forward``
        to 127.0.0.1, for processes the OS blocks from the LAN, such as macOS Local Network
        permission) or ``auto`` (direct when Kodi answers there, otherwise forward)."""
        kodi_route = config.http_route if kodi_route is None else kodi_route
        if kodi_route not in KODI_ROUTES:
            raise ValueError("kodi_route must be one of " + ", ".join(KODI_ROUTES))
        self.c = config
        self.kodi_route = kodi_route
        self.forward_port = None
        self.manager_forward_port = None
        self._kodi_url = None
        self._manager_url = None
        self._route_lock = threading.Lock()
        self.http = httpx.Client(
            timeout=httpx.Timeout(20, connect=3), follow_redirects=False, trust_env=False
        )

    def close(self):
        try:
            self.remove_forward()
        finally:
            self.http.close()

    def kodi_url(self):
        """Base URL for Kodi JSON-RPC under the chosen route; sets up the forward on first use."""
        return self.service_url()

    def service_url(self, manager=False):
        if self.kodi_route == "direct":
            return self.c.url(manager)
        with self._route_lock:
            attr = "_manager_url" if manager else "_kodi_url"
            base = getattr(self, attr)
            if base is None:
                if self.kodi_route == "auto" and self.answers(self.c.url(manager), manager):
                    base = self.c.url(manager)
                else:
                    base = self.forward_kodi(manager)
                setattr(self, attr, base)
            return base

    def answers(self, base, manager=False):
        """True when something at ``base`` answers HTTP (an auth refusal counts as an answer)."""
        try:
            if manager:
                self.request(base + "/api/health", "GET", manager=True)
            else:
                self.request(
                    base + "/jsonrpc", body={"jsonrpc": "2.0", "id": 1, "method": "JSONRPC.Ping"}
                )
        except ShieldError as exc:
            return exc.kind not in ("unreachable", "timeout")
        return True

    def forward_kodi(self, manager=False):
        """``adb forward tcp:0 tcp:<kodi port>``: the adb server, not this process, opens the
        LAN connection. Returns the local base URL."""
        remote_port = self.c.manager_port if manager else self.c.kodi_port
        out = self.adb("forward", "tcp:0", f"tcp:{remote_port}", timeout=15)
        port = out.decode("ascii", "replace").strip()
        if not port.isdigit() or not 0 < int(port) < 65536:
            raise ShieldError("adb forward did not report a local port", "device_error")
        setattr(self, "manager_forward_port" if manager else "forward_port", int(port))
        return f"http://127.0.0.1:{port}"

    def remove_forward(self):
        with self._route_lock:
            ports = (self.forward_port, self.manager_forward_port)
            self.forward_port = self.manager_forward_port = None
            self._kodi_url = self._manager_url = None
            for port in ports:
                if port is not None:
                    try:
                        self.adb("forward", "--remove", f"tcp:{port}", timeout=15)
                    except ShieldError:
                        pass  # The adb server may already be gone; the forward goes with it.

    @property
    def known_secrets(self):
        return (self.c.password, self.c.manager_token)

    def request(self, url, method="POST", body=None, manager=False):
        headers = {"Authorization": "Bearer " + self.c.manager_token} if manager else {}
        auth = None if manager else (self.c.username, self.c.password)
        try:
            with self.http.stream(method, url, json=body, headers=headers, auth=auth) as response:
                if manager and response.status_code != 200:
                    raise manager_error(
                        response.status_code, read_bounded(response, 64_000), self.known_secrets
                    )
                if response.status_code in (401, 403):
                    raise ShieldError(
                        "Authentication denied: check local Kodi/Manager credentials",
                        "authentication_denied",
                    )
                if response.status_code != 200:
                    raise ShieldError(
                        f"Device HTTP request failed ({response.status_code})", "service_error"
                    )
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 4_000_000:
                        raise ShieldError("Device response exceeds 4 MB; narrow the request")
                return json.loads(data)
        except httpx.TimeoutException:
            raise ShieldError(
                "Cannot reach device HTTP service: request timed out", "timeout"
            ) from None
        except httpx.HTTPError:
            raise ShieldError(
                "Cannot reach device HTTP service: check IP, port and Kodi HTTP control",
                "unreachable",
            ) from None
        except ValueError:
            raise ShieldError(
                "Device HTTP service returned invalid JSON", "invalid_response"
            ) from None

    def rpc(self, method, params=None):
        result = self.request(
            self.kodi_url() + "/jsonrpc",
            body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
        if not isinstance(result, dict):
            raise ShieldError("Invalid Kodi JSON-RPC response", "invalid_response")
        if "error" in result:
            error = result["error"] if isinstance(result["error"], dict) else {}
            detail = str(error.get("message") or "")[:200]
            data = error.get("data")
            if data is not None:
                # Kodi puts the offending parameter/stack here; redact and bound it.
                detail += " " + json.dumps(privacy.scrub(data, (self.c.password,)))[:500]
            raise ShieldError(
                f"Kodi {method} failed ({error.get('code', 'unknown')}): "
                + (
                    privacy.text(detail.strip(), (self.c.password,)) or "check supported parameters"
                ),
                "rpc_error",
            )
        if "result" not in result:
            raise ShieldError("Invalid Kodi JSON-RPC response", "invalid_response")
        return result["result"]

    def manager(self, path, method="GET", body=None):
        if not self.c.manager_token:
            raise ShieldError(
                "This tool needs optional Kodi Manager (0.4+; widget-cache tools need 0.6+) and "
                "KODI_MANAGER_TOKEN; core ADB/Kodi tools work without it",
                "not_configured",
            )
        result = self.request(self.service_url(True) + path, method, body, manager=True)
        if not isinstance(result, dict):
            raise ShieldError("Invalid Kodi Manager response", "invalid_response")
        if result.get("ok") is not True:
            raise manager_error(200, json.dumps(result).encode(), self.known_secrets)
        return result["data"]

    def adb(self, *args, limit=1_000_000, timeout=30, device=True):
        command = [self.c.adb_path] + (["-s", self.c.serial] if device else []) + list(args)
        try:
            # Spooled output avoids unbounded pipe buffers, including Android logcat.
            with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
                proc = subprocess.Popen(command, stdout=out, stderr=err)
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    raise ShieldError(
                        "ADB timed out; check the Shield connection", "timeout"
                    ) from None
                if proc.returncode:
                    err.seek(0)
                    raise adb_error(err.read(8192))
                out.seek(0)
                data = out.read(limit + 1)
                if len(data) > limit:
                    raise ShieldError("ADB output exceeds the limit; narrow the request")
                return data
        except FileNotFoundError:
            raise ShieldError(
                "ADB not found: install official Android Platform Tools and set ADB_PATH",
                "missing_dependency",
            ) from None
        except PermissionError:
            raise ShieldError(
                "ADB could not start: check ADB_PATH points to the executable and allow it in OS permissions",
                "permission_denied",
            ) from None
        except OSError:
            raise ShieldError(
                "ADB could not start: use official Platform Tools for this computer's OS and architecture",
                "missing_dependency",
            ) from None

    def is_file(self, remote):
        """``test -f`` with a printed result: old adb shell protocols drop exit codes."""
        answer = self.shell(
            "sh",
            "-c",
            'if [ -f "$1" ] && [ -r "$1" ]; then echo present; else echo missing; fi',
            "sh",
            remote,
        )
        return answer == "present"

    def exec_out(self, argv, limit, timeout=30):
        """Run argv through exec-out and fail on a non-zero exit instead of returning stderr."""
        script, token = checked_script(argv)
        data = self.adb("exec-out", script, limit=limit + TRAILER, timeout=timeout)
        payload, code = split_status(data, token)
        if code != 0:
            raise ShieldError(
                f"Device command failed (exit {code}); the file may be missing or unreadable",
                "device_error",
            )
        if len(payload) > limit:
            raise ShieldError("ADB output exceeds the limit; narrow the request")
        return payload

    def download(self, remote, destination, limit=600_000_000, timeout=180):
        """Stream an explicitly chosen remote file to private storage, with byte/time bounds."""
        if not self.is_file(remote):
            raise ShieldError("Device file is missing or unreadable", "not_found")
        script, token = checked_script(["cat", remote])
        command = [self.c.adb_path, "-s", self.c.serial, "exec-out", script]
        self.stream_to_file(command, destination, limit + TRAILER, timeout)
        return strip_status(destination, token)

    def stream_to_file(self, command, destination, limit, timeout):
        """Internal subprocess helper; not exposed as an arbitrary command MCP tool."""
        destination = Path(destination)
        failures = []
        proc = None
        created = False
        try:
            target = destination.open("xb")
            created = True
            with target, tempfile.TemporaryFile() as err:
                destination.chmod(0o600)
                proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err)

                def pump():
                    count = 0
                    try:
                        while chunk := proc.stdout.read(65536):
                            count += len(chunk)
                            if count > limit:
                                raise ShieldError("Device download exceeds the byte limit")
                            target.write(chunk)
                    except Exception as exc:
                        failures.append(exc)
                        proc.kill()

                worker = threading.Thread(target=pump, daemon=True)
                worker.start()
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    failures.append(ShieldError("Device download timed out", "timeout"))
                worker.join(timeout=5)
                if worker.is_alive():
                    raise ShieldError("Device download did not finish", "timeout")
                proc.stdout.close()
                if failures:
                    raise failures[0]
                if proc.returncode:
                    err.seek(0)
                    raise adb_error(err.read(8192))
            return destination.stat().st_size
        except (OSError, ShieldError) as exc:
            if created:
                destination.unlink(missing_ok=True)
            if isinstance(exc, ShieldError):
                raise
            raise ShieldError(
                "Cannot download device file; check ADB and private storage",
                "missing_dependency" if isinstance(exc, FileNotFoundError) else "storage_error",
            ) from None

    def shell(self, *args, **kwargs):
        return (
            self.adb("shell", shlex.join(args), **kwargs).decode("utf-8", errors="replace").strip()
        )


TRAILER = 128
REMOTE_MODE = re.compile(r"[0-7]{3,4}")


def push_atomic(transport, source, remote, *, mode=None, before_commit=None):
    """Push ``source`` beside ``remote`` under a unique temporary name, optionally chmod it, run
    ``before_commit(temp)`` (which may raise to abandon the push), then ``mv -f`` it into place.
    The temporary file is always removed. Readback of the result is the caller's job."""
    if mode is not None and not REMOTE_MODE.fullmatch(mode):
        raise ShieldError("File mode must be octal digits such as 644", "invalid_request")
    temp = str(remote) + ".nvidia-mcp-" + uuid.uuid4().hex
    try:
        transport.adb("push", str(source), temp)
        if mode is not None:
            transport.shell("chmod", mode, temp)
        if before_commit is not None:
            before_commit(temp)
        transport.shell("mv", "-f", temp, str(remote))
    finally:
        transport.shell("rm", "-f", temp)


def remote_sha256(transport, path):
    """SHA-256 of a device file, computed on the Shield with toybox ``sha256sum``."""
    value = transport.shell("sha256sum", str(path), limit=2000).split()
    if not value or not re.fullmatch(r"[a-fA-F0-9]{64}", value[0]):
        raise ShieldError("Cannot checksum the device file", "device_error")
    return value[0].lower()


# Kodi Manager error codes (``{"ok": false, "error": {"code", "message"}}``) with their own
# remedy. None of them means the companion is missing or outdated.
MANAGER_ERRORS = {
    "write_disabled": "Kodi Manager has Write Mode turned off; the user can turn it on in Kodi "
    "Manager's settings on the TV (the token is fine)",
    "account_write_blocked": "Kodi Manager does not allow account changes from this client; "
    "make account changes on the TV",
    "origin_mismatch": "Kodi Manager rejected the request origin; check the configured host "
    "and KODI_MANAGER_PORT",
    "playback_active": "Kodi Manager refused because playback is active. Wait until viewing "
    "has finished; no change made",
}


def read_bounded(response, limit):
    data = bytearray()
    for chunk in response.iter_bytes():
        data.extend(chunk)
        if len(data) > limit:
            break
    return bytes(data[:limit])


def manager_error(status, raw, known=()):
    """A ShieldError from Kodi Manager's JSON error envelope.

    Surfaces the error ``code`` and a redacted, bounded ``message``. Only a 404 for an unknown
    route means the API is unsupported (an older Kodi Manager).
    """
    try:
        body = json.loads(raw)
    except ValueError:
        body = None
    body = body if isinstance(body, dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    code = error.get("code", body.get("code"))
    if not (isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,39}", code)):
        code = None
    message = error.get("message")
    detail = (
        privacy.text(message.strip()[:200], known)
        if isinstance(message, str) and message.strip()
        else ""
    )
    if status == 401 or (status == 403 and code in (None, "unauthorized", "forbidden")):
        return ShieldError(
            "Authentication denied: check KODI_MANAGER_TOKEN (the Kodi Manager bearer token)",
            "authentication_denied",
        )
    if status == 404 and code in (None, "not_found") and detail in ("", "Route not found"):
        return ShieldError(
            "Kodi Manager does not offer this API; it needs a newer Kodi Manager", "unsupported"
        )
    if code in MANAGER_ERRORS:
        return ShieldError(MANAGER_ERRORS[code] + (f" ({detail})" if detail else ""), code)
    label = f"{status}, {code}" if code else str(status)
    if status == 404:
        kind = "not_found"
    elif 400 <= status < 500 or status == 200:
        kind = "invalid_request"
    else:
        kind = "service_error"
    return ShieldError(
        f"Kodi Manager refused the request ({label})" + (f": {detail}" if detail else ""), kind
    )


def checked_script(argv):
    """Shell script that runs argv (stderr discarded) and appends a unique exit-status line."""
    token = "__nvidia_mcp_exit_" + uuid.uuid4().hex + "__"
    return f"{shlex.join(argv)} 2>/dev/null; echo; echo {token}$?", token


def split_status(data, token):
    marker = b"\n" + token.encode()
    index = data.rfind(marker)
    tail = data[index + len(marker) :].strip() if index >= 0 else b""
    if index < 0 or not tail.isdigit():
        raise ShieldError("Device command status is unknown; output discarded", "device_error")
    return data[:index], int(tail)


def strip_status(path, token):
    """Verify and remove the exit-status trailer from a streamed file; delete it on failure."""
    path = Path(path)
    try:
        with path.open("r+b") as handle:
            size = handle.seek(0, 2)
            start = max(0, size - TRAILER)
            handle.seek(start)
            payload, code = split_status(handle.read(), token)
            if code != 0:
                raise ShieldError(
                    f"Device command failed (exit {code}); download discarded", "device_error"
                )
            handle.truncate(start + len(payload))
    except (OSError, ShieldError) as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc, ShieldError):
            raise
        raise ShieldError("Cannot verify device download", "storage_error") from None
    return path.stat().st_size


def adb_error(raw):
    """Classify bounded stderr without returning device output or private paths."""
    message = raw.decode("utf-8", "replace").lower()
    if "unauthorized" in message or "authentication" in message:
        return ShieldError(
            "ADB authorization needed: select Allow on the Shield debugging prompt",
            "authorization_required",
        )
    if "offline" in message:
        return ShieldError("ADB device is offline: reconnect the configured Shield", "offline")
    if (
        "not found" in message
        or "no devices" in message
        or "cannot connect" in message
        or "failed to connect" in message
        or "connection refused" in message
    ):
        return ShieldError(
            "ADB cannot reach the configured Shield: check IP and network debugging", "unreachable"
        )
    if "permission denied" in message:
        return ShieldError(
            "ADB file permission denied: check the configured storage access", "permission_denied"
        )
    return ShieldError(
        "ADB operation failed: check device state and file permissions", "device_error"
    )
