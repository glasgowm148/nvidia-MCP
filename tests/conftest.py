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
        # Body of `dumpsys media_session` after its header; see media_session() below.
        self.media = ""

    def rpc(self, method, params=None):
        self.calls.append((method, params))
        if self.offline:
            # What a stopped/hung Kodi HTTP server looks like to the real transport.
            raise ShieldError("Cannot reach device HTTP service", "unreachable")
        if method == "Player.GetActivePlayers":
            return self.players
        if method == "Profiles.GetCurrentProfile":
            return {"label": self.profile}
        if method == "Settings.GetSettingValue":
            return {"value": self.settings[params["setting"]]}
        if method == "Settings.SetSettingValue":
            self.settings[params["setting"]] = params["value"]
            return True
        if method == "Application.Quit":
            self.running = False  # A clean exit; tests/test_lifecycle_exit.py covers hangs.
            return "OK"
        if method == "Addons.GetAddonDetails":
            return {"addon": {"enabled": True}}
        return {"files": [], "limits": {"total": 0}}

    def shell(self, *args, **kwargs):
        self.calls.append(("shell", args))
        if args[:2] == ("sh", "-c"):
            return "1234" if self.running else ""
        if args[:2] == ("am", "force-stop"):
            self.running = False
        if args == ("dumpsys", "activity", "activities"):
            return "mResumedActivity: org.xbmc.kodi/.Splash"
        if args == ("dumpsys", "media_session"):
            return "MEDIA SESSION SERVICE (dumpsys media_session)\n" + self.media
        return ""

    def manager(self, path, method="GET", body=None):
        self.calls.append((path, method, json.loads(json.dumps(body))))
        return {"can_apply": True, "backup_id": "manager-owned-backup"}


def media_session(package, state, active=True):
    """One session block in the shape Android 9-11 `dumpsys media_session` prints."""
    return (
        f"    {package}/MediaSession (userId=0)\n"
        f"      ownerPid=4242, ownerUid=10085, userId=0\n"
        f"      package={package}\n"
        f"      launchIntent=null\n"
        f"      active={'true' if active else 'false'}\n"
        f"      flags=3\n"
        f"      state=PlaybackState {{state={state}, position=1000, buffered position=0, "
        f"speed=1.0, updated=1, actions=822, custom actions=[], active item id=-1, error=null}}\n"
    )


@pytest.fixture
def ops(tmp_path):
    mount = tmp_path / "kodi"
    (mount / "userdata").mkdir(parents=True)
    (mount / "userdata/profiles.xml").write_text(
        "<profiles><lastloaded>0</lastloaded><profile><id>0</id><name>Adults</name><directory>special://masterprofile/</directory></profile><profile><id>1</id><name>Kids</name><directory>profiles/kids/</directory></profile></profiles>"
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
    operations = Operations(FakeTransport(config))
    operations.quit_wait = 0  # No real waiting for a fake Kodi to exit.
    return operations
