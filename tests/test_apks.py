import io
import json
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

from nvidia_mcp import android_tools
from nvidia_mcp.apks import ApkOperations
from nvidia_mcp.config import ShieldError
from nvidia_mcp.files import digest

SIGNER = "a" * 64


def test_current_aapt2_badging_uses_min_sdk_version():
    metadata = android_tools.parse_badging(
        "package: name='org.xbmc.kodi' versionCode='2103000' versionName='21.3'\nminSdkVersion:'21'\nnative-code: 'arm64-v8a'\n"
    )
    assert metadata["min_sdk"] == 21 and metadata["abis"] == ["arm64-v8a"]


def apk_bytes(
    version=1, package="dev.example.player", split="", signer=SIGNER, abi="armeabi-v7a", sdk=23
):
    return json.dumps(
        {
            "version": version,
            "package": package,
            "split": split,
            "signer": signer,
            "abi": abi,
            "sdk": sdk,
        }
    ).encode()


@pytest.fixture
def apk_env(ops, monkeypatch, tmp_path):
    class Device:
        def __init__(self):
            self.c = ops.c
            self.installed = {"/data/app/example/base.apk": apk_bytes()}
            self.pushed = {}
            self.foreground = "com.google.android.tvlauncher"
            self.running = set()
            self.calls = []
            self.install_result = "Success"
            self.session = []
            self.wrong_version = False
            self.fail_snapshot = False

        def rpc(self, *args):
            return []

        def shell(self, *args, **kwargs):
            self.calls.append(args)
            if args[:2] == ("getprop", "ro.product.cpu.abilist"):
                return "armeabi-v7a,arm64-v8a"
            if args[:2] == ("getprop", "ro.build.version.sdk"):
                return "30"
            if args[:3] == ("pm", "list", "packages"):
                return "\n".join(
                    sorted(
                        {
                            "package:" + json.loads(data)["package"]
                            for data in self.installed.values()
                        }
                    )
                )
            if args[:2] == ("pm", "path"):
                return "\n".join(
                    "package:" + path
                    for path, data in self.installed.items()
                    if json.loads(data)["package"] == args[2]
                )
            if args[:2] == ("dumpsys", "package"):
                value = next(
                    json.loads(data)
                    for data in self.installed.values()
                    if json.loads(data)["package"] == args[2]
                )
                return f"versionCode={value['version']} minSdk=23\nversionName=test\npkgFlags=[ HAS_CODE ]"
            if args[0] == "sha256sum":
                return digest((self.installed | self.pushed)[args[1]]) + "  " + args[1]
            if args == ("dumpsys", "activity", "activities"):
                return f"mResumedActivity: {self.foreground}/.Main" if self.foreground else ""
            if args[:2] == ("sh", "-c"):
                return "123" if any(f"pidof {pkg} " in args[2] for pkg in self.running) else ""
            if args[0] == "readlink":
                return "/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi"
            if args[:2] == ("pm", "install"):
                self.commit([args[-1]])
                return self.install_result
            if args[:2] == ("pm", "install-create"):
                return "Success: created install session [42]"
            if args[:2] == ("pm", "install-write"):
                self.session.append(args[-1])
                return "Success: streamed 10 bytes"
            if args[:2] == ("pm", "install-commit"):
                self.commit(self.session)
                return self.install_result
            return ""

        def commit(self, paths):
            if self.install_result == "Success" and not self.wrong_version:
                self.installed = {
                    f"/data/app/updated/{i}.apk": self.pushed[path] for i, path in enumerate(paths)
                }

        def adb(self, *args, **kwargs):
            self.calls.append(args)
            if args[0] == "push":
                self.pushed[args[2]] = Path(args[1]).read_bytes()
            return b""

        def download(self, remote, destination, **kwargs):
            destination.write_bytes(self.installed[remote])

        def stream_to_file(self, command, destination, limit, timeout):
            if self.fail_snapshot:
                raise ShieldError("snapshot unavailable")
            with tarfile.open(destination, "w") as archive:
                for name in ("addons", "userdata"):
                    member = tarfile.TarInfo(name)
                    member.type = tarfile.DIRTYPE
                    archive.addfile(member)
                member = tarfile.TarInfo("userdata/guisettings.xml")
                data = b"<settings>synthetic-private-token</settings>"
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))

    device = Device()
    ops.t = device
    ops.apks = ApkOperations(ops)
    ops.apks.c = replace(ops.c, mount=None)

    def sdk_tool(command):
        value = json.loads(Path(command[-1]).read_bytes())
        if "verify" in command:
            if value["signer"] == "invalid":
                raise ShieldError("Android SDK tool rejected the APK")
            return f"Signer #1 certificate SHA-256 digest: {value['signer']}\n"
        return f"package: name='{value['package']}' versionCode='{value['version']}' versionName='test' split='{value['split']}'\nsdkVersion:'{value['sdk']}'\nnative-code: '{value['abi']}'\n"

    monkeypatch.setattr(android_tools, "run_tool", sdk_tool)

    def candidate(**kwargs):
        path = tmp_path / f"candidate-{len(list(tmp_path.glob('candidate-*.apk')))}.apk"
        path.write_bytes(apk_bytes(version=2, **kwargs))
        return str(path)

    return ops, device, candidate


def test_verified_upgrade_stages_exact_bytes_and_preserves_original(apk_env):
    ops, device, candidate = apk_env
    source = candidate()
    preview = ops.apks.preview([source])
    assert not any(call[:2] == ("pm", "install") or call[0] == "push" for call in device.calls)
    Path(source).write_bytes(b"changed after preview")
    result = ops.apks.apply(preview["preview_id"])
    assert result["status"] == "verified"
    backup = ops.c.state / "apk_backups" / result["backup_id"]
    assert (backup / "0.apk").read_bytes() == apk_bytes()
    assert ops.apks.backups()["backups"][0]["status"] == "verified"
    with pytest.raises(ShieldError, match="missing or expired"):
        ops.apks.apply(preview["preview_id"])


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"signer": "b" * 64}, "signers differ"),
        ({"signer": "invalid"}, "rejected"),
        ({"abi": "x86_64"}, "architecture"),
        ({"sdk": 35}, "newer Android"),
    ],
)
def test_incompatible_or_untrusted_apks_never_reach_installer(apk_env, kwargs, reason):
    ops, device, candidate = apk_env
    with pytest.raises(ShieldError, match=reason):
        ops.apks.preview([candidate(**kwargs)])
    assert not any(call[0] == "push" or call[:2] == ("pm", "install") for call in device.calls)


def test_new_apps_need_independent_signer_trust(apk_env):
    ops, device, candidate = apk_env
    device.installed = {}
    source = candidate()
    with pytest.raises(ShieldError, match="independently trusted"):
        ops.apks.preview([source])
    preview = ops.apks.preview([source], [SIGNER])
    assert ops.apks.apply(preview["preview_id"])["status"] == "verified"


@pytest.mark.parametrize("state", ["running", "youtube", "unknown", "expired", "stale", "tampered"])
def test_busy_unknown_stale_expired_and_tampered_previews_are_refused(apk_env, state):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    plan = ops.apks.plans[preview["preview_id"]]
    if state == "running":
        device.running.add("dev.example.player")
    elif state == "youtube":
        device.foreground = "com.google.android.youtube.tv"
    elif state == "unknown":
        device.foreground = ""
    elif state == "expired":
        plan["created"] -= 601
    elif state == "stale":
        device.installed["/data/app/example/base.apk"] = apk_bytes(version=3)
    elif state == "tampered":
        Path(plan["paths"][0]).write_bytes(apk_bytes(version=4))
    with pytest.raises(ShieldError):
        ops.apks.apply(preview["preview_id"])
    assert not any(call[0] == "push" for call in device.calls)


@pytest.mark.parametrize("wrong_version", [False, True])
def test_install_failure_or_failed_readback_keeps_recovery_bundle_without_retry(
    apk_env, wrong_version
):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    device.wrong_version = wrong_version
    if not wrong_version:
        device.install_result = "Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE private-token]"
    with pytest.raises(ShieldError, match="[Rr]ecovery bundle") as exc:
        ops.apks.apply(preview["preview_id"])
    assert "private-token" not in str(exc.value)
    assert sum(call[:2] == ("pm", "install") for call in device.calls) == 1
    assert not any(call[:2] == ("pm", "uninstall") for call in device.calls)
    assert ops.apks.backups()["backups"][0]["status"] == "failed_after_transfer"
    assert ops.apks.backups()["backups"][0]["original_version_code"] == 1


def test_split_apks_are_validated_and_installed_in_one_session(apk_env):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate(), candidate(split="config.arm64", abi="arm64-v8a")])
    assert ops.apks.apply(preview["preview_id"])["status"] == "verified"
    assert sum(call[:2] == ("pm", "install-commit") for call in device.calls) == 1
    with pytest.raises(ShieldError, match="share package"):
        ops.apks.preview([candidate(), candidate(split="config.arm64", signer="b" * 64)])


@pytest.mark.parametrize("fail_snapshot", [False, True])
def test_kodi_upgrade_requires_a_validated_full_data_snapshot(apk_env, fail_snapshot):
    ops, device, candidate = apk_env
    device.installed["/data/app/example/base.apk"] = apk_bytes(package="org.xbmc.kodi")
    preview = ops.apks.preview([candidate(package="org.xbmc.kodi")])
    device.fail_snapshot = fail_snapshot
    if fail_snapshot:
        with pytest.raises(ShieldError, match="[Rr]ecovery bundle"):
            ops.apks.apply(preview["preview_id"])
        assert not any(call[0] == "push" for call in device.calls)
    else:
        result = ops.apks.apply(preview["preview_id"])
        backup = ops.apks.backups()["backups"][0]
        assert backup["kodi_data"]["members"] == 3
        assert "synthetic-private-token" not in json.dumps(result) + json.dumps(backup)


def test_symlink_and_corrupt_original_backups_are_refused(apk_env, tmp_path):
    ops, device, candidate = apk_env
    source = candidate()
    link = tmp_path / "link.apk"
    try:
        link.symlink_to(source)
    except OSError:
        pytest.skip("Symlinks unavailable on this platform")
    with pytest.raises(ShieldError, match="symlink"):
        ops.apks.preview([str(link)])
    preview = ops.apks.preview([source])
    Path(ops.apks.plans[preview["preview_id"]]["originals"][0]).write_bytes(apk_bytes(version=5))
    with pytest.raises(ShieldError, match="Original APK backup changed"):
        ops.apks.apply(preview["preview_id"])
    assert not any(call[0] == "push" for call in device.calls)


def test_mounted_kodi_snapshot_is_complete_and_refuses_external_links(apk_env, tmp_path):
    ops, device, candidate = apk_env
    mount = tmp_path / "mount"
    (mount / "addons").mkdir(parents=True)
    (mount / "userdata/profiles/kids").mkdir(parents=True)
    (mount / "userdata/profiles/kids/guisettings.xml").write_text("<settings>private</settings>")
    ops.apks.c = replace(ops.apks.c, mount=mount)
    backup = tmp_path / "backup"
    backup.mkdir()
    result = ops.apks.kodi_snapshot(backup)
    assert result["members"] == 5
    with tarfile.open(backup / "kodi-data.tar") as archive:
        assert (
            archive.extractfile("userdata/profiles/kids/guisettings.xml").read()
            == b"<settings>private</settings>"
        )
    try:
        (mount / "userdata/link").symlink_to(tmp_path)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ShieldError, match="unsupported links"):
        ops.apks.kodi_snapshot(backup)


def test_corrupt_remote_kodi_snapshot_blocks_all_transfers(apk_env):
    ops, device, candidate = apk_env
    device.installed["/data/app/example/base.apk"] = apk_bytes(package="org.xbmc.kodi")
    preview = ops.apks.preview([candidate(package="org.xbmc.kodi")])
    device.stream_to_file = lambda command, destination, limit, timeout: destination.write_bytes(
        b"not a tar archive"
    )
    with pytest.raises(ShieldError, match="backup could not be validated"):
        ops.apks.apply(preview["preview_id"])
    assert not any(call[0] == "push" for call in device.calls)


@pytest.mark.parametrize("failure", ["corrupt_transfer", "tv_started"])
def test_transfer_corruption_and_viewing_start_block_installation(apk_env, failure):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    original = device.adb

    def transfer(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0] == "push":
            if failure == "corrupt_transfer":
                device.pushed[args[2]] = b"corrupt"
            else:
                device.foreground = "com.google.android.youtube.tv"
        return result

    device.adb = transfer
    with pytest.raises(ShieldError):
        ops.apks.apply(preview["preview_id"])
    assert not any(call[:2] == ("pm", "install") for call in device.calls)
    assert any(call[:2] == ("rm", "-f") for call in device.calls)
    assert ops.apks.backups()["backups"][0]["status"] == "failed_after_transfer"


def test_failed_split_write_abandons_session_and_never_commits(apk_env):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate(), candidate(split="config.arm64", abi="arm64-v8a")])
    original = device.shell

    def shell(*args, **kwargs):
        if args[:2] == ("pm", "install-write"):
            device.calls.append(args)
            return "Failure [INSUFFICIENT_STORAGE]"
        return original(*args, **kwargs)

    device.shell = shell
    with pytest.raises(ShieldError, match="could not stage"):
        ops.apks.apply(preview["preview_id"])
    assert not any(call[:2] == ("pm", "install-commit") for call in device.calls)
    assert any(call[:2] == ("pm", "install-abandon") for call in device.calls)
