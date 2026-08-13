package dev.sinnix.phone;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * The single bit of persisted intent: whether capture should be running.
 *
 * <p>Boot and watchdog restarts consult it so that an operator who stops
 * capture from the UI does not get it silently resurrected ten minutes later,
 * while an unattended reboot resumes without anyone touching the screen.
 */
final class Prefs {
  private static final String NAME = "sinnix-phone";
  private static final String KEY_ENABLED = "capture_enabled";

  private Prefs() {}

  private static SharedPreferences prefs(Context ctx) {
    return ctx.getApplicationContext().getSharedPreferences(NAME, Context.MODE_PRIVATE);
  }

  static boolean enabled(Context ctx) {
    return prefs(ctx).getBoolean(KEY_ENABLED, true);
  }

  static void setEnabled(Context ctx, boolean value) {
    prefs(ctx).edit().putBoolean(KEY_ENABLED, value).apply();
  }
}
