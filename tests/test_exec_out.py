"""M2: exec-out reads verify exit status/existence instead of returning error text as content."""

import re
import shlex

import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.files import Files
from nvidia_mcp.transport import Transport, checked_script, split_status, strip_status

ROOT = "/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi"


class FakeAdb(Transport):
    """Real Transport logic over a fake device filesystem (no subprocess)."""

    def __init__(self, files, hide_missing=False):
        super().__init__(Config(host="127.0.0.1", remote_root=ROOT))
        self.files = files
        self.hide_missing = hide_missing

    def adb(self, *args, limit=1_000_000, timeout=30, device=True):
        if args[0] == "shell":
            argv = shlex.split(args[1])
            if argv[:2] == ["readlink", "-f"]:
                return argv[2].encode()
            if argv[:2] == ["sh", "-c"]:
                present = argv[-1] in self.files or self.hide_missing
                return b"present" if present else b"missing"
            raise AssertionError(argv)
        assert args[0] == "exec-out"
        script = args[1]
        token = re.search(r"echo (__nvidia_mcp_exit_[0-9a-f]+__)\$\?", script)[1]
        argv = shlex.split(script.split(" 2>/dev/null;")[0])
        path = argv[-1]
        if path not in self.files:
            # head writes its error to stderr, which exec-out merges into stdout.
            body, code = f"{argv[0]}: {path}: No such file or directory\n".encode(), 1
        else:
            body, code = self.files[path], 0
        return body + f"\n{token}{code}\n".encode()


def test_missing_file_is_an_error_not_content():
    transport = FakeAdb({})
    with pytest.raises(ShieldError, match="not found") as exc:
        Files(transport).read("userdata/advancedsettings.xml")
    assert exc.value.kind == "not_found"


def test_nonzero_exit_is_an_error_even_if_existence_check_passes():
    transport = FakeAdb({}, hide_missing=True)
    with pytest.raises(ShieldError, match="exit 1"):
        Files(transport).read("userdata/advancedsettings.xml")
    with pytest.raises(ShieldError, match="exit 1"):
        Files(transport).tail("temp/kodi.log", 10)


def test_existing_file_round_trips_exact_bytes():
    data = b"<advancedsettings>\n</advancedsettings>\n\n"
    transport = FakeAdb({ROOT + "/userdata/advancedsettings.xml": data})
    assert Files(transport).read("userdata/advancedsettings.xml") == data


def test_missing_mounted_file_and_log(tmp_path):
    transport = Transport(Config(host="127.0.0.1", mount=tmp_path, state=tmp_path / "s"))
    with pytest.raises(ShieldError, match="not found"):
        Files(transport).read("userdata/nothing.xml")
    with pytest.raises(ShieldError, match="not found"):
        Files(transport).tail("temp/kodi.log", 5)
    transport.close()


def test_status_trailer_parsing(tmp_path):
    script, token = checked_script(["cat", "/x y"])
    assert script.startswith("cat '/x y' 2>/dev/null;")
    assert split_status(b"abc\n" + token.encode() + b"0\n", token) == (b"abc", 0)
    with pytest.raises(ShieldError, match="unknown"):
        split_status(b"abc", token)
    target = tmp_path / "download.bin"
    target.write_bytes(b"payload\n" + token.encode() + b"0\n")
    assert strip_status(target, token) == len(b"payload") and target.read_bytes() == b"payload"
    target.write_bytes(b"partial\n" + token.encode() + b"2\n")
    with pytest.raises(ShieldError, match="exit 2"):
        strip_status(target, token)
    assert not target.exists()


def test_download_checks_existence(tmp_path):
    transport = FakeAdb({})
    with pytest.raises(ShieldError, match="missing"):
        transport.download("/data/app/x/base.apk", tmp_path / "o.apk")
    assert not (tmp_path / "o.apk").exists()
