package dev.sinnix.phone.capture

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.util.Log
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Storage
import dev.sinnix.phone.sync.InboxWatcher

/**
 * Periodic self-repair.
 *
 * A foreground service is durable, not immortal: MIUI's own memory manager
 * kills background apps aggressively, and START_STICKY only covers the
 * platform's own low-memory path. An inexact repeating alarm gives capture a
 * second way back that does not require a human noticing.
 */
object Watchdog {

    const val INTERVAL_MILLIS = 10 * 60 * 1000L

    fun schedule(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        // Inexact and elapsed-realtime: this is a liveness sweep, not a
        // deadline, so it should coalesce with whatever wakeups the platform
        // already plans rather than forcing its own.
        am.setInexactRepeating(
            AlarmManager.ELAPSED_REALTIME_WAKEUP,
            SystemClock.elapsedRealtime() + INTERVAL_MILLIS,
            INTERVAL_MILLIS,
            pendingIntent(ctx),
        )
    }

    fun pendingIntent(ctx: Context): PendingIntent =
        PendingIntent.getBroadcast(
            ctx,
            0,
            Intent(ctx, WatchdogReceiver::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
}

class WatchdogReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent?) {
        // The sweep also drains the inbox. When capture is disabled this alarm
        // is the only thing still running on a schedule, and receipts arriving
        // from prime should not be invisible just because the microphone is off.
        InboxWatcher.sweepOnce(ctx)
        // Everything else periodic rides this same wakeup rather than adding
        // alarms of its own — see Scheduler for why that is the whole design.
        dev.sinnix.phone.core.Scheduler.tick(ctx)

        // The speech lane is a separate service with the same mortality as the
        // recorder, so the sweep that revives one revives the other.
        if (Prefs.speechLane(ctx)) SpeechService.start(ctx)

        if (!Prefs.enabled(ctx)) return
        if (AmbientService.running) return
        Log.w(Storage.TAG, "watchdog: service not running, restarting")
        AmbientService.start(ctx)
    }
}
