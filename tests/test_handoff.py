"""Run the handoff policy across slow shutdown, cancellation and stale readiness."""

import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "contrib/profile-relaunch/src/org/kodimanager/profileswitch/Handoff.java"
)

HARNESS = """
package org.kodimanager.profileswitch;
public final class Harness {
    static void check(boolean condition) {
        if (!condition) throw new AssertionError("unsafe handoff decision");
    }
    public static void main(String[] args) {
        Handoff.Decision armed = Handoff.decide("ARM", 1000, 0, true);
        check(armed.accepted && armed.launchDelay == 0);
        // Shutdown can finish before or well after the old ten-second alarm.
        for (long finished : new long[] {9000, 17000, 91000}) {
            Handoff.Decision ready = Handoff.decide("READY", finished, armed.armedUntil, true);
            check(ready.accepted && ready.armedUntil == 0 && ready.launchDelay == 2000);
            check(!Handoff.decide("READY", finished, ready.armedUntil, true).accepted);
        }
        Handoff.Decision cancelled = Handoff.decide("CANCEL", 17000, armed.armedUntil, false);
        check(cancelled.accepted && cancelled.armedUntil == 0 && cancelled.launchDelay == 0);
        check(!Handoff.decide("READY", 17000, cancelled.armedUntil, true).accepted);
        check(!Handoff.decide("READY", armed.armedUntil, armed.armedUntil, true).accepted);
        check(!Handoff.decide("READY", 17000, 0, true).accepted);
        check(!Handoff.decide("READY", 17000, armed.armedUntil, false).accepted);
        check(!Handoff.decide("ARM", 1000, 0, false).accepted);
        // WATCH (native switch safety net) schedules a later reopen without a lease; CANCEL clears it.
        Handoff.Decision watch = Handoff.decide("WATCH", 1000, armed.armedUntil, true);
        check(watch.accepted && watch.armedUntil == 0 && watch.launchDelay == Handoff.WATCH_DELAY);
        check(Handoff.WATCH_DELAY >= 60000);
        check(!Handoff.decide("WATCH", 1000, 0, false).accepted);
        check(!Handoff.decide("READY", 2000, watch.armedUntil, true).accepted);
        // ARMWATCH (controlled restart): a fresh lease plus the late reopen; READY still works.
        Handoff.Decision armWatch = Handoff.decide("ARMWATCH", 1000, 0, true);
        check(armWatch.accepted && armWatch.armedUntil == armed.armedUntil
              && armWatch.launchDelay == Handoff.WATCH_DELAY);
        Handoff.Decision readyAfterWatch = Handoff.decide("READY", 9000, armWatch.armedUntil, true);
        check(readyAfterWatch.accepted && readyAfterWatch.launchDelay == 2000);
        check(!Handoff.decide("ARMWATCH", 1000, 0, false).accepted);
        check(!Handoff.decide("OTHER", 1000, 0, true).accepted);
        check(!Handoff.decide(null, 1000, 0, true).accepted);
    }
}
"""


@pytest.mark.skipif(not shutil.which("javac") or not shutil.which("java"), reason="needs JDK")
def test_handoff_waits_for_shutdown_and_consumes_one_readiness_lease(tmp_path):
    harness = tmp_path / "Harness.java"
    harness.write_text(HARNESS, encoding="utf-8")
    subprocess.run(
        ["javac", "--release", "8", "-d", str(tmp_path), str(SOURCE), str(harness)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        ["java", "-cp", str(tmp_path), "org.kodimanager.profileswitch.Harness"],
        check=True,
        capture_output=True,
        timeout=15,
    )
