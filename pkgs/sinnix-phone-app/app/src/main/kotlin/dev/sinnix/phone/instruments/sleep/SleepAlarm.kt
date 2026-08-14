package dev.sinnix.phone.instruments.sleep

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.instruments.Catalogue
import dev.sinnix.phone.ui.instrument.InstrumentActivity

/**
 * Sleep inertia, measured where it actually happens.
 *
 * The decay of cognitive performance after waking is steep and short — most of
 * it is gone within half an hour — which is exactly why it is almost never
 * measured at natural wake time. A lab has to wake you to catch it, and waking
 * you is the confound.
 *
 * The phone already owns the alarm, so it can catch the real thing:
 * `setAlarmClock` fires, the operator dismisses it, and a ten-trial PVT runs
 * immediately on the lock screen. Optional follow-ups at +10 and +30 minutes
 * turn three points into a decay curve.
 *
 * Opt-in ritual, never a default alarm app. Hijacking someone's morning alarm
 * to run a test on them is not a feature, and the instrument is worthless if
 * the operator resents it.
 */
object SleepAlarm {

    private const val REQUEST_WAKE = 7100
    private const val REQUEST_FOLLOWUP = 7101

    const val EXTRA_OFFSET_MIN = "offset_min"

    /**
     * The follow-up ladder, in minutes after dismissal. Inertia is mostly gone
     * by thirty, so a later point would cost a prompt and measure nothing.
     */
    val FOLLOW_UPS = listOf(10, 30)

    fun scheduleFollowUps(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        FOLLOW_UPS.forEach { minutes ->
            val pi =
                PendingIntent.getBroadcast(
                    ctx,
                    REQUEST_FOLLOWUP + minutes,
                    Intent(ctx, SleepAlarmReceiver::class.java)
                        .putExtra(EXTRA_OFFSET_MIN, minutes),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                )
            // Inexact: a decay curve does not need the second point at exactly
            // ten minutes, it needs to know when the point was taken — and the
            // run record carries that.
            am.set(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                android.os.SystemClock.elapsedRealtime() + minutes * 60_000L,
                pi,
            )
        }
    }

    /** Disarm: the alarm and every follow-up it would have scheduled. */
    fun cancel(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        am.cancel(
            PendingIntent.getBroadcast(
                ctx,
                REQUEST_WAKE,
                Intent(ctx, SleepAlarmReceiver::class.java).putExtra(EXTRA_OFFSET_MIN, 0),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
        )
        FOLLOW_UPS.forEach { minutes ->
            am.cancel(
                PendingIntent.getBroadcast(
                    ctx,
                    REQUEST_FOLLOWUP + minutes,
                    Intent(ctx, SleepAlarmReceiver::class.java).putExtra(EXTRA_OFFSET_MIN, minutes),
                    PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                )
            )
        }
        Events.record(ctx, "sleep_alarm_cancelled")
    }

    /**
     * Anchor the protocol to a real alarm clock.
     *
     * `setAlarmClock` rather than a plain exact alarm: it is the one alarm type
     * the platform treats as user-visible and refuses to defer, which is the
     * whole point when the measurement is "what were you like the moment you
     * woke up".
     */
    fun scheduleWake(ctx: Context, triggerAtMs: Long) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        val show =
            PendingIntent.getActivity(
                ctx,
                REQUEST_WAKE,
                Intent(ctx, dev.sinnix.phone.ui.MainActivity::class.java),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
        val fire =
            PendingIntent.getBroadcast(
                ctx,
                REQUEST_WAKE,
                Intent(ctx, SleepAlarmReceiver::class.java).putExtra(EXTRA_OFFSET_MIN, 0),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
        try {
            am.setAlarmClock(AlarmManager.AlarmClockInfo(triggerAtMs, show), fire)
            Events.record(ctx, "sleep_alarm_set", "trigger_at_ms", triggerAtMs)
        } catch (e: SecurityException) {
            // SCHEDULE_EXACT_ALARM can be revoked. The protocol is off rather
            // than approximated: an inertia probe at an unknown offset from
            // waking is not a measurement of inertia.
            Events.record(ctx, "sleep_alarm_refused", "reason", "exact alarms not permitted")
        }
    }
}

class SleepAlarmReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent?) {
        val offset = intent?.getIntExtra(SleepAlarm.EXTRA_OFFSET_MIN, 0) ?: 0
        Events.record(ctx, "sleep_inertia_probe", "offset_min", offset)
        if (offset == 0) SleepAlarm.scheduleFollowUps(ctx)
        // showWhenLocked on the runner Activity is what makes this work without
        // an unlock: the probe has to happen before the operator has properly
        // arrived, or it is measuring someone else's morning.
        InstrumentActivity.launchOne(ctx, Catalogue.SLEEP_INERTIA_PVT.id)
    }
}
