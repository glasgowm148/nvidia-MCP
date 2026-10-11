"""Profile resolution against Kodi's real profiles.xml layout.

Kodi writes ``<id>`` as a child element and ``<lastloaded>`` as the profile's position in the
file. Ids and positions diverge once a profile has been deleted.
"""

import pytest

from nvidia_mcp.config import ShieldError

REAL = """<profiles>
    <lastloaded>{last}</lastloaded>
    <useloginscreen>false</useloginscreen>
    <autologin>-1</autologin>
    <nextIdProfile>3</nextIdProfile>
    <profile>
        <id>0</id>
        <name>Master user</name>
        <directory pathversion="1">special://masterprofile/</directory>
        <hasdatabases>true</hasdatabases>
    </profile>
    <profile>
        <id>2</id>
        <name>Kids</name>
        <directory pathversion="1">{kids}</directory>
        <hasdatabases>true</hasdatabases>
    </profile>
</profiles>
"""


def write_profiles(ops, last=0, kids="profiles/kids/"):
    (ops.c.mount / "userdata/profiles.xml").write_text(REAL.format(last=last, kids=kids))


def stop_kodi(ops):
    ops.t.offline = True
    ops.t.running = False


def test_master_profile_resolves_while_kodi_runs(ops):
    write_profiles(ops)
    ops.t.profile = "Master user"
    assert ops.profile_userdata() == "userdata"


def test_set_setting_backs_up_master_guisettings(ops):
    write_profiles(ops)
    ops.t.profile = "Master user"
    result = ops.set_core_setting("audiooutput.passthrough", True)
    assert ops.files.restore_data(result["backup_id"])[0] == "userdata/guisettings.xml"


def test_stopped_kodi_uses_lastloaded_position_not_id(ops):
    write_profiles(ops, last=1)
    stop_kodi(ops)
    assert ops.profile_userdata() == "userdata/profiles/kids"
    write_profiles(ops, last=0)
    assert ops.profile_userdata() == "userdata"


def test_stopped_kodi_refuses_out_of_range_lastloaded(ops):
    write_profiles(ops, last=2)  # The deleted-profile id, not a valid position.
    stop_kodi(ops)
    with pytest.raises(ShieldError, match="uniquely resolve"):
        ops.profile_userdata()


def test_absolute_masterprofile_directory_is_supported(ops):
    write_profiles(ops, kids="special://masterprofile/profiles/kids/")
    ops.t.profile = "Kids"
    assert ops.profile_userdata() == "userdata/profiles/kids"


@pytest.mark.parametrize(
    "directory", ["special://masterprofile/", "profiles/../../addons/", "/storage/elsewhere/"]
)
def test_secondary_profile_cannot_alias_master_or_escape(ops, directory):
    write_profiles(ops, kids=directory)
    ops.t.profile = "Kids"
    with pytest.raises(ShieldError):
        ops.profile_userdata()


def test_offline_addon_setting_edits_the_last_loaded_profile(ops):
    addon = "plugin.video.example"
    (ops.c.mount / "addons" / addon).mkdir(parents=True)
    (ops.c.mount / "addons" / addon / "addon.xml").write_text(f'<addon id="{addon}" version="1"/>')
    for folder in ("userdata", "userdata/profiles/kids"):
        data = ops.c.mount / folder / "addon_data" / addon
        data.mkdir(parents=True)
        (data / "settings.xml").write_text(
            '<settings><setting id="autoplay">false</setting></settings>'
        )
    write_profiles(ops, last=1)
    stop_kodi(ops)
    ops.set_addon_setting(addon, "1", "autoplay", True)
    kids = ops.c.mount / "userdata/profiles/kids/addon_data" / addon / "settings.xml"
    master = ops.c.mount / "userdata/addon_data" / addon / "settings.xml"
    assert ">true<" in kids.read_text() and ">false<" in master.read_text()
