package org.kodimanager.profileswitch;

import android.app.Activity;
import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.SystemClock;
import android.provider.Settings;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Offline, explicit, authenticated one-shot Kodi handoff. No boot or timer loop. */
public final class ArmReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent request) {
        setResultCode(Activity.RESULT_CANCELED);
        try {
            String supplied = request.getStringExtra("token");
            if (supplied == null) return;
            byte[] expected;
            try (InputStream stream = context.getAssets().open("handoff-token")) {
                byte[] buffer = new byte[128]; int count = stream.read(buffer);
                if (count < 1 || count >= buffer.length) return;
                expected = java.util.Arrays.copyOf(buffer, count);
            }
            if (!MessageDigest.isEqual(expected, supplied.getBytes(StandardCharsets.UTF_8))) return;
            Intent launch = new Intent().setComponent(new ComponentName("org.xbmc.kodi", "org.xbmc.kodi.Splash"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            PendingIntent next = PendingIntent.getActivity(context, 45644, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            AlarmManager alarms = (AlarmManager) context.getSystemService(Context.ALARM_SERVICE);
            String action = request.getAction();
            String prefix = "org.kodimanager.profileswitch.";
            if (action == null || !action.startsWith(prefix)) return;
            SharedPreferences state = context.getSharedPreferences("handoff", Context.MODE_PRIVATE);
            Handoff.Decision decision = Handoff.decide(action.substring(prefix.length()),
                SystemClock.elapsedRealtime(), state.getLong("armed_until", 0),
                Settings.canDrawOverlays(context));
            if (!decision.accepted) return;
            if (!state.edit().putLong("armed_until", decision.armedUntil).commit()) return;
            if (decision.launchDelay == 0) {
                // ARM proves permission and clears any older launch. It cannot
                // reopen Kodi while native shutdown is still running.
                alarms.cancel(next);
                if ("CANCEL".equals(action.substring(prefix.length()))) next.cancel();
            } else {
                // READY is sent only at Application stopped. Android owns this
                // one-shot launch after the child ends Kodi's old process. WATCH
                // and ARMWATCH schedule a later launch (same PendingIntent, so READY
                // replaces it) that only fires if Kodi died before READY or before
                // the destination profile cancelled it.
                alarms.setAlarmClock(new AlarmManager.AlarmClockInfo(
                    System.currentTimeMillis() + decision.launchDelay, next), next);
            }
            setResultData("shutdown-ready-v2");
            setResultCode(Activity.RESULT_OK);
        } catch (Exception ignored) {
            // Sender must observe success before asking Kodi to quit.
        }
    }
}
