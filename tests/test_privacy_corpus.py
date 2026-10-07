"""H1: every fake secret in the fixture corpus must be redacted; diagnostics must survive."""

import json
import re
from pathlib import Path

import pytest

from nvidia_mcp import privacy

FIXTURES = Path(__file__).parent / "fixtures" / "privacy"
FAKE = re.compile(r"FAKE-[A-Za-z0-9-]+")
# Fake secrets that do not use the FAKE- prefix because realistic files would not.
EXTRA = {
    "advancedsettings.xml": ["hunter22secret", "<user>kodi</user>", "kodimusic"],
    "fen_settings.xml": ["fakeTraktUser01"],
    "pov_settings_v1.xml": ["fakePovUser02"],
    "passwords.xml": ["fakesmbuser", "fakenfsuser"],
    "sources.xml": ["fakesrcuser", "fakedavuser"],
    "kodi.log": ["fakeloguser", "logsmbuser"],
}
KEPT = {
    "advancedsettings.xml": [
        "<host>192.168.1.20</host>",
        "<port>3306</port>",
        "<type>mysql</type>",
        "<memorysize>157286400</memorysize>",
    ],
    "fen_settings.xml": [
        '<setting id="widget_limit">20</setting>',
        '<setting id="rd.enabled">true</setting>',
        '<setting id="trakt.expires">1767225600</setting>',
        '<setting id="results.sort_order" default="true">0</setting>',
    ],
    "pov_settings_v1.xml": ['<setting id="default_action" value="1" />'],
    "profiles.xml": ["<name>Kids</name>", "<lockmode>1</lockmode>", "profiles/kids/"],
    "sources.xml": ["<name>Movies</name>", "<allowsharing>true</allowsharing>"],
    "kodi.log": [
        "Starting Kodi (21.2",
        '"expires_in": 7776000',
        '"scope": "public"',
        "widget_limit=20",
        "mode=list",
        "page=2",
        "'User-Agent': 'Kodi'",
    ],
    "logcat.txt": ["region=GB", "Start proc 4321:org.xbmc.kodi"],
    "tmdbhelper_settings.json": ['"widget_limit": 20', '"host": "192.168.1.20"', '"port": 8080'],
}
FILES = sorted(p.name for p in FIXTURES.iterdir())


def secrets_in(name):
    return FAKE.findall((FIXTURES / name).read_text()) + EXTRA.get(name, [])


@pytest.mark.parametrize("name", FILES)
def test_fixture_secrets_never_survive_file_text_or_text(name):
    raw = (FIXTURES / name).read_text()
    assert secrets_in(name), "fixture must contain fake secrets"
    for redacted in (privacy.file_text(raw), privacy.text(raw)):
        leaked = [s for s in secrets_in(name) if s in redacted]
        assert not leaked, leaked


@pytest.mark.parametrize("name", FILES)
def test_fixture_diagnostics_are_kept(name):
    clean = privacy.file_text((FIXTURES / name).read_text())
    for value in KEPT.get(name, []):
        assert value in clean, value


def test_scrub_json_fixture():
    data = json.loads((FIXTURES / "tmdbhelper_settings.json").read_text())
    clean = json.dumps(privacy.scrub(data))
    assert not FAKE.search(clean)
    assert '"enabled": true' in clean and '"port": 8080' in clean


@pytest.mark.parametrize(
    "setting",
    [
        "trakt.refresh",
        "rd.refresh",
        "rd.auth",
        "pvrparental.pin",
        "masterlock.lockcode",
        "trakt_user",
        "services.webserverpassword",
        "tb.api_key",
        "sessionid",
        "user",
    ],
)
def test_secret_setting_ids(setting):
    assert privacy.is_secret(setting)
    assert privacy.scrub({"id": setting, "value": "v4lue"})["value"] == "[redacted]"


@pytest.mark.parametrize(
    "setting",
    [
        "widget_limit",
        "audiooutput.passthrough",
        "videoplayer.adjustrefreshrate",
        "lookandfeel.skin",
        "rd.enabled",
        "default_action",
        "results.sort_order",
        "monkey",
    ],
)
def test_non_secret_setting_ids(setting):
    assert not privacy.is_secret(setting)


@pytest.mark.parametrize(
    "raw,secret",
    [
        ('{"access_token": "abc123", "password":"pw-9"}', "abc123"),
        ('{"access_token": "abc123", "password":"pw-9"}', "pw-9"),
        ("<user>kodi</user><pass>hunter22secret</pass>", "hunter22secret"),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        ("Bearer abcdEFGH1234", "abcdEFGH1234"),
        ("smb://bob:pa55@nas/share", "pa55"),
        ("nfs://bob:pa55@nas/share", "pa55"),
        ("plugin://plugin.video.x/?token=tok3n&mode=list", "tok3n"),
        ("trakt.refresh=r3fresh", "r3fresh"),
        ("{'pin': 4321}", "4321"),
    ],
)
def test_text_rules(raw, secret):
    assert secret not in privacy.text(raw)
    assert secret not in privacy.file_text(raw)


def test_keymap_key_elements_are_not_redacted():
    xml = '<keymap><global><keyboard><key id="61448">Back</key></keyboard></global></keymap>'
    assert ">Back<" in privacy.file_text(xml)
