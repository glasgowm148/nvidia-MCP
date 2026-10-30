package org.kodimanager.profileswitch;

/** A bounded readiness lease; arming alone must never launch the closing app. */
public final class Handoff {
    private Handoff() {}

    public static final class Decision {
        public final boolean accepted;
        public final long armedUntil;
        public final long launchDelay;

        private Decision(boolean accepted, long armedUntil, long launchDelay) {
            this.accepted = accepted;
            this.armedUntil = armedUntil;
            this.launchDelay = launchDelay;
        }
    }

    /** WATCH / ARMWATCH: reopen Kodi this long from now unless cancelled or replaced by READY. */
    public static final long WATCH_DELAY = 75000L;
    /** READY: reopen Kodi this long after the acknowledged shutdown. */
    public static final long READY_DELAY = 1000L;

    public static Decision decide(String action, long now, long armedUntil, boolean permitted) {
        if ("CANCEL".equals(action)) return new Decision(true, 0, 0);
        // A native in-process switch is armed just before Kodi's crash-prone profile unload and
        // cancelled by the destination profile once it has loaded.
        if (permitted && "WATCH".equals(action)) return new Decision(true, 0, WATCH_DELAY);
        // A controlled restart arms the usual lease and the same late reopen: if Android kills
        // Kodi (and its relaunch child) during shutdown, READY never comes and the reopen fires.
        if (permitted && "ARMWATCH".equals(action)) return new Decision(true, now + 120000L, WATCH_DELAY);
        if (permitted && "ARM".equals(action)) return new Decision(true, now + 120000L, 0);
        // READY: the child kills the old Kodi process right after this; one second leaves
        // Android time to reap it before the new launch (it was two seconds before 1.4).
        if (permitted && "READY".equals(action) && armedUntil > now)
            return new Decision(true, 0, READY_DELAY);
        return new Decision(false, armedUntil, 0);
    }
}
