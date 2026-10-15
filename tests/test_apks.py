import io
import json
import re
import tarfile
import time
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import media_session

from nvidia_mcp import android_tools, apks
from nvidia_mcp.apks import SNAPSHOT_EXCLUDES, ApkOperations
from nvidia_mcp.config import ShieldError
from nvidia_mcp.files import Files, digest

SIGNER = "a" * 64


def trailer(command, code=0):
    """What the device appends after a checked exec-out command (see transport.checked_script)."""
    token = re.search(r"echo (__nvidia_mcp_exit_[0-9a-f]+__)\$s", command[-1])[1]
    return f"\n{token}{code}\n".encode()


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
            self.tar_exit = 0
            self.media = ""
            self.players = []
            self.downloads = []
            self.serialno = "synthetic_device_001"

        def rpc(self, *args):
            return self.players

        def shell(self, *args, **kwargs):
            self.calls.append(args)
            if args == ("getprop", "ro.serialno"):
                return self.serialno
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
            if args == ("dumpsys", "media_session"):
                return "MEDIA SESSION SERVICE (dumpsys media_session)\n" + self.media
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
            self.downloads.append(remote)
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
            with open(destination, "ab") as handle:
                handle.write(trailer(command, self.tar_exit))

    device = Device()
    ops.t = device
    ops.files = Files(device)
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


def test_apk_preview_cannot_apply_to_replacement_device(apk_env):
    ops, device, candidate = apk_env
    plan = ops.apks.preview([candidate()])
    device.serialno = "synthetic_device_002"  # Same IP, SDK, ABIs and installed APK.
    with pytest.raises(ShieldError) as caught:
        ops.apks.apply(plan["preview_id"])
    assert caught.value.kind == "device_mismatch"
    assert not any(call[0] == "push" or call[:2] == ("pm", "install") for call in device.calls)


def test_apk_without_stable_identity_is_refused_before_staging(apk_env):
    ops, device, candidate = apk_env
    device.serialno = "unknown"
    with pytest.raises(ShieldError) as caught:
        ops.apks.preview([candidate()])
    assert caught.value.kind == "device_identity_unknown"
    assert not device.downloads
    assert not ops.apks.plans


def test_device_change_after_upload_cannot_install_or_cleanup_on_new_device(apk_env):
    ops, device, candidate = apk_env
    plan = ops.apks.preview([candidate()])
    original = device.adb

    def adb(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[0] == "push":
            device.serialno = "synthetic_device_002"
        return result

    device.adb = adb
    with pytest.raises(ShieldError) as caught:
        ops.apks.apply(plan["preview_id"])
    assert caught.value.kind == "device_mismatch"
    assert not any(call[:2] in (("pm", "install"), ("rm", "-f")) for call in device.calls)


@pytest.mark.parametrize("phase", ["install-create", "install-write", "install-commit"])
def test_device_change_during_split_session_blocks_later_actions(apk_env, phase):
    ops, device, candidate = apk_env
    plan = ops.apks.preview([candidate(), candidate(split="config.arm64", abi="arm64-v8a")])
    original = device.shell
    changed = False

    def shell(*args, **kwargs):
        nonlocal changed
        if changed and args[0] in ("pm", "rm"):
            pytest.fail("Mutation attempted on the replacement TV")
        result = original(*args, **kwargs)
        if args[:2] == ("pm", phase):
            device.serialno = "synthetic_device_002"
            changed = True
        return result

    device.shell = shell
    with pytest.raises(ShieldError) as caught:
        ops.apks.apply(plan["preview_id"])
    # Before the commit nothing changed: a refusal. After it the app may have changed on
    # whichever device took the commit, so a different serial is not a refusal.
    assert caught.value.kind == (
        "outcome_unknown" if phase == "install-commit" else "device_mismatch"
    )
    assert changed


def test_failed_recovery_metadata_write_still_cleans_up_and_reports_bundle(apk_env, monkeypatch):
    ops, device, candidate = apk_env
    plan = ops.apks.preview([candidate()])
    original = apks.save_json

    def save(path, value):
        if value["status"] == "verified":
            raise OSError("private credential path must not appear")
        return original(path, value)

    monkeypatch.setattr(apks, "save_json", save)
    with pytest.raises(ShieldError) as caught:
        ops.apks.apply(plan["preview_id"])
    assert caught.value.kind == "local_storage_error"
    assert "private credential" not in str(caught.value)
    assert "Recovery bundle" in str(caught.value)
    assert any(call[:2] == ("rm", "-f") for call in device.calls)
    assert plan["preview_id"] not in ops.apks.plans


def test_metadata_commit_failure_preserves_previous_recovery_state(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    apks.save_json(path, {"status": "prepared"})

    def failed_replace(*args):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(apks.os, "replace", failed_replace)
    with pytest.raises(OSError):
        apks.save_json(path, {"status": "installing"})
    assert json.loads(path.read_text()) == {"status": "prepared"}
    assert list(tmp_path.iterdir()) == [path]


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
    "who,state",
    [("org.xbmc.kodi", 2), ("org.xbmc.kodi", 3), ("com.spotify.tv.android", 3), ("kodi", None)],
)
def test_preview_does_not_pull_installed_apks_while_anything_plays(apk_env, who, state):
    # Saving the originals pulls up to 1 GB over the Shield's network link; during a stream
    # (or with a film paused, about to resume) that competes with playback.
    ops, device, candidate = apk_env
    if state is None:
        device.players = [{"playerid": 1, "type": "video"}]
    else:
        device.media = media_session(who, state)
    with pytest.raises(ShieldError, match="playing or paused") as error:
        ops.apks.preview([candidate()])
    assert error.value.kind == "playing"
    assert not device.downloads
    assert not ops.apks.plans
    assert not list((ops.c.state / "apk_previews").glob("*"))
    device.media, device.players = media_session("org.xbmc.kodi", 1), []  # Lingering, stopped.
    assert ops.apks.preview([candidate()])["original_apks_saved"] == 1
    assert device.downloads


def test_preview_rechecks_before_each_pull(apk_env):
    ops, device, candidate = apk_env
    device.installed = {
        "/data/app/example/base.apk": apk_bytes(),
        "/data/app/example/split_config.apk": apk_bytes(split="config.xx"),
    }
    download = device.download

    def first_then_playback(remote, destination, **kwargs):
        download(remote, destination, **kwargs)
        device.media = media_session("org.xbmc.kodi", 3)

    device.download = first_then_playback
    with pytest.raises(ShieldError, match="playing or paused"):
        ops.apks.preview([candidate(), candidate(split="config.xx")])
    assert device.downloads == ["/data/app/example/base.apk"]


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
    # A model-supplied fingerprint is not trust on its own (M1).
    with pytest.raises(ShieldError, match="independently trusted"):
        ops.apks.preview([source], [SIGNER])
    ops.apks.c = replace(ops.apks.c, trusted_signers=frozenset({SIGNER, "c" * 64}))
    with pytest.raises(ShieldError, match="only narrow"):
        ops.apks.preview([source], ["b" * 64])
    with pytest.raises(ShieldError, match="signers differ"):
        ops.apks.preview([source], ["c" * 64])
    preview = ops.apks.preview([source], [SIGNER.upper()])
    assert ops.apks.apply(preview["preview_id"])["status"] == "verified"
    device.installed = {}
    assert ops.apks.preview([candidate()])["package"] == "dev.example.player"


def test_trusted_signers_come_from_env_or_file(monkeypatch, tmp_path):
    from nvidia_mcp.config import Config

    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    colon = ":".join(["AB"] * 32)
    monkeypatch.setenv("NVIDIA_MCP_TRUSTED_SIGNERS", f"{SIGNER}, {colon}")
    listing = tmp_path / "signers.txt"
    listing.write_text("# SmartTube\n" + "d" * 64 + "  # stable\n\n")
    monkeypatch.setenv("NVIDIA_MCP_TRUSTED_SIGNERS_FILE", str(listing))
    assert Config.from_env().trusted_signers == {SIGNER, "ab" * 32, "d" * 64}
    monkeypatch.setenv("NVIDIA_MCP_TRUSTED_SIGNERS", "not-a-fingerprint")
    with pytest.raises(ShieldError, match="fingerprints"):
        Config.from_env()


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
        b"not a tar archive" + trailer(command)
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
    assert ops.apks.backups()["backups"][0]["status"] == "failed_before_install"


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


def test_mounted_kodi_snapshot_skips_regenerable_caches(apk_env, tmp_path):
    ops, device, candidate = apk_env
    mount = tmp_path / "mount"
    (mount / "addons/packages").mkdir(parents=True)
    (mount / "addons/packages/big.zip").write_bytes(b"x" * 100)
    (mount / "userdata/Thumbnails/0").mkdir(parents=True)
    (mount / "userdata/Thumbnails/0/a.jpg").write_bytes(b"x" * 100)
    (mount / "userdata/guisettings.xml").write_text("<settings/>")
    ops.apks.c = replace(ops.apks.c, mount=mount)
    backup = tmp_path / "backup"
    backup.mkdir()
    result = ops.apks.kodi_snapshot(backup)
    assert result["excluded"] == list(SNAPSHOT_EXCLUDES)
    with tarfile.open(backup / "kodi-data.tar") as archive:
        names = archive.getnames()
    assert "userdata/guisettings.xml" in names
    assert not any("Thumbnails" in n or "packages" in n for n in names)


def test_adb_kodi_snapshot_excludes_caches(apk_env, tmp_path):
    ops, device, candidate = apk_env
    commands = []
    original = device.stream_to_file

    def capture(command, destination, limit, timeout):
        commands.append(command)
        return original(command, destination, limit, timeout)

    device.stream_to_file = capture
    original_shell = device.shell
    device.shell = lambda *a, **k: (
        "/storage/emulated/0/Android/data/org.xbmc.kodi/files/.kodi"
        if a[:2] == ("readlink", "-f")
        else original_shell(*a, **k)
    )
    backup = tmp_path / "adb-backup"
    backup.mkdir()
    ops.apks.kodi_snapshot(backup)
    remote = commands[0][-1]
    for path in SNAPSHOT_EXCLUDES:
        assert "--exclude=" + path in remote
    assert "addons userdata 2>/dev/null;" in remote


def test_failed_remote_tar_exit_blocks_installation(apk_env):
    ops, device, candidate = apk_env
    device.installed["/data/app/example/base.apk"] = apk_bytes(package="org.xbmc.kodi")
    preview = ops.apks.preview([candidate(package="org.xbmc.kodi")])
    device.tar_exit = 1
    with pytest.raises(ShieldError, match="exit 1"):
        ops.apks.apply(preview["preview_id"])
    assert not any(call[0] == "push" for call in device.calls)


def test_attempt_failing_before_transfer_removes_its_bundle(apk_env):
    ops, device, candidate = apk_env
    device.installed["/data/app/example/base.apk"] = apk_bytes(package="org.xbmc.kodi")
    preview = ops.apks.preview([candidate(package="org.xbmc.kodi")])
    device.fail_snapshot = True
    for _ in range(3):  # Retries must not pile up GB-sized bundles.
        with pytest.raises(ShieldError, match="No APK was transferred") as caught:
            ops.apks.apply(preview["preview_id"])
        assert caught.value.kind != "outcome_unknown"
    assert not any(call[0] == "push" for call in device.calls)
    root = ops.c.state / "apk_backups"
    assert not root.exists() or not any(root.iterdir())
    assert preview["preview_id"] in ops.apks.plans  # Still retryable after a local failure.


@pytest.mark.parametrize("kind", ["timeout", "response_timeout"])
def test_install_timeout_after_transfer_is_outcome_unknown(apk_env, kind):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    original = device.shell

    def shell(*args, **kwargs):
        if args[:2] == ("pm", "install"):
            raise ShieldError("ADB timed out; check the TV connection", kind)
        return original(*args, **kwargs)

    device.shell = shell
    with pytest.raises(ShieldError, match="may still complete") as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind == "outcome_unknown"
    backup = ops.apks.backups()["backups"][0]
    assert backup["status"] == "failed_after_transfer"


def test_push_timeout_keeps_timeout_kind(apk_env):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])

    def adb(*args, **kwargs):
        raise ShieldError("ADB timed out; check the TV connection", "timeout")

    device.adb = adb
    with pytest.raises(ShieldError, match="Recovery bundle") as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind == "timeout"


@pytest.mark.parametrize(
    "kind", ["unreachable", "offline", "device_error", "invalid_response", "storage_error"]
)
def test_any_connection_failure_once_installing_is_outcome_unknown(apk_env, kind):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    original = device.shell

    def shell(*args, **kwargs):
        if args[:2] == ("pm", "install"):
            raise ShieldError("ADB connection lost", kind)
        return original(*args, **kwargs)

    device.shell = shell
    with pytest.raises(ShieldError, match="may have completed") as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind == "outcome_unknown"


def test_android_rejecting_the_install_keeps_its_outcome(apk_env):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    device.install_result = "Failure [INSTALL_FAILED_VERSION_DOWNGRADE]"
    with pytest.raises(ShieldError, match="Android rejected the install") as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind != "outcome_unknown"


def test_apk_push_timeout_scales_with_size(apk_env, monkeypatch):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    monkeypatch.setattr(apks, "push_timeout", lambda source: 600)
    timeouts = []
    adb = device.adb

    def recording(*args, **kwargs):
        if args[0] == "push":
            timeouts.append(kwargs.get("timeout"))
        return adb(*args, **kwargs)

    device.adb = recording
    ops.apks.apply(preview["preview_id"])
    assert timeouts == [600]


def bundle_status(ops):
    return ops.apks.backups()["backups"][0]["status"]


def test_lost_serial_read_after_android_installed_is_outcome_unknown(apk_env):
    # pm answered Success, then one getprop ro.serialno lost its reply: the app has changed,
    # so this must not be recorded as a refusal (device_mismatch).
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    original, installed = device.shell, []

    def shell(*args, **kwargs):
        if installed == [1] and args == ("getprop", "ro.serialno"):
            installed.append(2)
            raise ShieldError("ADB timed out", "timeout")
        result = original(*args, **kwargs)
        if args[:2] == ("pm", "install"):
            installed.append(1)
        return result

    device.shell = shell
    with pytest.raises(ShieldError, match="could not be read") as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind == "outcome_unknown"
    assert json.loads(next(iter(device.installed.values())))["version"] == 2
    assert bundle_status(ops) == "failed_after_transfer"


def test_lost_serial_read_before_any_install_command_is_a_refusal(apk_env):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    original, pushed = device.shell, []

    def shell(*args, **kwargs):
        if pushed and args == ("getprop", "ro.serialno"):
            raise ShieldError("ADB timed out", "timeout")
        if args[0] == "sha256sum" and "/data/local/tmp/" in args[1]:
            pushed.append(1)
        return original(*args, **kwargs)

    device.shell = shell
    with pytest.raises(ShieldError, match="could not be read") as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind == "device_mismatch"
    assert not any(call[:2] == ("pm", "install") for call in device.calls)
    device.shell = original
    assert bundle_status(ops) == "failed_before_install"


def test_local_storage_failure_before_pm_is_not_outcome_unknown(apk_env, monkeypatch):
    # The "installing" status could not be saved (a full disk): no pm command was sent.
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])
    original = apks.save_json

    def save(path, value):
        if value["status"] == "installing":
            raise OSError(28, "No space left on device")
        return original(path, value)

    monkeypatch.setattr(apks, "save_json", save)
    with pytest.raises(ShieldError) as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind != "outcome_unknown"
    assert not any(call[0] == "pm" and call[1].startswith("install") for call in device.calls)
    assert bundle_status(ops) == "failed_before_install"


def test_playback_starting_during_split_staging_blocks_the_commit(apk_env):
    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate(), candidate(split="config.arm64", abi="arm64-v8a")])
    original = device.shell

    def shell(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[:2] == ("pm", "install-write"):
            device.foreground = "com.google.android.youtube.tv"
        return result

    device.shell = shell
    with pytest.raises(ShieldError) as caught:
        ops.apks.apply(preview["preview_id"])
    assert caught.value.kind == "other_app_foreground"
    assert not any(call[:2] == ("pm", "install-commit") for call in device.calls)
    assert any(call[:2] == ("pm", "install-abandon") for call in device.calls)
    assert json.loads(next(iter(device.installed.values())))["version"] == 1
    assert bundle_status(ops) == "failed_before_install"


def test_bundle_from_an_attempt_that_never_sent_an_install_is_pruned(apk_env):
    from nvidia_mcp.retention import prune_state

    ops, device, candidate = apk_env
    preview = ops.apks.preview([candidate()])

    def push(*args, **kwargs):
        device.calls.append(args)
        raise ShieldError("ADB device is offline", "offline")

    device.adb = push
    with pytest.raises(ShieldError):
        ops.apks.apply(preview["preview_id"])
    assert bundle_status(ops) == "failed_before_install"
    later = time.time() + 400 * 86400
    removed = prune_state(replace(ops.c, keep_apk_backups=0), now=later)
    assert removed["apk_backups"] == 1
    assert not list((ops.c.state / "apk_backups").iterdir())
