package dev.sinnix.phone.instruments

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.sync.Inbox
import java.util.Calendar
import java.util.TimeZone
import org.json.JSONObject

/** The single thing home is asking. `nothing due` is a legitimate answer. */
data class Ask(val title: String, val detail: String = "", val route: String? = null)

/**
 * What to measure next, decided rather than listed.
 *
 * A flat catalogue of twenty instruments is a compliance disaster: choosing is
 * work, and work at the moment of measurement is what stops the measurement
 * happening. So the unit is the Check — two to four instruments, under three
 * minutes, assembled here — and the shelf exists behind it precisely so this
 * policy can stay opinionated.
 */
object OfferPolicy {

    private const val CHECK_BUDGET_SECONDS = 180

    /**
     * Assemble a Check.
     *
     * Rules, in order of authority:
     * 1. The PVT if none in twelve hours. It is the most validated instrument
     *    in the catalogue and the one most directly sensitive to the sleep
     *    problem this whole program is aimed at.
     * 2. Prefer instruments whose covariate cells are empty. The value is in
     *    the time series, so a measurement at an hour of day never sampled is
     *    worth more than the fifth one at 21:00.
     * 3. Respect the declared energy state.
     * 4. Never offer an auditory instrument with no headphones connected — it
     *    is not in the deck at all, rather than offered and then refused.
     */
    fun assembleCheck(ctx: Context): List<Instrument> {
        val runs = recentRuns(ctx, days = 14)
        val energy = Prefs.energyState(ctx)
        val headphones = headphonesConnected(ctx)
        val hour = hourOfDay()

        val eligible =
            Catalogue.all.filter { i ->
                when {
                    i.id == Catalogue.SLEEP_INERTIA_PVT.id -> false // alarm-anchored only
                    i.needsHeadphones && !headphones -> false
                    energy == "low" && i.energy == Energy.GOOD_ONLY -> false
                    energy == "good" && i.energy == Energy.LOW_OK -> false
                    else -> true
                }
            }

        val check = ArrayList<Instrument>()
        var budget = CHECK_BUDGET_SECONDS

        val lastPvt = runs.filter { it.optString("instrument") == Catalogue.PVT.id }.maxOfOrNull {
            Stamps.parse(it.optString("ts"))
        } ?: 0L
        if (System.currentTimeMillis() - lastPvt > 12 * 3_600_000L &&
            eligible.contains(Catalogue.PVT)
        ) {
            check += Catalogue.PVT
            budget -= Catalogue.PVT.seconds
        }

        // Coverage of the time-of-day cell, then recency. Both are "how much
        // would this run add", which is the only question worth ranking on.
        val ranked =
            eligible
                .filterNot { it in check }
                .sortedBy { i ->
                    val cell = runs.count { r ->
                        r.optString("instrument") == i.id && r.optInt("hour_of_day", -1) == hour
                    }
                    val lastRun =
                        runs.filter { it.optString("instrument") == i.id }
                            .maxOfOrNull { Stamps.parse(it.optString("ts")) } ?: 0L
                    // Sparse cells first; among equals, the least recently run.
                    cell * 1_000_000_000L + lastRun / 1000L
                }

        for (i in ranked) {
            if (check.size >= 4) break
            if (i.seconds > budget) continue
            check += i
            budget -= i.seconds
        }
        return check
    }

    /**
     * The shelf: everything runnable right now, with the reason anything is
     * not. Refusals are shown rather than hidden, because "why can I not run
     * the pitch task" has an answer and hiding it makes the app feel arbitrary.
     */
    fun shelf(ctx: Context): List<Pair<Instrument, String?>> {
        val headphones = headphonesConnected(ctx)
        return Catalogue.all.map { i ->
            i to
                when {
                    i.needsHeadphones && !headphones -> "needs headphones"
                    i.id == Catalogue.SLEEP_INERTIA_PVT.id -> "runs when the alarm does"
                    else -> null
                }
        }
    }

    /**
     * The one ask on home.
     *
     * Priority order is about interruption cost, not importance: an agent
     * blocked on a question is waiting on a human, a commitment has a
     * deadline, and a Check will still be there in an hour.
     */
    fun currentAsk(ctx: Context, glance: JSONObject?): Ask {
        val attention = glance?.optJSONArray("attention")
        if (attention != null && attention.length() > 0) {
            val first = attention.optJSONObject(0)
            if (first != null && first.optString("kind") == "agent_question") {
                return Ask(
                    "An agent is waiting on you",
                    first.optString("text"),
                    "estate",
                )
            }
        }

        val steering = Inbox.readObject(ctx, Inbox.STEERING)
        val commitments = steering?.optJSONArray("commitments")
        if (commitments != null && commitments.length() > 0) {
            return Ask(
                "Resolve ${commitments.length()} from yesterday",
                "one tap each · " + stalenessOf(ctx, Inbox.STEERING),
                "resolve",
            )
        }

        val hour = hourOfDay()
        val ritualDone =
            recentRuns(ctx, 1).any { it.optString("kind") == "steering_ritual" }
        if (hour in 5..11 && !ritualDone && steering != null) {
            return Ask(
                "Pick today's intentions",
                "under a minute · " + stalenessOf(ctx, Inbox.STEERING),
                "ritual",
            )
        }

        val queue = steering?.optJSONArray("ready_queue")
        if (queue != null && queue.length() > 0) {
            return Ask("${queue.length()} ready to send", "spend the stack", "ready")
        }

        val check = assembleCheck(ctx)
        if (check.isNotEmpty()) {
            val minutes = (check.sumOf { it.seconds } + 59) / 60
            return Ask(
                "${minutes}-minute check due",
                check.joinToString(" · ") { it.title },
                "instruments",
            )
        }

        return Ask("nothing due", "")
    }

    /** Staleness, always rendered, never hidden. */
    fun stalenessOf(ctx: Context, name: String): String {
        val age = Inbox.ageSeconds(ctx, name)
        return when {
            age < 0 -> "never pushed"
            age < 3600 -> "as of ${age / 60}m ago"
            age < 86400 -> "as of ${age / 3600}h ago"
            else -> "as of ${age / 86400}d ago"
        }
    }

    fun headphonesConnected(ctx: Context): Boolean {
        val am = ctx.getSystemService(AudioManager::class.java) ?: return false
        return am.getDevices(AudioManager.GET_DEVICES_OUTPUTS).any {
            it.type == AudioDeviceInfo.TYPE_WIRED_HEADPHONES ||
                it.type == AudioDeviceInfo.TYPE_WIRED_HEADSET ||
                it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                it.type == AudioDeviceInfo.TYPE_USB_HEADSET
        }
    }

    fun recentRuns(ctx: Context, days: Int): List<JSONObject> =
        Events.recentOfKind(ctx, days, "instrument_run", "steering_ritual")

    private fun hourOfDay(): Int =
        Calendar.getInstance(TimeZone.getTimeZone("UTC")).get(Calendar.HOUR_OF_DAY)
}
