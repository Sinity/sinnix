package dev.sinnix.phone.core

import android.content.Context
import android.util.Log
import dev.sinnix.phone.ingress.HealthLane
import dev.sinnix.phone.sync.NotificationActionReceiver
import java.util.Calendar
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlin.random.Random

/**
 * The periodic work that is not capture.
 *
 * Driven by the watchdog alarm rather than by alarms of its own. That alarm
 * already fires every ten minutes to check the recorder is alive, so every
 * other periodic question the app has — is an EMA due, has the band written
 * anything, does the widget still say something true — can be answered on the
 * same wakeup for free. Three more alarms would have been three more reasons
 * to wake a sleeping phone to learn that nothing had changed.
 *
 * Ten-minute granularity is coarse, and that is fine for everything here. An
 * EMA prompt is not less useful for arriving at 14:07 rather than 14:00; it is
 * less useful for arriving at 03:00, which is what the waking-hours window is
 * for.
 */
object Scheduler {

    private const val KEY_LAST_EMA = "last_ema_at"
    private const val KEY_EMA_SLOT = "ema_slot_today"

    /** Called from the watchdog receiver, every ~10 minutes. */
    fun tick(ctx: Context) {
        maybePromptEma(ctx)
        maybeSyncHealth(ctx)
        // Prime's way back in. Rides this tick for the same reason everything
        // else does, and because the failure it repairs is only observable
        // from the device -- prime cannot ask a phone it cannot reach.
        dev.sinnix.phone.estate.TransportGuard.tick(ctx)
        dev.sinnix.phone.ui.widget.SinnixWidget.refresh(ctx)
    }

    private fun prefs(ctx: Context) =
        ctx.applicationContext.getSharedPreferences("sinnix-phone-schedule", Context.MODE_PRIVATE)

    /**
     * An EMA prompt, if one is due.
     *
     * Jittered rather than on the hour, because a prompt that arrives at a
     * predictable time is a prompt that gets anticipated, and an anticipated
     * mood sample is a different measurement from a momentary one. The
     * randomness is the method, not a nicety.
     *
     * Waking hours only. A sample at 04:00 measures being woken up.
     */
    private fun maybePromptEma(ctx: Context) {
        val perDay = Prefs.emaPerDay(ctx)
        if (perDay <= 0) return

        val now = System.currentTimeMillis()
        val cal = Calendar.getInstance().apply { timeInMillis = now }
        val hour = cal.get(Calendar.HOUR_OF_DAY)
        if (hour < WAKING_START_HOUR || hour >= WAKING_END_HOUR) return

        val p = prefs(ctx)
        val last = p.getLong(KEY_LAST_EMA, 0L)
        val wakingMillis = (WAKING_END_HOUR - WAKING_START_HOUR) * 3_600_000L
        val spacing = wakingMillis / perDay

        // Two thirds of the nominal spacing, so a missed tick does not push
        // the whole day's samples late, plus jitter up to a third.
        if (now - last < spacing * 2 / 3) return
        val slot = p.getInt(KEY_EMA_SLOT, -1)
        val today = cal.get(Calendar.DAY_OF_YEAR)
        if (slot == today && Random.nextInt(3) != 0) return

        NotificationActionReceiver.postEma(ctx, PROMPTS.random())
        p.edit().putLong(KEY_LAST_EMA, now).putInt(KEY_EMA_SLOT, today).apply()
        Events.record(ctx, "ema_prompted", "per_day", perDay)
    }

    /**
     * Pull whatever the band has written since the last look.
     *
     * Every tick, not hourly. It used to be hourly on the reasoning that
     * Health Connect writes in batches when the band syncs, so asking more
     * often would mostly ask a database that had not changed -- true, and
     * irrelevant: the query is against a local database and costs nothing,
     * while the hour it saved was an hour of latency on every reading. Ten
     * minutes is now the whole phone-side lag, and the rest is Mi Fitness's
     * own band-sync cadence, which is not ours to set.
     *
     * Nothing is stamped here any more. The lane keeps its own changes token
     * and only advances it on a successful read, which is what makes a failed
     * or unpermitted sync retry instead of silently skipping the window it
     * could not read -- the old stamp was written BEFORE the attempt, so an
     * hour's data was dropped every time a sync failed for any reason.
     */
    private fun maybeSyncHealth(ctx: Context) {
        if (!Prefs.healthLane(ctx)) {
            Log.i(Storage.TAG, "health lane: off, skipping")
            return
        }
        // Unconditional, because the absence of any health event was
        // indistinguishable from the tick never running -- and it turned out
        // to be worth knowing which.
        Log.i(Storage.TAG, "health lane: syncing")
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val n = HealthLane.sync(ctx)
                if (n > 0) Log.i(Storage.TAG, "health lane: $n record(s)")
            } catch (e: Exception) {
                Log.w(Storage.TAG, "health sync failed", e)
            }
        }
    }

    private const val WAKING_START_HOUR = 9
    private const val WAKING_END_HOUR = 23

    /**
     * Short, answerable in one word, and about right now.
     *
     * Deliberately not a scale-and-submit form: the whole compliance argument
     * for shade-answerable EMA is that answering costs one tap and one word,
     * and a prompt that needs consideration is a prompt answered later, which
     * is to say not momentarily.
     */
    private val PROMPTS =
        listOf(
            "How is it going, right now?",
            "What are you doing?",
            "How's your energy?",
            "Where's your attention?",
            "How do you feel?",
        )
}
