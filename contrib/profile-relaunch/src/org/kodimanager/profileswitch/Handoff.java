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

    public static Decision decide(String action, long now, long armedUntil, boolean permitted) {
        if ("CANCEL".equals(action)) return new Decision(true, 0, 0);
        if (permitted && "ARM".equals(action)) return new Decision(true, now + 120000L, 0);
        if (permitted && "READY".equals(action) && armedUntil > now)
            return new Decision(true, 0, 2000L);
        return new Decision(false, armedUntil, 0);
    }
}
