package dev.sinnix.phone.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Storage

/**
 * Resumes capture after a reboot or an app upgrade.
 *
 * On a file-based-encrypted device BOOT_COMPLETED is delivered after the first
 * unlock, not at power-on, and shared storage is not mounted before that
 * either — so capture resumes at first unlock rather than truly unattended.
 * That is still the property that was missing: no app has to be opened and
 * nothing has to be tapped.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent?) {
        val action = intent?.action
        Log.i(Storage.TAG, "boot receiver: $action")
        // Recorded before the enabled check, and recorded even when capture is
        // meant to be off: a reboot is the only real test of MIUI autostart,
        // and the grants screen infers that grant from whether a chunk follows
        // this line. A boot that produced no event at all is itself the finding.
        Events.record(ctx, "boot", "action", action.toString(), "enabled", Prefs.enabled(ctx))
        Watchdog.schedule(ctx)
        // The speech lane comes back on its own schedule, not the recorder's:
        // it has its own preference, and gating it behind capture_enabled would
        // silently tie two independent lanes together. Started before the
        // recorder's own check for the same reason.
        if (Prefs.speechLane(ctx)) SpeechService.start(ctx)
        if (!Prefs.enabled(ctx)) return
        AmbientService.start(ctx)
    }
}
