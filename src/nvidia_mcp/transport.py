"""Bounded HTTP requests and shell-quoted ADB operations on one configured Shield."""

import json
import shlex
import subprocess

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
                    raise ShieldError("Authentication denied: check local Kodi/Manager credentials")
                if response.status_code != 200:
                    raise ShieldError(f"Device HTTP request failed ({response.status_code})")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 4_000_000:
                        raise ShieldError("Device response exceeds 4 MB; narrow the request")
                return json.loads(data)
        except (httpx.HTTPError, ValueError):
            raise ShieldError(
                "Cannot reach device HTTP service: check IP, port and Kodi HTTP control"
            ) from None

    def rpc(self, method, params=None):
        result = self.request(
            self.c.url() + "/jsonrpc",
            body={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )
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
                "This tool needs optional Kodi Manager 0.3.9/0.4.0 and KODI_MANAGER_TOKEN; core ADB/Kodi tools work without it"
            )
        result = self.request(self.c.url(True) + path, method, body, manager=True)
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
                    raise ShieldError("ADB timed out; check the Shield connection") from None
                if proc.returncode:
                    raise ShieldError(
                        "ADB operation failed: check debugging authorization, device state and file permissions"
                    )
                out.seek(0)
                data = out.read(limit + 1)
                if len(data) > limit:
                    raise ShieldError("ADB output exceeds the limit; narrow the request")
                return data
        except FileNotFoundError:
            raise ShieldError(
                "ADB not found: install official Android Platform Tools and set ADB_PATH"
            ) from None

    def shell(self, *args, **kwargs):
        return (
            self.adb("shell", shlex.join(args), **kwargs).decode("utf-8", errors="replace").strip()
        )
