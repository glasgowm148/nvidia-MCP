"""M2: exec-out reads verify exit status/existence instead of returning error text as content."""

import os
import re
import shlex
import shutil
import subprocess

import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.files import Files
from nvidia_mcp.transport import (
    Transport,
    adb_error,
    checked_script,
    split_status,
    strip_status,
)

ROOT = "/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi"


class FakeAdb(Transport):
    """Real Transport logic over a fake device filesystem (no subprocess)."""

    def __init__(self, files, hide_missing=False, exit_status=True, missing_dirs=()):
        super().__init__(Config(host="127.0.0.1", remote_root=ROOT))
        self.files = files
        self.hide_missing = hide_missing
        self.exit_status = exit_status  # Old adb shell protocols drop it.
        self.missing_dirs = missing_dirs

    def adb(self, *args, limit=1_000_000, timeout=30, device=True):
        if args[0] == "shell":
            argv = shlex.split(args[1])
            if argv[:2] == ["readlink", "-f"]:
                # toybox: the last component may be missing, its parent folder may not.
                if argv[2].rsplit("/", 1)[0] in self.missing_dirs:
                    if self.exit_status:
                        raise adb_error(b"")
                    return b""
                return argv[2].encode() + b"\n"
            if argv[:2] == ["sh", "-c"]:
                present = argv[-1] in self.files or self.hide_missing
                return b"present" if present else b"missing"
            raise AssertionError(argv)
        assert args[0] == "exec-out"
        script = args[1]
        token = re.search(r"echo (__nvidia_mcp_exit_[0-9a-f]+__)\$s", script)[1]
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


@pytest.mark.parametrize("exit_status", [True, False])
def test_missing_parent_folder_is_not_found(exit_status):
    # An add-on that never saved settings has no userdata/addon_data/<id>/ folder.
    folder = ROOT + "/userdata/addon_data/plugin.video.example"
    transport = FakeAdb({}, exit_status=exit_status, missing_dirs={folder})
    with pytest.raises(ShieldError) as exc:
        Files(transport).read("userdata/addon_data/plugin.video.example/settings.xml")
    assert exc.value.kind == "not_found"


def test_trailing_space_selects_that_exact_file():
    transport = FakeAdb({ROOT + "/userdata/a.xml": b"plain", ROOT + "/userdata/a.xml ": b"space"})
    files = Files(transport)
    assert files.location("userdata/a.xml ") == ROOT + "/userdata/a.xml "
    assert files.read("userdata/a.xml ") == b"space"
    assert files.read("userdata/a.xml") == b"plain"


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


def test_status_trailer_edges(tmp_path):
    _script, token = checked_script(["cat", "/x"])
    # A command with no output still prints the newline before the token.
    assert split_status(b"\n" + token.encode() + b"0\n", token) == (b"", 0)
    target = tmp_path / "download.bin"
    for cut in (b"", b"\n", b"1x\n", b"-1\n"):
        # A stream cut right after the token (or a garbled status) is not a status.
        with pytest.raises(ShieldError, match="status is unknown"):
            split_status(b"data\n" + token.encode() + cut, token)
        target.write_bytes(b"partial\n" + token.encode() + cut)
        with pytest.raises(ShieldError, match="status is unknown"):
            strip_status(target, token)
        assert not target.exists()


@pytest.mark.skipif(os.name != "posix" or not shutil.which("sh"), reason="needs a POSIX shell")
@pytest.mark.parametrize(
    "command,payload,code",
    [("printf partial; exit 3", b"partial", 3), ("printf whole", b"whole", 0)],
)
def test_status_trailer_reports_the_commands_exit_code_in_a_real_shell(command, payload, code):
    # Regression: "$?" after the bare "echo" was always 0, so failed tar/cat looked successful.
    script, token = checked_script(["sh", "-c", command])
    out = subprocess.run(["sh", "-c", script], capture_output=True, timeout=10, check=True)
    assert split_status(out.stdout, token) == (payload, code)


def test_download_checks_existence(tmp_path):
    transport = FakeAdb({})
    with pytest.raises(ShieldError, match="missing"):
        transport.download("/data/app/x/base.apk", tmp_path / "o.apk")
    assert not (tmp_path / "o.apk").exists()
