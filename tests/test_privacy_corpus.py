"""H1: every fake secret in the fixture corpus must be redacted; diagnostics must survive."""

import json
import re
import time
from pathlib import Path

import pytest

from nvidia_mcp import privacy
from nvidia_mcp.config import ShieldError

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
        ('password="hunter 2 with space"', "2 with space"),
        ("password = 'hunter 2 with space'", "with space"),
        ('"token" = "abc def"', "def"),
        ('{\\"password\\":\\"hunter2secret\\"}', "hunter2secret"),
        ('log: {\\"access_token\\": \\"abc 123\\", \\"mode\\": 1}', "abc 123"),
    ],
)
def test_text_rules(raw, secret):
    assert secret not in privacy.text(raw)
    assert secret not in privacy.file_text(raw)


@pytest.mark.parametrize(
    "raw,redacted",
    [
        # A quoted value is redacted to its closing quote, spaces included.
        ('password="hunter 2 with space" mode=1', 'password="[redacted]" mode=1'),
        ('password = "hunter 2 with space"', 'password = "[redacted]"'),
        ("pass='a b', user=bob", "pass='[redacted]', user=[redacted]"),
        ('token=abc"', 'token=[redacted]"'),
        # JSON escaped inside a string (a log line quoting a request body).
        ('{\\"password\\":\\"hunter2secret\\"}', '{\\"password\\":\\"[redacted]\\"}'),
        ('{\\"mode\\":\\"play\\",\\"pin\\":1234}', '{\\"mode\\":\\"play\\",\\"pin\\":[redacted]}'),
        ('{"password": "[redacted]"}', '{"password": "[redacted]"}'),
    ],
)
def test_quoted_values_are_redacted_whole(raw, redacted):
    assert privacy.text(raw) == redacted
    assert privacy.text(redacted) == redacted


def test_keymap_key_elements_are_not_redacted():
    xml = '<keymap><global><keyboard><key id="61448">Back</key></keyboard></global></keymap>'
    assert ">Back<" in privacy.file_text(xml)


@pytest.mark.parametrize(
    "label",
    [
        "Addon.SettingStr(plugin.video.fen,rd.auth)",
        "addon.settingstr(plugin.video.pov,tb.token)",
        "Addon.SettingInt(plugin.video.fen,trakt.expires)",
        "Skin.String(pin)",
        "Window(Home).Property(fen.trakt.refresh)",
        "$INFO[Addon.SettingStr(plugin.video.fen,rd.auth)]",
        "Window(Home).Property(fenlight.debrid.rd)",
        "Skin.String(PVRAccessCode)",
        "Window.Property(TraktUser)",
    ],
)
def test_info_labels_cannot_read_addon_settings_or_secrets(ops, label):
    with pytest.raises(ShieldError, match="kodi_list_addon_settings"):
        ops.rpc_read("XBMC.GetInfoLabels", {"labels": ["System.BuildVersion", label]})
    assert not any(c[0] == "XBMC.GetInfoLabels" for c in ops.t.calls)


@pytest.mark.parametrize(
    "boolean",
    [
        # A boolean oracle extracts a token one character at a time.
        "String.StartsWith(Addon.SettingStr(plugin.video.fen,rd.auth),a)",
        "String.IsEqual(Skin.String(PVRAccessCode),1234)",
        "String.Contains(Window(Home).Property(fenlight.debrid.rd),x)",
        "String.IsEmpty(Addon.SettingBool(plugin.video.pov,trakt.enabled))",
    ],
)
def test_info_booleans_cannot_probe_addon_settings_or_secrets(ops, boolean):
    with pytest.raises(ShieldError, match="secret_read|kodi_addon_settings") as error:
        ops.rpc_read("XBMC.GetInfoBooleans", {"booleans": ["Player.HasVideo", boolean]})
    assert error.value.kind == "secret_read"
    assert not any(c[0] == "XBMC.GetInfoBooleans" for c in ops.t.calls)


def test_ordinary_info_booleans_still_work(ops):
    ops.rpc_read(
        "XBMC.GetInfoBooleans",
        {"booleans": ["Player.HasVideo", "Skin.HasSetting(HomeMenuNoMoviesButton)"]},
    )
    assert any(c[0] == "XBMC.GetInfoBooleans" for c in ops.t.calls)


def test_ordinary_info_labels_still_work(ops):
    ops.rpc_read(
        "XBMC.GetInfoLabels",
        {
            "labels": [
                "System.BuildVersion",
                "Skin.String(HomeMenuNoMoviesButton)",
                "Window.Property(xmlfile)",
            ]
        },
    )
    assert any(c[0] == "XBMC.GetInfoLabels" for c in ops.t.calls)


# Kodi logs and plugin:// paths usually carry nested URLs percent-encoded or JSON-escaped.
ENCODED_LEAKS = [
    (
        "Playlist: plugin://plugin.video.fen/?mode=play&url=https%3A%2F%2Fabcd.download."
        "real-debrid.com%2Fd%2FFAKEPATH01%2Ffile.mkv%3Ftoken%3DFAKETOK01",
        ["FAKEPATH01", "FAKETOK01", "real-debrid"],
        ["mode=play"],
    ),
    (
        "info <general>: Creating InputStream - url=http%3a%2f%2fu%3aFAKEPASS02%40host%2fstream",
        ["FAKEPASS02"],
        ["Creating InputStream"],
    ),
    ('{"url": "https:\\/\\/x.alldebrid.com\\/dl\\/FAKEAD03"}', ["FAKEAD03", "alldebrid"], []),
    ("cache key access_token%3DFAKETOK04", ["FAKETOK04"], ["cache key"]),
    (
        "CCurlFile::Open failed for https:\\/\\/api.real-debrid.com\\/rest\\/1.0\\/unrestrict"
        "?auth_token\\u003dFAKETOK05",
        ["FAKETOK05"],
        ["CCurlFile::Open failed"],
    ),
    ("headers: Authorization%3A%20Bearer%20FAKEBEARER06", ["FAKEBEARER06"], ["headers"]),
    (
        "script param: ['plugin://plugin.video.fen/?mode=playback&rd_link=https%3A%2F%2F1."
        "download.real-debrid.com%2Fd%2FFAKELINK07', '1']",
        ["FAKELINK07"],
        ["mode=playback"],
    ),
    ("davs://user:p@FAKEPASS08@host/share", ["FAKEPASS08"], ["@host/share"]),
    ("{'access_token': u'FAKETOK09'}", ["FAKETOK09"], []),
    ("premiumize customer_id: FAKECUST10 ready", ["FAKECUST10"], ["ready"]),
    (
        ".real-debrid.com\tTRUE\t/\tTRUE\t1999999999\tauth\tFAKECOOKIE11\n",
        ["FAKECOOKIE11"],
        [".real-debrid.com"],
    ),
]


@pytest.mark.parametrize("sample,secrets,kept", ENCODED_LEAKS)
def test_encoded_and_escaped_secrets_are_redacted(sample, secrets, kept):
    clean = privacy.text(sample)
    assert not [s for s in secrets if s in clean], clean
    assert all(k in clean for k in kept), clean


@pytest.mark.parametrize(
    "line",
    [
        "url=https%3A%2F%2Fx%2Fd%3Ftoken%3DFAKETOK12",
        "access_token%3DFAKETOK13",
        "u%3AFAKE%40host smb%3A%2F%2Fu%3AFAKEPASS14%40nas%2Fshare",
    ],
)
def test_patches_cannot_touch_encoded_secrets(line):
    assert privacy.contains_secret(line)


def test_benign_encoded_paths_are_kept():
    sample = "special%3A%2F%2Fprofile%2Fplaylists plugin%3A%2F%2Fplugin.video.fen%2F%3Fmode%3Dlist"
    assert privacy.text(sample) == sample


@pytest.mark.parametrize("setting", ["tmdb_api", "omdb_api", "fanart.tv.client", "customer_id"])
def test_personal_api_keys_are_secret(setting):
    xml = f'<settings version="2"><setting id="{setting}">FAKEKEY15</setting></settings>'
    assert "FAKEKEY15" not in privacy.file_text(xml)
    assert "FAKEKEY15" not in privacy.text(xml)


def test_cookie_files_are_withheld():
    jar = "# Netscape HTTP Cookie File\n.example.com\tTRUE\t/\tTRUE\t1999999999\tsid\tFAKE16\n"
    assert "FAKE16" not in privacy.file_text(jar)


# A key-like word inside one quoted value must not pair with the next value's opening quote.
@pytest.mark.parametrize(
    "raw,redacted",
    [
        ('prompt="Enter PIN:" pin="1234"', 'prompt="Enter PIN:" pin="[redacted]"'),
        (
            'DEBUG: dialog heading="Trakt token:" token="abcd1234efgh"',
            'DEBUG: dialog heading="Trakt token:" token="[redacted]"',
        ),
        ("label='API key:' api_key='sk-123456'", "label='API key:' api_key='[redacted]'"),
        ('msg="user=" password="hunter2"', 'msg="user=" password="[redacted]"'),
        (
            '<x heading="Password:" password="hunter2"/>',
            '<x heading="Password:" password="[redacted]"/>',
        ),
        ('token="abc def"', 'token="[redacted]"'),
        ('auth: "Bearer x" foo', 'auth: "[redacted]" foo'),
        ('{"x": "key: \\"abc def\\""}', '{"x": "key: \\"[redacted]\\""}'),
        ('\\"password\\":\\"abc\\\\\\"def\\"', '\\"password\\":\\"[redacted]\\"'),
        ('Debug: user=" Some Movie (2020)" played', 'Debug: user="[redacted]" played'),
    ],
)
def test_quoted_values_do_not_pair_across_values(raw, redacted):
    assert privacy.text(raw) == redacted
    assert privacy.text(redacted) == redacted


@pytest.mark.parametrize(
    "raw",
    [
        '{"label": "Password:", "value": "visible", "other": "keep me"}',
        '{"label": "Trakt account: ", "id": "x"}',
        '{"help": "Set token=", "enabled": true, "name": "Fen"}',
        '<string id="30001">Username:</string><string id="30002">"Server"</string>',
        'msg="Enter pin: " title="Kodi Movies" year="2020"',
        '{"label": "API key: ", "path": "/storage/a b", "name": "z"}',
    ],
)
def test_labels_mentioning_secrets_are_kept(raw):
    assert privacy.text(raw) == raw
    assert not privacy.contains_secret(raw)


@pytest.mark.parametrize(
    "line", ["password = ''", 'password=""', "pin=''", '"password": ""', "{'token': ''}"]
)
def test_empty_secret_values_are_not_secrets(line):
    # Patches that only touch an empty default must not be refused as secret edits.
    assert not privacy.contains_secret(line)
    assert privacy.text(line) == line


def test_empty_value_does_not_hide_the_next_secret():
    assert privacy.text('password="" token="abc"') == 'password="" token="[redacted]"'


ADVERSARIAL = {
    "quotes": '"' * 100_000,
    "backslash_quotes": '\\"' * 50_000,
    "unclosed_token": 'token="\\x' * 11_000,
    "escaped_pairs": '\\"a\\":\\"' * 11_000,
    "key_runs": "token" * 20_000,
    "segment_runs": "a.pin" * 20_000,
    "label_runs": 'x="Enter PIN:" ' * 6_500,
    "mixed": 'password="a b\\" ' * 6_000,
}


@pytest.mark.parametrize("name", sorted(ADVERSARIAL))
def test_redaction_is_linear_on_adversarial_input(name):
    sample = ADVERSARIAL[name]
    start = time.perf_counter()
    privacy.text(sample)
    privacy.file_text(sample)
    assert time.perf_counter() - start < 5.0


LWP_JAR = (
    "#LWP-Cookies-2.0\n"
    'Set-Cookie3: ckns_atkn="SECRETVALUE/abc+def=="; path="/"; domain=.bbc.co.uk; path_spec;'
    ' domain_dot; secure; expires="2026-10-15 14:28:40Z"; version=0\n'
    'Set-Cookie3: ckns_id=IDTOKENSECRET123; path="/"; domain=.bbc.co.uk; version=0\n'
)


def test_lwp_cookie_files_are_withheld():
    assert privacy.file_text(LWP_JAR) == "[Cookie file; contents withheld]"


@pytest.mark.parametrize(
    "line,secret",
    [
        ('Set-Cookie3: session="abc/def+ghi="; path="/"', "abc/def+ghi="),
        ('Set-Cookie3: ckns_rtkn="r3fr3sh/T0KEN=="; domain=.bbc.co.uk', "r3fr3sh/T0KEN=="),
        ("Set-Cookie3: ckns_id=IDTOKENSECRET123; path=/", "IDTOKENSECRET123"),
        ("Set-Cookie: sid=abc123def; Path=/", "abc123def"),
    ],
)
def test_set_cookie_values_are_redacted(line, secret):
    for clean in (privacy.text(line), privacy.file_text(line), privacy.text(LWP_JAR)):
        assert secret not in clean
    assert privacy.text(privacy.text(line)) == privacy.text(line)
