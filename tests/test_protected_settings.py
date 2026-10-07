"""H3: kodi_set_setting must not weaken Kodi security or expose services."""

from dataclasses import replace

import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.operations import protected_setting


@pytest.mark.parametrize(
    "setting",
    [
        "services.webserver",
        "services.webserverauthentication",
        "services.webserverport",
        "services.esenabled",
        "services.zeroconf",
        "services.upnp",
        "services.airplay",
        "addons.unknownsources",
        "addons.updatemode",
        "masterlock.startuplock",
        "system.playlistspath",
        "debug.extralogging",
        "lookandfeel.skin",
        "network.usehttpproxy",
        "network.httpproxyserver",
    ],
)
def test_protected_settings_are_refused(ops, setting):
    ops.t.settings[setting] = True
    with pytest.raises(ShieldError, match="protected") as exc:
        ops.set_core_setting(setting, False)
    assert exc.value.kind == "protected_setting"
    assert not any(c[0] == "Settings.SetSettingValue" for c in ops.t.calls)


@pytest.mark.parametrize(
    "setting", ["debug.showloginfo", "videoplayer.adjustrefreshrate", "audiooutput.passthrough"]
)
def test_ordinary_settings_are_allowed(ops, setting):
    ops.t.settings[setting] = False
    assert ops.set_core_setting(setting, True)["current"] is True


def test_exact_env_allow_list(monkeypatch, ops):
    monkeypatch.setenv("SHIELD_HOST", "192.168.1.50")
    monkeypatch.setenv("NVIDIA_MCP_ALLOW_SETTINGS", "services.zeroconf")
    config = Config.from_env()
    assert not protected_setting("services.zeroconf", config.allow_settings)
    assert protected_setting("services.webserver", config.allow_settings)
    ops.c = replace(ops.c, allow_settings=config.allow_settings)
    ops.t.settings["services.zeroconf"] = True
    assert ops.set_core_setting("services.zeroconf", False)["current"] is False
    monkeypatch.setenv("NVIDIA_MCP_ALLOW_SETTINGS", "services.*")
    with pytest.raises(ShieldError):
        Config.from_env()
