"""Bounded HTTP requests and shell-quoted ADB operations on one configured Shield."""

import json
import shlex
import subprocess
import tempfile
import threading
from pathlib import Path

import httpx

from .config import Config, ShieldError


class Transport:
    def __init__(self, config: Config):
        self.c = config
        self.http = httpx.Client(
            timeout=httpx.Timeout(20, connect=3), follow_redirects=False, trust_env=False
        )

    def close(self):
        self.http.close()

    def request(self, url, method="POST", body=None, manager=False):
        headers = {"Authorization": "Bearer " + self.c.manager_token} if manager else {}
        auth = None if manager else (self.c.username, self.c.password)
        try:
            with self.http.stream(method, url, json=body, headers=headers, auth=auth) as response:
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
            self.c.url() + "/jsonrpc",
            body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
        if not isinstance(result, dict):
            raise ShieldError("Invalid Kodi JSON-RPC response", "invalid_response")
        if "error" in result:
            error = result["error"]
            raise ShieldError(
                f"Kodi {method} failed ({error.get('code', 'unknown')}): check supported parameters"
            )
        if "result" not in result:
            raise ShieldError("Invalid Kodi JSON-RPC response")
        return result["result"]

    def manager(self, path, method="GET", body=None):
        if not self.c.manager_token:
            raise ShieldError(
                "This tool needs optional Kodi Manager 0.3.9/0.4.x and KODI_MANAGER_TOKEN; core ADB/Kodi tools work without it"
            )
        result = self.request(self.c.url(True) + path, method, body, manager=True)
        if not isinstance(result, dict):
            raise ShieldError("Invalid Kodi Manager response", "invalid_response")
        if result.get("ok") is not True:
            # Manager errors can include supplied setting values or paths. Do not echo them.
            raise ShieldError(
                "Kodi Manager rejected the request; inspect version, permissions and current layout revision"
            )
        return result["data"]

    def adb(self, *args, limit=1_000_000, timeout=30, device=True):
        command = [self.c.adb_path] + (["-s", self.c.serial] if device else []) + list(args)
        try:
            # Spooled output avoids unbounded pipe buffers, including Android logcat.
            import tempfile

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

    def download(self, remote, destination, limit=600_000_000, timeout=180):
        """Stream an explicitly chosen remote file to private storage, with byte/time bounds."""
        command = [self.c.adb_path, "-s", self.c.serial, "exec-out", "cat", remote]
        return self.stream_to_file(command, destination, limit, timeout)

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
