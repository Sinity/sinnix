package dev.sinnix.phone.instruments

import android.content.Context
import android.os.PowerManager
import dev.sinnix.phone.capture.AmbientSensors
import dev.sinnix.phone.core.Epoch
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Stamps
import java.util.Calendar
import java.util.TimeZone
import org.json.JSONArray
import org.json.JSONObject

/**
 * Writing a result down, with everything needed to interpret it later.
 *
 * Covariates are attached automatically and are offered as explanation, never
 * as excuse: "21:04 · dim · still" is what turns a slow reaction time from a
 * verdict about the person into an observation about a moment. They are
 * recorded even when a condition was unmet, because annotating a trial beats
 * pretending the apparatus was calibrated.
 *
 * The epoch id travels with every record. Comparisons across an epoch boundary
 * are suspended rather than adjusted — a firmware change moves the input path,
 * and a correction factor invented after the fact would be worse than an
 * honest gap in the series.
 */
object RunRecord {

    fun write(
        ctx: Context,
        instrument: Instrument,
        startedAtMs: Long,
        fields: Map<String, Any?>,
        preflightUnmet: List<String> = emptyList(),
    ) {
        val epoch = Epoch.current(ctx)
        val o = JSONObject()
        o.put("kind", "instrument_run")
        o.put("instrument", instrument.id)
        o.put("engine", instrument.engine.name.lowercase())
        o.put("epoch", epoch.id)
        o.put("touch_offset_ms", epoch.touchOffsetMs)
        o.put("started_at", Stamps.iso(startedAtMs))
        o.put("seconds", ((System.currentTimeMillis() - startedAtMs) / 1000L).coerceAtLeast(0L))
        o.put("scored_on_device", instrument.scoredOnDevice)
        o.put("hour_of_day", hourOfDay())
        o.put("energy_state", dev.sinnix.phone.core.Prefs.energyState(ctx))
        o.put("screen_interactive", screenInteractive(ctx))
        AmbientSensors.latest?.let {
            o.put("lux_mean", it.luxMean ?: JSONObject.NULL)
            o.put("motion_rms", it.motionRms ?: JSONObject.NULL)
        }
        o.put("headphones", OfferPolicy.headphonesConnected(ctx))
        if (preflightUnmet.isNotEmpty()) {
            o.put("preflight_unmet", JSONArray(preflightUnmet))
        }
        fields.forEach { (k, v) ->
            o.put(
                k,
                when (v) {
                    null -> JSONObject.NULL
                    is List<*> -> JSONArray(v)
                    else -> v
                },
            )
        }
        Events.append(ctx, o)
    }

    /** Past runs of one instrument, oldest first, for the result sparkline. */
    fun history(ctx: Context, instrumentId: String, metric: String, days: Int = 60): List<Double> =
        Events.recentOfKind(ctx, days, "instrument_run")
            .filter { it.optString("instrument") == instrumentId && it.has(metric) }
            .mapNotNull { it.optDouble(metric).takeIf { d -> !d.isNaN() } }

    /**
     * One plain sentence about where a value sits in the operator's own spread.
     *
     * No streaks, no goals, no badges. Gamification converts a measurement into
     * self-judgement, which is precisely what makes this category of tool
     * aversive to the person it is built for.
     */
    fun context(history: List<Double>, value: Double, lowerIsBetter: Boolean): String {
        if (history.size < 5) return "too early to compare — ${history.size} runs so far"
        val sorted = history.sorted()
        val q1 = sorted[(sorted.size * 0.25).toInt()]
        val q3 = sorted[(sorted.size * 0.75).toInt()]
        val recent = history.takeLast(5)
        val recentMean = recent.average()
        return when {
            value in q1..q3 -> "within your usual range"
            (value < q1) == lowerIsBetter -> "better than your usual range"
            else ->
                if ((value < recentMean) == lowerIsBetter) "outside your usual range, but not your last five"
                else "outside your usual range"
        }
    }

    private fun hourOfDay(): Int =
        Calendar.getInstance(TimeZone.getTimeZone("UTC")).get(Calendar.HOUR_OF_DAY)

    private fun screenInteractive(ctx: Context): Boolean =
        ctx.getSystemService(PowerManager::class.java)?.isInteractive == true
}
