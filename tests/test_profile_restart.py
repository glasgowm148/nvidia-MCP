import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class Tests(unittest.TestCase):
    def env(self, folder, phase="waiting_saved", dead=False):
        calls = []
        props = {}
        root = Path(folder)
        (root / "kodi.log").write_text("")
        profiles = root / "profiles.xml"
        profiles.write_text(
            "<profiles><lastloaded>0</lastloaded><profile><name>Adults</name></profile><profile><name>Kids</name></profile></profiles>"
        )
        (root / "data").mkdir()
        (root / "data/profile-handoff-token").write_text("test-token")
        window = types.SimpleNamespace(
            setProperty=lambda k, v: props.__setitem__(k, v),
            clearProperty=lambda k: props.pop(k, None),
        )
        xbmc = types.SimpleNamespace(
            getCondVisibility=lambda v: True,
            getInfoLabel=lambda v: "22.0-BETA2",
            LOGINFO=1,
            log=lambda *a: None,
            executebuiltin=lambda s: calls.append(s),
            sleep=lambda ms: None,
        )
        vfs = types.SimpleNamespace(
            translatePath=lambda path: (
                str(profiles)
                if path.endswith("profiles.xml")
                else str(root / "kodi.log")
                if "logpath" in path
                else str(root / "data")
            )
        )
        modules = {
            "xbmc": xbmc,
            "xbmcgui": types.SimpleNamespace(Window=lambda *a: window),
            "xbmcvfs": vfs,
        }
        spec = importlib.util.spec_from_file_location(
            "restart",
            Path(__file__).resolve().parents[1]
            / "contrib/profile-relaunch/kodi/profile_restart.py",
        )
        m = importlib.util.module_from_spec(spec)
        with patch.dict("sys.modules", modules):
            spec.loader.exec_module(m)
        # Production DEX is deliberately excluded from public source. Mocked
        # launches need only private fixture files for the preflight checks.
        m.__file__ = str(root / "profile_restart.py")
        (root / "profile_restart").mkdir()
        (root / "profile_restart/relaunch.sh").write_text("# synthetic fixture\n")
        (root / "profile_restart/classes.dex").write_bytes(b"synthetic fixture")
        child = types.SimpleNamespace(
            poll=lambda: 1 if dead else None, terminate=lambda: calls.append("terminate")
        )

        def launch(args, **kw):
            Path(args[5]).write_text(json.dumps({"phase": phase, "pid": os.getpid(), "index": 1}))
            calls.append(("launch", args, kw))
            return child

        return m, profiles, calls, props, launch

    def test_restart_waits_for_ack_and_preserves_current_profile_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            m, path, calls, props, launch = self.env(folder)
            original = path.read_bytes()
            with patch.object(m.subprocess, "Popen", side_effect=launch):
                m.restart("Kids")
            self.assertEqual(calls[-1], "Quit")
            self.assertTrue(calls[0][2]["start_new_session"])
            self.assertEqual(calls[0][1][2], str(os.getpid()))
            self.assertEqual(calls[0][1][3], "1")
            self.assertEqual(path.read_bytes(), original)

    def test_failed_helper_leaves_kodi_running_and_clears_overlay(self):
        with tempfile.TemporaryDirectory() as folder:
            m, path, calls, props, launch = self.env(folder, dead=True)
            with (
                patch.object(m.subprocess, "Popen", side_effect=launch),
                self.assertRaisesRegex(RuntimeError, "stopped"),
            ):
                m.restart("Kids")
            self.assertNotIn("Quit", calls)
            self.assertFalse(props)

    def test_missing_permission_never_quits_and_explains_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            m, path, calls, props, launch = self.env(folder, dead=True)

            def denied(args, **kw):
                child = launch(args, **kw)
                Path(args[5] + ".launch.log").write_text("relaunch_helper_unavailable\n")
                return child

            with (
                patch.object(m.subprocess, "Popen", side_effect=denied),
                self.assertRaisesRegex(RuntimeError, "relaunch permission"),
            ):
                m.restart("Kids")
            self.assertNotIn("Quit", calls)
            self.assertFalse(props)

    def test_unacknowledged_helper_never_quits_kodi(self):
        with tempfile.TemporaryDirectory() as folder:
            m, path, calls, props, launch = self.env(folder, phase="other")
            with (
                patch.object(m.subprocess, "Popen", side_effect=launch),
                patch.object(m.time, "monotonic", side_effect=[0, 7]),
                self.assertRaisesRegex(RuntimeError, "acknowledge"),
            ):
                m.restart("Kids")
            self.assertNotIn("Quit", calls)
            self.assertIn("terminate", calls)
            self.assertFalse(props)

    def test_unknown_destination_and_wrong_profile_count_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            m, path, *_ = self.env(folder)
            with self.assertRaises(ValueError):
                m.target_index(path, "Nobody")
            path.write_text(
                "<profiles><lastloaded>0</lastloaded><profile><name>Adults</name></profile></profiles>"
            )
            with self.assertRaises(ValueError):
                m.target_index(path, "Adults")

    def test_locked_destination_is_refused_before_the_helper_runs(self):
        for lock in ("<lockmode>1</lockmode>", "<lockmode>0</lockmode><lockcode>1234</lockcode>"):
            with self.subTest(lock), tempfile.TemporaryDirectory() as folder:
                m, path, calls, props, launch = self.env(folder)
                path.write_text(
                    "<profiles><lastloaded>0</lastloaded><profile><name>Adults</name></profile>"
                    "<profile><name>Kids</name>" + lock + "</profile></profiles>"
                )
                with (
                    patch.object(m.subprocess, "Popen", side_effect=launch) as popen,
                    self.assertRaisesRegex(ValueError, "Locked profiles"),
                ):
                    m.restart("Kids")
                popen.assert_not_called()
                self.assertEqual(calls, [])
                self.assertFalse(props)
                self.assertEqual(m.target_index(path, "Adults"), 0)

    def test_workaround_only_applies_to_affected_android_builds(self):
        with tempfile.TemporaryDirectory() as folder:
            m, *_ = self.env(folder)
            self.assertTrue(m.required())
            for version, affected in [
                ("22.0-BETA2 (21.90.801) Git:20260815-0a1b2c3d4e", True),
                ("22.0-RC1 (21.90.901) Git:20260927-28ea2eac1e", True),
                ("22.0-RC1", True),
                ("22.0-RC10 (21.90.910) Git:20261201-0a1b2c3d4e", False),
                ("22.0-RC2 (21.90.902) Git:20261020-0a1b2c3d4e", False),
                ("22.0-BETA20", False),
                ("22.0 (22.0.0) Git:20261101-0a1b2c3d4e", False),
                ("22.1-RC1", False),
                ("21.3 (21.3.0) Git:20251004-0a1b2c3d4e", False),
            ]:
                m.xbmc.getInfoLabel = lambda v, version=version: version
                self.assertIs(m.required(), affected, version)
            m.xbmc.getInfoLabel = lambda v: "22.0-RC1 (21.90.901) Git:20260927-28ea2eac1e"
            m.xbmc.getCondVisibility = lambda v: False  # Not Android.
            self.assertFalse(m.required())


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "contrib/profile-relaunch/kodi/profile_restart/relaunch.sh"
)


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "needs a POSIX shell")
class RelaunchArguments(unittest.TestCase):
    """relaunch.sh must reject malformed numbers before arming or touching profiles.xml."""

    def run_script(self, pid, index, offset):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profiles = root / "profiles.xml"
            profiles.write_text("<profiles><lastloaded>0</lastloaded></profiles>")
            status = root / "result.json"
            done = subprocess.run(
                [
                    shutil.which("sh"),
                    str(SCRIPT),
                    pid,
                    index,
                    str(profiles),
                    str(status),
                    str(root / "x.dex"),
                    str(root / "kodi.log"),
                    offset,
                    "synthetic-token",
                ],
                capture_output=True,
                timeout=20,
                env={"PATH": "/nonexistent"},
            )
            touched = sorted(p.name for p in root.iterdir())
            return done.returncode, touched, profiles.read_text()

    def test_empty_or_non_numeric_arguments_exit_before_arming(self):
        for pid, index, offset in [
            ("4242", "", "0"),
            ("", "1", "0"),
            ("4242", "1", ""),
            ("4242", "1a", "0"),
            ("4242", "-1", "0"),
        ]:
            with self.subTest(pid=pid, index=index, offset=offset):
                code, touched, profiles = self.run_script(pid, index, offset)
                self.assertNotEqual(code, 0)
                self.assertEqual(touched, ["profiles.xml"])  # No launch log, status or temp file.
                self.assertIn("<lastloaded>0</lastloaded>", profiles)


FAKE_LAUNCHER = """#!/bin/sh
# Fake app_process: record the action, answer like a helper (old: no ARMWATCH).
action=$3
echo "$action" >> "$CALLS"
case "$action" in
  arm) echo handoff_armed ;;
  armwatch) if [ -n "$OLD_HELPER" ]; then echo relaunch_helper_unavailable; exit 2; fi
            echo handoff_armed_with_watch ;;
  ready) echo launch_scheduled ;;
  cancel) echo alarm_cancelled ;;
esac
"""

FAKE_TOYBOX = """#!/bin/sh
cmd=$1; shift
case "$cmd" in
  usleep) exec sleep 0.02 ;;
  *) exec "$cmd" "$@" ;;
esac
"""


@unittest.skipUnless(
    os.name == "posix" and shutil.which("sh") and Path("/proc/self/stat").exists(),
    "needs a POSIX shell and /proc",
)
class RelaunchHandoff(unittest.TestCase):
    """relaunch.sh against a fake helper: the late reopen must survive Kodi dying in shutdown."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name, body in (("app_process", FAKE_LAUNCHER), ("toybox", FAKE_TOYBOX)):
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        (bin_dir / "sh").symlink_to(shutil.which("sh"))
        script = SCRIPT.read_text().replace("/system/bin/", str(bin_dir) + "/")
        self.script = self.root / "relaunch.sh"
        self.script.write_text(script)
        self.profiles = self.root / "profiles.xml"
        self.profiles.write_text("<profiles><lastloaded>0</lastloaded></profiles>")
        self.log = self.root / "kodi.log"
        self.log.write_text("start\n")
        self.status = self.root / "result.json"
        self.calls = self.root / "calls"

    def tearDown(self):
        self.tmp.cleanup()

    def run_parent(self, parent_body, old_helper=False):
        """``parent_body`` plays Kodi: it starts the script with its own pid, then acts."""
        offset = self.log.stat().st_size
        env = dict(
            os.environ,
            CALLS=str(self.calls),
            SCRIPT=str(self.script),
            PROFILES=str(self.profiles),
            STATUS=str(self.status),
            LOG=str(self.log),
            OFFSET=str(offset),
            DEX=str(self.root / "classes.dex"),
            TOKEN="token",
        )
        if old_helper:
            env["OLD_HELPER"] = "1"
        launch = (
            'sh "$SCRIPT" $$ 1 "$PROFILES" "$STATUS" "$DEX" "$LOG" "$OFFSET" "$TOKEN" & child=$!\n'
        )
        subprocess.run([shutil.which("sh"), "-c", launch + parent_body], env=env, timeout=30)
        # The script may outlive its parent; wait for its final status.
        for _ in range(200):
            state = self.status.read_text() if self.status.exists() else ""
            if any(p in state for p in ("termination", "reopened", "kodi_died", "save_timeout")):
                break
            subprocess.run(["sleep", "0.05"])
        subprocess.run(["sleep", "0.3"])
        calls = self.calls.read_text().split() if self.calls.exists() else []
        return json.loads(self.status.read_text()), calls

    def say(self, line):
        return 'echo "2026-10-17 12:00:00.000 T:1 info <general>: %s" >> "$LOG"\n' % line

    def test_clean_shutdown_replaces_the_late_reopen_with_ready(self):
        body = (
            "sleep 0.5\n"
            + self.say("XBMCApp: Finishing the activity")
            + "sleep 0.3\n"
            + self.say("Saving skin settings")
            + "sleep 0.3\n"
            + self.say("Application stopped")
            + "sleep 10\n"
        )
        state, calls = self.run_parent(body)
        self.assertEqual(calls, ["arm", "armwatch", "ready"])
        self.assertEqual(state.get("termination"), "saved_settings_and_services_stopped")
        self.assertIn("<lastloaded>1</lastloaded>", self.profiles.read_text())

    def test_kodi_killed_after_finishing_the_activity_reopens_instead_of_cancelling(self):
        # Low-memory killer: Kodi dies after the activity finished, before it saved settings.
        body = "sleep 0.5\n" + self.say("XBMCApp: Finishing the activity") + "sleep 0.5\nexit 0\n"
        state, calls = self.run_parent(body)
        self.assertEqual(calls, ["arm", "armwatch", "ready"])
        self.assertNotIn("cancel", calls)
        self.assertEqual(state["phase"], "reopened_after_kodi_died")
        self.assertIn("<lastloaded>1</lastloaded>", self.profiles.read_text())

    def test_old_helper_without_armwatch_still_completes_the_restart(self):
        body = (
            "sleep 0.5\n"
            + self.say("XBMCApp: Finishing the activity")
            + self.say("Saving skin settings")
            + self.say("Application stopped")
            + "sleep 10\n"
        )
        state, calls = self.run_parent(body, old_helper=True)
        self.assertEqual(calls, ["arm", "armwatch", "ready"])
        self.assertEqual(state.get("termination"), "saved_settings_and_services_stopped")

    def test_save_timeout_while_kodi_lives_cancels_the_reopen(self):
        # Kodi still running but never saved: the restart is abandoned and nothing may reopen.
        state, calls = self.run_parent("sleep 13\n")
        self.assertEqual(state["phase"], "save_timeout")
        self.assertEqual(calls[-1], "cancel")
