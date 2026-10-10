import importlib.util
import json
import os
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

    def test_workaround_only_applies_to_affected_android_beta(self):
        with tempfile.TemporaryDirectory() as folder:
            m, *_ = self.env(folder)
            self.assertTrue(m.required())
            m.xbmc.getInfoLabel = lambda v: "22.0"
            self.assertFalse(m.required())
