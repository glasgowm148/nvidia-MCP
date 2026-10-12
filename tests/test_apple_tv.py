import asyncio
import base64
import json
import threading
from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import FakeTransport

from nvidia_mcp.apple_bridge import AppleBridge, private_pairing_logs
from nvidia_mcp.apple_tv import AppleOperations, AppleTransport, make_operations
from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.files import digest
from nvidia_mcp.operations import Operations
from nvidia_mcp.server import create_server


@pytest.fixture
def apple(tmp_path):
    config = Config(
        host="127.0.0.1",
        platform="apple_tv",
        state=tmp_path / "state",
        manager_token="synthetic-manager",
        allow_writes=True,
        allow_plugin_browse=True,
        apple_kodi_app_id="com.example.kodi",
    )

    class Transport(FakeTransport):
        def __init__(self):
            super().__init__(config)
            self.state = {
                "platform": "tvos",
                "active": True,
                "device_id": "a" * 32,
                "profile": "Adults",
                "profile_root": "userdata",
            }
            self.media = {"playback": "idle", "power": "on", "identifier": "synthetic-apple"}
            self.apple = SimpleNamespace(
                snapshot=lambda: dict(self.media),
                launch=lambda app: self.calls.append(("launch", app)),
                can_launch=lambda app: None,
                button=lambda key: self.calls.append(("button", key)),
            )
            self.data = {"userdata/guisettings.xml": b"<settings/>"}

        def manager(self, path, method="GET", body=None):
            self.calls.append(("manager", path, method, body))
            if path == "/api/portable/state":
                return dict(self.state)
            if path.startswith("/api/portable/file?"):
                name = parse_qs(urlsplit(path).query)["path"][0]
                data = self.data[name]
                return {
                    "path": name,
                    "base64": base64.b64encode(data).decode(),
                    "bytes": len(data),
                    "sha256": digest(data),
                    "device_id": self.state["device_id"],
                    "profile_root": self.state["profile_root"],
                }
            if path == "/api/kodi/logs":
                return {"lines": ["safe log"]}
            return {"backup_id": "synthetic-backup", "can_apply": True}

        def shell(self, *args, **kwargs):
            pytest.fail("Apple TV operation attempted Android shell access")

        def close(self):
            pass

    transport = Transport()
    return AppleOperations(transport), transport


def test_default_factory_keeps_android_backend(tmp_path):
    ops = make_operations(Config(host="127.0.0.1", state=tmp_path))
    assert type(ops) is Operations
    ops.t.close()


def test_explicit_apple_config_and_forwarding_refusal(monkeypatch):
    monkeypatch.setenv("NVIDIA_MCP_PLATFORM", "apple_tv")
    monkeypatch.setenv("APPLE_TV_HOST", "192.168.1.8")
    monkeypatch.delenv("SHIELD_HOST", raising=False)
    monkeypatch.delenv("ANDROID_TV_HOST", raising=False)
    assert Config.from_env().platform == "apple_tv"
    monkeypatch.setenv("KODI_HTTP_ROUTE", "auto")
    with pytest.raises(ShieldError, match="forwarding"):
        Config.from_env()


@pytest.mark.parametrize("platform", ["android", "apple_tv"])
@pytest.mark.parametrize("writes", [False, True])
def test_tool_capabilities_match_platform_and_write_mode(tmp_path, platform, writes):
    server, ops = create_server(
        Config(host="127.0.0.1", platform=platform, state=tmp_path, allow_writes=writes)
    )
    try:
        tools = {tool.name for tool in asyncio.run(server.list_tools())}
        assert "kodi_layout_preview" in tools and "kodi_read_file" in tools
        assert ("kodi_layout_apply" in tools) is writes
        assert ("kodi_configuration_restore" in tools) is writes
        assert ("apple_tv_power" in tools) is (platform == "apple_tv" and writes)
        for name in ["shield_screenshot", "shield_logcat", "shield_connect", "shield_apk_preview"]:
            assert (name in tools) is (platform == "android")
        assert ("kodi_patch_apply" in tools) is (platform == "android" and writes)
    finally:
        ops.t.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("playback", "paused"),
        ("playback", "playing"),
        ("playback", "loading"),
        ("playback", "unknown"),
        ("power", "off"),
        ("power", "unknown"),
    ],
)
def test_other_media_or_unknown_state_blocks_skin_write(apple, field, value):
    ops, transport = apple
    transport.media[field] = value
    with pytest.raises(ShieldError):
        ops.configuration_backup()
    assert not any(call[0] == "manager" and call[2] == "POST" for call in transport.calls)


@pytest.mark.parametrize("active", [False, None, "true"])
def test_only_explicit_active_kodi_allows_write(apple, active):
    ops, transport = apple
    transport.state["active"] = active
    with pytest.raises(ShieldError, match="confirmed active"):
        ops.widget_cache_refresh()


def test_skin_preview_apply_and_backup_routes_without_adb(apple):
    ops, transport = apple
    plan = {"section_id": "hub:moviehub", "expected_revision": "rev", "rows": []}
    preview = ops.layout_preview(plan)
    assert ops.layout_apply(preview["preview_id"])["backup_id"] == "synthetic-backup"
    ops.configuration_backup("skin.bingie")
    ops.configuration_restore("checkpoint-1", "skin.bingie")
    ops.configuration_restore("checkpoint-1")
    ops.manager_read("backups")
    ops.manager_read("backups", "skin.bingie")
    requests = [
        (call[1], call[3]) for call in transport.calls if call[0] == "manager" and call[2] == "POST"
    ]
    assert ("/api/addons/skin.bingie/backup", {}) in requests
    assert ("/api/addons/skin.bingie/restore", {"backup_id": "checkpoint-1"}) in requests
    assert ("/api/stack/restore", {"backup_id": "checkpoint-1"}) in requests
    assert any(call[:2] == ("manager", "/api/stack/backups") for call in transport.calls)
    assert any(
        call[:2] == ("manager", "/api/addons/skin.bingie/backups") for call in transport.calls
    )


@pytest.mark.parametrize("changed", ["device", "profile", "profile_root"])
def test_skin_preview_bound_to_device_and_profile(apple, changed):
    ops, transport = apple
    preview = ops.layout_preview(
        {"section_id": "hub:moviehub", "expected_revision": "rev", "rows": []}
    )
    if changed == "device":
        transport.state["device_id"] = "b" * 32
    elif changed == "profile_root":
        transport.state["profile_root"] = "userdata/profiles/Kids"
    else:
        transport.profile = "Kids"
    with pytest.raises(ShieldError):
        ops.layout_apply(preview["preview_id"])
    assert not any(call[:2] == ("manager", "/api/widgets/layout/apply") for call in transport.calls)


def test_bounded_private_file_read_and_local_backup(apple):
    ops, transport = apple
    result = ops.read_file("userdata/guisettings.xml")
    assert result["content"] == "<settings />"
    identifier = ops.backup_file("userdata/guisettings.xml")["backup_id"]
    assert ops.files.restore_data(identifier)[1] == b"<settings/>"
    transport.state["device_id"] = "b" * 32
    with pytest.raises(ShieldError, match="instance changed"):
        ops.files.restore_data(identifier)


def test_corrupt_file_checksum_is_not_returned(apple):
    ops, transport = apple
    original = transport.manager

    def manager(path, *args):
        value = original(path, *args)
        if path.startswith("/api/portable/file?"):
            value["sha256"] = "0" * 64
        return value

    transport.manager = manager
    with pytest.raises(ShieldError, match="checksum"):
        ops.read_file("userdata/guisettings.xml")


def test_restart_checks_launch_capability_before_quitting(apple):
    ops, transport = apple

    def cannot_launch(app):
        raise ShieldError("bundle unavailable", "not_found")

    transport.apple.can_launch = cannot_launch
    with pytest.raises(ShieldError):
        ops.lifecycle("restart")
    assert not any(call[0] == "Application.Quit" for call in transport.calls)


def test_offline_start_requires_separate_interrupt_permission(apple):
    ops, transport = apple
    transport.state["active"] = False
    with pytest.raises(ShieldError):
        ops.lifecycle("start")
    with pytest.raises(ShieldError, match="ALLOW_INTERRUPT"):
        ops.lifecycle("start", interrupt_other_app=True)
    ops.c = replace(ops.c, allow_interrupt=True)
    assert ops.lifecycle("start", interrupt_other_app=True)["state"] == "launch_requested"


def test_transport_never_invokes_adb_for_apple(tmp_path):
    transport = AppleTransport(Config(host="127.0.0.1", platform="apple_tv", state=tmp_path))
    try:
        for method in [transport.adb, transport.shell, transport.exec_out]:
            with pytest.raises(ShieldError, match="unavailable"):
                method("any")
    finally:
        transport.close()


@pytest.fixture
def paired_bridge(tmp_path, monkeypatch):
    path = tmp_path / "private/apple.json"
    config = Config(host="192.168.1.8", platform="apple_tv", apple_credentials=path)
    bridge = AppleBridge(config)
    calls = []
    target = SimpleNamespace(
        identifier="synthetic-tv",
        all_identifiers={"synthetic-tv"},
        set_credentials=lambda *args: True,
    )

    async def scan(loop, **kwargs):
        calls.append(("scan", kwargs))
        return [target]

    mrp = SimpleNamespace(psm=SimpleNamespace(playing=SimpleNamespace(_playback_state=3)))
    device = SimpleNamespace(
        metadata=SimpleNamespace(main_protocol="MRP", get=lambda protocol: mrp),
        power=SimpleNamespace(power_state=SimpleNamespace(name="On")),
        device_info=SimpleNamespace(model_str="Apple TV", version="test"),
        close=lambda: set(),
    )

    async def connect(*args):
        calls.append(("connect",))
        return device

    class Handler:
        device_provides_pin = has_paired = True
        service = SimpleNamespace(credentials="synthetic-private-pair-secret")

        async def begin(self):
            calls.append(("begin",))

        def pin(self, value):
            calls.append(("pin", value))

        async def finish(self):
            pass

        async def close(self):
            calls.append(("closed",))

    async def pair(*args):
        return Handler()

    sdk = SimpleNamespace(scan=scan, connect=connect, pair=pair)
    protocols = SimpleNamespace(Companion="Companion", AirPlay="AirPlay", MRP="MRP")
    monkeypatch.setattr(bridge, "sdk", lambda: (sdk, None, None, protocols))
    yield bridge, target, calls
    bridge.close()


def test_private_pairing_merges_protocols_and_uses_only_explicit_host(paired_bridge):
    bridge, target, calls = paired_bridge
    first = bridge.pair("Companion", lambda: "7751")
    assert "synthetic-private" not in json.dumps(first)
    bridge.pair("AirPlay", lambda: "7751")
    assert set(bridge.credentials()["services"]) == {"Companion", "AirPlay"}
    assert all(call[1]["hosts"] == ["192.168.1.8"] for call in calls if call[0] == "scan")
    assert bridge.snapshot()["playback"] == "stopped"
    target.all_identifiers = {"replacement-tv"}
    bridge.device = None
    with pytest.raises(ShieldError, match="different Apple TV"):
        bridge.snapshot()


def test_partial_pairing_cannot_masquerade_as_idle(paired_bridge):
    bridge, _target, _calls = paired_bridge
    bridge.pair("Companion", lambda: "7751")
    with pytest.raises(ShieldError, match="Pair both"):
        bridge.snapshot()


def test_paired_controls_require_ipv4_before_discovery(paired_bridge):
    bridge, _target, calls = paired_bridge
    bridge.c = replace(bridge.c, host="::1")
    with pytest.raises(ShieldError, match="private IPv4"):
        bridge.pair("Companion", lambda: "7751")
    assert calls == []


def test_idle_snapshot_reconnects_instead_of_reusing_a_cache(paired_bridge):
    bridge, _target, calls = paired_bridge
    bridge.pair("Companion", lambda: "7751")
    bridge.pair("AirPlay", lambda: "7751")
    assert bridge.snapshot()["playback"] == "stopped"
    assert bridge.snapshot()["playback"] == "stopped"
    assert sum(call[0] == "connect" for call in calls) == 2


def test_pairing_cancel_never_saves_credentials(paired_bridge):
    bridge, _target, calls = paired_bridge

    def cancelled():
        raise EOFError("synthetic private information")

    with pytest.raises(ShieldError, match="pairing cancelled"):
        bridge.pair("Companion", cancelled)
    assert not bridge.c.apple_credentials.exists()
    assert ("closed",) in calls


def test_pairing_failure_does_not_echo_sdk_secrets(paired_bridge, monkeypatch):
    bridge, _target, _calls = paired_bridge
    sdk, names, states, protocols = bridge.sdk()

    async def broken(*args):
        raise ValueError("synthetic-secret-pairing-credential")

    sdk.pair = broken
    with pytest.raises(ShieldError) as error:
        bridge.pair("Companion", lambda: "7751")
    assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize("fail", [False, True])
def test_private_pairing_suppresses_sdk_pin_and_key_logs(paired_bridge, caplog, monkeypatch, fail):
    import logging

    bridge, _target, calls = paired_bridge
    sdk, _names, _states, _protocols = bridge.sdk()
    original_pair = sdk.pair
    logger = logging.getLogger("pyatv.protocols.companion.pairing")
    package = logging.getLogger("pyatv")
    monkeypatch.setattr(logger, "level", logging.DEBUG)
    monkeypatch.setattr(package, "level", logging.WARNING)
    caplog.set_level(logging.DEBUG)

    async def noisy_pair(*args):
        handler = await original_pair(*args)
        original_pin = handler.pin

        def pin(value):
            logger.debug("Companion PIN changed to %04d", value)
            original_pin(value)

        async def finish():
            # A logger first created inside pairing inherits the silent package.
            logging.getLogger("pyatv.synthetic_new_pairing_logger").error("synthetic-new-key")
            logger.error("synthetic-private-pair-secret")
            logging.getLogger("synthetic_application").warning("application log retained")
            if fail:
                raise ValueError("synthetic-private-pair-secret")

        handler.pin, handler.finish = pin, finish
        return handler

    sdk.pair = noisy_pair
    if fail:
        with pytest.raises(ShieldError):
            bridge.pair("Companion", lambda: "0751")
        assert not bridge.c.apple_credentials.exists()
    else:
        assert bridge.pair("Companion", lambda: "0751")["paired"] == "Companion"
        assert bridge.credentials()["services"]["Companion"] == "synthetic-private-pair-secret"
    assert ("pin", 751) in calls and ("closed",) in calls
    assert (
        "0751" not in caplog.text
        and "synthetic-private" not in caplog.text
        and "synthetic-new-key" not in caplog.text
    )
    assert "application log retained" in caplog.text
    assert logger.level == logging.DEBUG and package.level == logging.WARNING


@pytest.mark.parametrize("protocol", ["companion", "airplay"])
def test_installed_sdk_pin_logs_are_private_and_keep_leading_zero(protocol, caplog):
    import importlib
    import logging

    pytest.importorskip("pyatv")
    module = importlib.import_module("pyatv.protocols." + protocol + ".pairing")
    handler_type = getattr(
        module, {"companion": "Companion", "airplay": "AirPlay"}[protocol] + "PairingHandler"
    )
    handler = handler_type.__new__(handler_type)  # No network/core required by pin().
    logger = logging.getLogger(module.__name__)
    caplog.set_level(logging.DEBUG, logger=logger.name)
    handler.pin(751)
    assert "0751" in caplog.text  # Demonstrate the installed SDK's actual trace.
    caplog.clear()
    with private_pairing_logs():
        handler.pin(751)
    assert handler.pin_code == "0751" and "0751" not in caplog.text
    assert logger.level == logging.DEBUG


def test_apple_library_uses_same_backend_without_android_access(apple):
    from nvidia_mcp import AppleTV

    ops, transport = apple
    with AppleTV(ops.c, transport=transport) as tv:
        assert isinstance(tv.operations, AppleOperations)
        assert tv.kodi_alive() is True
        assert tv.viewing_state()["state"] == "idle"
        assert tv.start_kodi()["state"] == "already_active"
    with pytest.raises(ShieldError):
        AppleTV(replace(ops.c, platform="android"))


def test_profile_change_during_file_read_blocks_return(apple):
    ops, transport = apple
    original = transport.manager

    def changing(path, *args):
        value = original(path, *args)
        if path.startswith("/api/portable/file?"):
            transport.state["profile_root"] = "userdata/profiles/Kids"
        return value

    transport.manager = changing
    with pytest.raises(ShieldError, match="changed during file read"):
        ops.read_file("userdata/guisettings.xml")


def test_restart_cannot_request_offline_recovery(apple):
    ops, transport = apple
    with pytest.raises(ShieldError, match="offline force-stop"):
        ops.lifecycle("restart", allow_offline=True)
    assert transport.calls == []


def test_installed_sdk_contract_without_network():
    pytest.importorskip("pyatv")
    import inspect

    sdk, features, states, protocols = AppleBridge.sdk()
    assert "hosts" in inspect.signature(sdk.scan).parameters
    assert callable(sdk.connect) and callable(sdk.pair)
    for name in ("LaunchApp", "AppList", "Home", "TurnOn", "TurnOff"):
        assert getattr(features, name) is not None
    assert (
        states.Available is not None
        and protocols.Companion is not None
        and protocols.AirPlay is not None
    )


@pytest.mark.parametrize(
    "kind", ["authentication_denied", "device_mismatch", "invalid_response", "unsupported"]
)
def test_start_opt_in_never_bypasses_manager_failure(apple, kind):
    ops, transport = apple
    ops.c = replace(ops.c, allow_interrupt=True)

    def failure():
        raise ShieldError("synthetic Manager failure", kind)

    ops.state = failure
    with pytest.raises(ShieldError) as error:
        ops.lifecycle("start", interrupt_other_app=True)
    assert error.value.kind == kind
    assert not any(call[0] == "launch" for call in transport.calls)


@pytest.mark.parametrize("kind", ["unreachable", "timeout"])
def test_start_offline_still_requires_both_opt_ins(apple, kind):
    ops, transport = apple
    ops.c = replace(ops.c, allow_interrupt=True)

    def offline():
        raise ShieldError("Kodi not answering", kind)

    ops.state = offline
    assert ops.lifecycle("start", interrupt_other_app=True)["state"] == "launch_requested"


@pytest.mark.parametrize("owner", ["device_id", "profile_root"])
def test_file_response_owner_must_match_request_even_if_state_returns_to_original(apple, owner):
    ops, transport = apple
    original = transport.manager

    def mismatched(path, *args):
        value = original(path, *args)
        if path.startswith("/api/portable/file?"):
            value[owner] = "b" * 32 if owner == "device_id" else "userdata/profiles/Kids"
        return value

    transport.manager = mismatched
    with pytest.raises(ShieldError, match="validation"):
        ops.read_file("userdata/guisettings.xml")


def test_real_sdk_missing_or_paused_without_metadata_never_means_idle(tmp_path):
    pytest.importorskip("pyatv")
    from pyatv.const import DeviceState, Protocol
    from pyatv.core.facade import FacadeMetadata
    from pyatv.protocols.mrp import MrpMetadata
    from pyatv.protocols.mrp import protobuf as pb
    from pyatv.protocols.mrp.player_state import PlayerStateManager

    protocol = SimpleNamespace(listen_to=lambda *args: None)
    psm = PlayerStateManager(protocol)
    metadata = MrpMetadata(protocol, psm, "synthetic-tv", None)
    facade = FacadeMetadata()
    facade.register(metadata, Protocol.MRP)
    bridge = AppleBridge(Config(host="127.0.0.1", platform="apple_tv", state=tmp_path))
    assert asyncio.run(facade.playing()).device_state == DeviceState.Idle
    assert bridge.confirmed_playback(facade) == "unknown"
    path = pb.PlayerPath()
    path.client.bundleIdentifier = "com.example.player"
    path.player.identifier = "synthetic-player"
    player = psm.get_player(path)
    psm._active_client = player.parent
    player.parent.active_player = player
    message = pb.SetStateMessage()
    message.playbackState = pb.PlaybackState.Paused
    player.handle_set_state(message)
    assert asyncio.run(facade.playing()).device_state == DeviceState.Idle
    assert bridge.confirmed_playback(facade) == "paused"
    message.playbackState = pb.PlaybackState.Stopped
    player.handle_set_state(message)
    assert bridge.confirmed_playback(facade) == "stopped"
    assert bridge.confirmed_playback(SimpleNamespace()) == "unknown"
    bridge.close()


def test_closing_bridge_cancels_pending_work_and_rejects_new_work(tmp_path):
    bridge = AppleBridge(Config(host="127.0.0.1", platform="apple_tv", state=tmp_path))
    entered, cancelled = threading.Event(), threading.Event()
    failures = []

    async def pending():
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    def worker():
        try:
            bridge._run(pending)
        except ShieldError as exc:
            failures.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    assert entered.wait(3)
    loop = bridge.loop
    bridge.close()
    thread.join(3)
    assert not thread.is_alive() and cancelled.is_set() and loop.is_closed()
    assert len(failures) == 1
    with pytest.raises(ShieldError, match="closed"):
        bridge._run(pending)
    bridge.close()


def test_cached_connection_still_refuses_removed_pairing_protocol(paired_bridge):
    bridge, _target, _calls = paired_bridge
    bridge.pair("Companion", lambda: "7751")
    bridge.pair("AirPlay", lambda: "7751")
    bridge.snapshot()
    value = bridge.credentials()
    del value["services"]["AirPlay"]
    bridge.save_credentials(value)
    with pytest.raises(ShieldError, match="Pair both"):
        bridge._run(bridge.connected)


def test_old_manager_file_contract_explains_upgrade(apple):
    ops, transport = apple
    original = transport.manager

    def old(path, *args):
        value = original(path, *args)
        if path.startswith("/api/portable/file?"):
            value.pop("device_id")
            value.pop("profile_root")
        return value

    transport.manager = old
    with pytest.raises(ShieldError, match="0.7.17"):
        ops.read_file("userdata/guisettings.xml")


def test_pairing_private_input_uses_caller_thread(paired_bridge):
    bridge, _target, _calls = paired_bridge
    caller = threading.get_ident()

    def pin():
        assert threading.get_ident() == caller
        return "7751"

    assert bridge.pair("Companion", pin)["paired"] == "Companion"


def test_private_pin_keyboard_interrupt_closes_pairing_without_saving(paired_bridge):
    bridge, _target, calls = paired_bridge

    def interrupted():
        raise KeyboardInterrupt()

    with pytest.raises(ShieldError, match="pairing cancelled"):
        bridge.pair("Companion", interrupted)
    assert not bridge.c.apple_credentials.exists()
    assert ("closed",) in calls


def test_private_input_errors_never_echo_input(paired_bridge):
    bridge, _target, calls = paired_bridge

    def broken():
        raise OSError("synthetic-secret-private-input")

    with pytest.raises(ShieldError) as error:
        bridge.pair("Companion", broken)
    assert "synthetic-secret" not in str(error.value)
    assert not bridge.c.apple_credentials.exists()
    assert ("closed",) in calls
