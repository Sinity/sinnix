package dev.sinnix.phone;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

public class WatchdogReceiver extends BroadcastReceiver {
  @Override
  public void onReceive(Context ctx, Intent intent) {
    if (!Prefs.enabled(ctx)) {
      return;
    }
    if (AmbientService.running) {
      return;
    }
    Log.w(AmbientService.TAG, "watchdog: service not running, restarting");
    AmbientService.start(ctx);
  }
}
