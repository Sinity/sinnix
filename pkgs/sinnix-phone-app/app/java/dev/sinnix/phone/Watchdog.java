package dev.sinnix.phone;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.SystemClock;

/**
 * Periodic self-repair.
 *
 * <p>A foreground service is durable, not immortal: MIUI's own memory manager
 * kills background apps aggressively, and START_STICKY only covers the
 * platform's own low-memory path. An inexact repeating alarm gives capture a
 * second way back that does not require a human noticing.
 */
final class Watchdog {

  static final long INTERVAL_MILLIS = 10 * 60 * 1000L;

  private Watchdog() {}

  static void schedule(Context ctx) {
    AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
    if (am == null) {
      return;
    }
    // Inexact and elapsed-realtime: this is a liveness sweep, not a deadline,
    // so it should coalesce with whatever wakeups the platform already plans
    // rather than forcing its own.
    am.setInexactRepeating(
        AlarmManager.ELAPSED_REALTIME_WAKEUP,
        SystemClock.elapsedRealtime() + INTERVAL_MILLIS,
        INTERVAL_MILLIS,
        pendingIntent(ctx));
  }

  static PendingIntent pendingIntent(Context ctx) {
    return PendingIntent.getBroadcast(
        ctx,
        0,
        new Intent(ctx, WatchdogReceiver.class),
        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
  }
}
