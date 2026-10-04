import json

import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.operations import Operations


class FakeTransport:
    def __init__(self, config):
        self.c = config
        self.players = []
        self.running = False
        self.offline = False
        self.profile = "Adults"
        self.calls = []
        self.settings = {"audiooutput.passthrough": False}

    def rpc(self, method, params=None):
        self.calls.append((method, params))
        if self.offline:
            raise ShieldError("offline")
        if method == "Player.GetActivePlayers":
            return self.players
        if method == "Profiles.GetCurrentProfile":
            return {"label": self.profile}
        if method == "Settings.GetSettingValue":
            return {"value": self.settings[params["setting"]]}
        if method == "Settings.SetSettingValue":
            self.settings[params["setting"]] = params["value"]
            return True
        if method == "Addons.GetAddonDetails":
            return {"addon": {"enabled": True}}
        return {"files": [], "limits": {"total": 0}}

    def shell(self, *args, **kwargs):
        self.calls.append(("shell", args))
        if args[:2] == ("sh", "-c"):
            return "1234" if self.running else ""
        if args == ("dumpsys", "activity", "activities"):
            return "mResumedActivity: org.xbmc.kodi/.Splash"
        return ""

    def manager(self, path, method="GET", body=None):
        self.calls.append((path, method, json.loads(json.dumps(body))))
        return {"can_apply": True, "backup_id": "manager-owned-backup"}


@pytest.fixture
def ops(tmp_path):
    mount = tmp_path / "kodi"
    (mount / "userdata").mkdir(parents=True)
    (mount / "userdata/profiles.xml").write_text(
        '<profiles><lastloaded>0</lastloaded><profile id="0"><name>Adults</name><directory>special://masterprofile/</directory></profile><profile id="1"><name>Kids</name><directory>profiles/kids/</directory></profile></profiles>'
    )
    (mount / "userdata/guisettings.xml").write_text(
        '<settings><setting id="audiooutput.passthrough">false</setting></settings>'
    )
    config = Config(
        host="127.0.0.1",
        mount=mount,
        state=tmp_path / "private",
        allow_writes=True,
        allow_plugin_browse=True,
    )
    return Operations(FakeTransport(config))
