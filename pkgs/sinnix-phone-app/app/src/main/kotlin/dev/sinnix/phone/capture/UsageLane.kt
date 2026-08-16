package dev.sinnix.phone.capture

import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps

/**
 * App-foreground, screen and keyguard history, read from the system's own
 * ledger instead of watched from a second app.
 *
 * ActivityWatch's Android watcher polls the foreground app from a process
 * that has to be alive at the moment of the transition; every gap in ITS
 * uptime is a hole in the timeline. UsageStatsManager is the opposite shape:
 * the SYSTEM records every activity resume/pause, screen-interactive change
 * and keyguard transition regardless of who is listening, and this lane
 * reads that ledger with a persisted cursor -- so a reboot, a kill, or a
 * week of the app being broken costs nothing once the next read runs. The
 * system retains these events for well over a month; a 10-minute cadence is
 * luxurious.
 *
 * Same discipline as every other lane here: the query is a binder call, so
 * it runs on its own worker with a busy gate (a slow system service must
 * never stall the capture heartbeat), the cursor only advances after the
 * events are written, and the required appop (GET_USAGE_STATS -- a special
 * grant, `appops set dev.sinnix.phone GET_USAGE_STATS allow`) being absent
 * is a recorded state, not a silent nothing.
 */
class UsageLane(context: Context) {

    private val ctx: Context = context.applicationContext

    private val worker = java.util.concurrent.Executors.newSingleThreadExecutor { r ->
        Thread(r, "usage-lane").apply { isDaemon = true }
    }
    private val busy = java.util.concurrent.atomic.AtomicBoolean(false)
    private var ticksUntilRun = 0
    private var reportedBlocked = false

    fun tick() {
        if (!busy.compareAndSet(false, true)) return
        worker.execute {
            try {
                if (ticksUntilRun > 0) {
                    ticksUntilRun--
                } else {
                    ticksUntilRun = RUN_EVERY_TICKS
                    sweep()
                }
            } finally {
                busy.set(false)
            }
        }
    }

    private fun sweep() {
        if (!Prefs.usageLane(ctx)) return
        val usm = ctx.getSystemService(UsageStatsManager::class.java) ?: return
        val now = System.currentTimeMillis()
        val from = prefs().getLong(KEY_CURSOR, now - FIRST_RUN_LOOKBACK_MILLIS)
        val events =
            try {
                usm.queryEvents(from, now)
            } catch (e: Exception) {
                blocked("query: ${e.message}")
                return
            }
        if (events == null || !events.hasNextEvent()) {
            // An empty window is ambiguous: either nothing happened (rare on
            // a phone in use) or the appop is missing and the system returns
            // an empty iterator rather than throwing. Distinguish by whether
            // ANY event has ever been read.
            if (!prefs().getBoolean(KEY_EVER_READ, false)) {
                blocked("no events readable; GET_USAGE_STATS appop likely missing")
            }
            return
        }
        val ev = UsageEvents.Event()
        var written = 0
        var last = from
        while (events.hasNextEvent()) {
            events.getNextEvent(ev)
            val kind = eventName(ev.eventType) ?: continue
            Events.record(
                ctx,
                "usage",
                "event", kind,
                "package", ev.packageName,
                "class", ev.className,
                "time", Stamps.iso(ev.timeStamp),
            )
            written++
            if (ev.timeStamp > last) last = ev.timeStamp
        }
        // +1: queryEvents is inclusive on the low bound, and re-reading the
        // final event every sweep would be a per-cadence duplicate machine.
        prefs().edit().putLong(KEY_CURSOR, last + 1).putBoolean(KEY_EVER_READ, true).apply()
        if (written > 0) reportedBlocked = false
    }

    private fun blocked(reason: String) {
        if (reportedBlocked) return
        reportedBlocked = true
        Events.record(ctx, "lane_blocked", "lane", "usage", "reason", reason)
    }

    /**
     * The transitions worth keeping; null drops the event. Configuration
     * changes, standby-bucket shuffles and chooser noise say nothing about
     * what the operator was doing.
     */
    private fun eventName(type: Int): String? =
        when (type) {
            UsageEvents.Event.ACTIVITY_RESUMED -> "activity_resumed"
            UsageEvents.Event.ACTIVITY_PAUSED -> "activity_paused"
            UsageEvents.Event.ACTIVITY_STOPPED -> "activity_stopped"
            UsageEvents.Event.SCREEN_INTERACTIVE -> "screen_interactive"
            UsageEvents.Event.SCREEN_NON_INTERACTIVE -> "screen_non_interactive"
            UsageEvents.Event.KEYGUARD_SHOWN -> "keyguard_shown"
            UsageEvents.Event.KEYGUARD_HIDDEN -> "keyguard_hidden"
            UsageEvents.Event.FOREGROUND_SERVICE_START -> "foreground_service_start"
            UsageEvents.Event.FOREGROUND_SERVICE_STOP -> "foreground_service_stop"
            UsageEvents.Event.DEVICE_SHUTDOWN -> "device_shutdown"
            UsageEvents.Event.DEVICE_STARTUP -> "device_startup"
            else -> null
        }

    private fun prefs() = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    companion object {
        private const val PREFS = "sinnix-phone-usage"
        private const val KEY_CURSOR = "cursor_ms"
        private const val KEY_EVER_READ = "ever_read"
        private const val RUN_EVERY_TICKS = 30 // heartbeats at 20s = 10 minutes
        // The system retains usage events for roughly the trailing month or
        // more; take what it will give on the first read.
        private const val FIRST_RUN_LOOKBACK_MILLIS = 30L * 24 * 3600 * 1000
    }
}
