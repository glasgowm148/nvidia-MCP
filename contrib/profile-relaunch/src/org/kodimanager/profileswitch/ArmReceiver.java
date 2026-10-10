package org.kodimanager.profileswitch;

import android.app.Activity;
import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
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
            if ("org.kodimanager.profileswitch.CANCEL".equals(request.getAction())) {
                alarms.cancel(next); next.cancel(); setResultCode(Activity.RESULT_OK); return;
            }
            if (!"org.kodimanager.profileswitch.ARM".equals(request.getAction())
                    || !Settings.canDrawOverlays(context)) return;
            // A single user-requested restart, owned by Android, survives Kodi's exit.
            alarms.setAlarmClock(new AlarmManager.AlarmClockInfo(
                System.currentTimeMillis() + 10000L, next), next);
            setResultCode(Activity.RESULT_OK);
        } catch (Exception ignored) {
            // Sender must observe success before asking Kodi to quit.
        }
    }
}
