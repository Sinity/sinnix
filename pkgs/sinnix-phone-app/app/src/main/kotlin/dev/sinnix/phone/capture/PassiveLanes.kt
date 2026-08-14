package dev.sinnix.phone.capture

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.os.PowerManager
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import kotlin.math.roundToInt

/**
 * Two lanes that cost nothing because something else is already awake.
 *
 * Both ride AmbientService's heartbeat rather than scheduling themselves. A
 * battery reading is one broadcast lookup and a sleep estimate is arithmetic
 * over readings already in hand, so giving either its own alarm would spend a
 * wakeup to learn something the process could have noticed for free.
 *
 * **Power** — battery level, charging state, temperature and thermal headroom
 * as events rather than only as fields in status.json. status.json is a
 * snapshot the desktop polls; it answers "what is the battery now" and cannot
 * answer "what did the battery do overnight", which is the question that makes
 * a discharge curve joinable to everything else the phone recorded.
 *
 * **Sleep** — inferred from the phone's own signals: sustained stillness, dark,
 * screen off, and usually charging. Deliberately an estimate independent of
 * any wearable, because two independent estimates that disagree is a finding
 * and one estimate is an assumption. It is not trying to beat a band at sleep
 * staging; it is answering "was the phone's owner plausibly asleep" so a
 * morning PVT knows what it is a morning after.
 */
class PassiveLanes(context: Context) {

    private val ctx: Context = context.applicationContext

    private var lastPowerAtMs = 0L
    private var lastLevel = -1
    private var lastCharging: Boolean? = null

    private var stillSince = 0L
    private var asleep = false
    private var sleepStartedAt = 0L

    /** Called from the capture heartbeat, every 20 s. */
    fun tick() {
        val now = System.currentTimeMillis()
        if (Prefs.powerLane(ctx)) power(now)
        if (Prefs.sleepDetect(ctx)) sleep(now)
    }

    private fun power(now: Long) {
        val battery =
            try {
                ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            } catch (e: Exception) {
                null
            } ?: return

        val level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        val percent = if (level < 0 || scale <= 0) -1 else (level * 100f / scale).roundToInt()
        val status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        val charging =
            status == BatteryManager.BATTERY_STATUS_CHARGING ||
                status == BatteryManager.BATTERY_STATUS_FULL

        // Written on change or on a slow heartbeat, not every 20 s. A row per
        // heartbeat would be 4,320 rows a day saying the same thing, and the
        // shape of a discharge curve survives a one-percent resolution.
        val changed = percent != lastLevel || charging != lastCharging
        if (!changed && now - lastPowerAtMs < POWER_FLOOR_MILLIS) return

        Events.record(
            ctx,
            "power",
            "percent", percent,
            "charging", charging,
            "temperature_c", battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, -1) / 10.0,
            "voltage_mv", battery.getIntExtra(BatteryManager.EXTRA_VOLTAGE, -1),
            "thermal_headroom", thermalHeadroom(),
        )
        lastLevel = percent
        lastCharging = charging
        lastPowerAtMs = now
    }

    private fun thermalHeadroom(): Double? =
        try {
            ctx.getSystemService(PowerManager::class.java)
                ?.getThermalHeadroom(60)
                ?.takeIf { !it.isNaN() }
                ?.toDouble()
        } catch (e: Exception) {
            // Not every device implements it, and an absent reading is honest.
            null
        }

    private fun sleep(now: Long) {
        val sensors = AmbientSensors.latest
        val motion = sensors?.motionRms
        val lux = sensors?.luxMean
        val interactive =
            try {
                ctx.getSystemService(PowerManager::class.java)?.isInteractive == true
            } catch (e: Exception) {
                false
            }

        // Absent sensor readings mean "unknown", not "still and dark". A lane
        // that treated a missing accelerometer as stillness would report the
        // operator asleep whenever the sensor lane was broken, which is the
        // failure this estate keeps finding in other forms.
        if (motion == null || lux == null) {
            stillSince = 0
            return
        }

        val quiet = motion < STILL_MOTION_RMS && lux < DARK_LUX && !interactive
        if (quiet) {
            if (stillSince == 0L) stillSince = now
            if (!asleep && now - stillSince >= SLEEP_ONSET_MILLIS) {
                asleep = true
                sleepStartedAt = stillSince
                Events.record(
                    ctx,
                    "sleep_estimate",
                    "state", "asleep",
                    "since", dev.sinnix.phone.core.Stamps.iso(stillSince),
                    "motion_rms", motion,
                    "lux_mean", lux,
                )
            }
        } else {
            stillSince = 0
            if (asleep) {
                asleep = false
                Events.record(
                    ctx,
                    "sleep_estimate",
                    "state", "awake",
                    "slept_minutes", (now - sleepStartedAt) / 60_000L,
                    "motion_rms", motion,
                    "lux_mean", lux,
                )
            }
        }
    }

    companion object {
        /** Below this the phone is on a surface, not in a hand or a pocket. */
        private const val STILL_MOTION_RMS = 0.06

        /** A lit room reads far higher; a phone face-down reads near zero. */
        private const val DARK_LUX = 3.0

        /** Twenty minutes of stillness, dark and screen-off before believing it.
         *  Shorter caught the operator reading motionless in a dark room. */
        private const val SLEEP_ONSET_MILLIS = 20 * 60_000L

        /** Even unchanged, write a power row this often so a flat night is
         *  evidence of a flat night rather than of a lane that stopped. */
        private const val POWER_FLOOR_MILLIS = 15 * 60_000L
    }
}
