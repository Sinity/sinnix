package dev.sinnix.phone;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Resumes capture after a reboot or an app upgrade.
 *
 * <p>On a file-based-encrypted device BOOT_COMPLETED is delivered after the
 * first unlock, not at power-on, and shared storage is not mounted before
 * that either -- so capture resumes at first unlock rather than truly
 * unattended. That is still the property that was missing: no app has to be
 * opened and nothing has to be tapped.
 */
public class BootReceiver extends BroadcastReceiver {
  @Override
  public void onReceive(Context ctx, Intent intent) {
    String action = intent == null ? null : intent.getAction();
    Log.i(AmbientService.TAG, "boot receiver: " + action);
    // Recorded before the enabled check, and recorded even when capture is
    // meant to be off: a reboot is the only real test of MIUI autostart, and
    // the grants screen infers that grant from whether a chunk follows this
    // line. A boot that produced no event at all is itself the finding.
    Events.record(ctx, "boot", "action", String.valueOf(action), "enabled", Prefs.enabled(ctx));
    if (!Prefs.enabled(ctx)) {
      return;
    }
    Watchdog.schedule(ctx);
    AmbientService.start(ctx);
  }
}
