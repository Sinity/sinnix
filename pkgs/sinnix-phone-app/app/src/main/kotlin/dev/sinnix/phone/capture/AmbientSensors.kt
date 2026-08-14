package dev.sinnix.phone.capture

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Handler
import android.os.Looper
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Storage
import kotlin.math.abs
import kotlin.math.roundToLong
import kotlin.math.sqrt

/**
 * Passive context alongside the audio: ambient light and body motion.
 *
 * Light exposure is the reason this exists. It is the best non-invasive
 * predictor of circadian phase, nothing else in the estate can produce it, and
 * it costs the operator nothing — no prompt, no decision, no screen. Motion
 * comes along because the same listener loop already runs and because "was the
 * phone on a desk or in a pocket" is the covariate that makes a lux reading
 * interpretable.
 *
 * Reduced on the phone, scored on prime. Raw sensor streams are tens of samples
 * a second of very little information; what leaves here is one line a minute
 * carrying the statistics that survive aggregation.
 *
 * Attached to the capture service rather than run on its own schedule: that
 * process is already alive continuously with a wakelock held, so this adds a
 * listener rather than a reason to wake up.
 */
class AmbientSensors(context: Context) : SensorEventListener {

    private val ctx: Context = context.applicationContext
    private val sensors: SensorManager? = ctx.getSystemService(SensorManager::class.java)
    private val light: Sensor? = sensors?.getDefaultSensor(Sensor.TYPE_LIGHT)
    private val accelerometer: Sensor? = sensors?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

    private val handler = Handler(Looper.getMainLooper())
    private var listening = false
    private var windowStartedAtMs = 0L

    private var luxSamples = 0
    private var luxSum = 0.0
    private var luxMax = -1f
    private var luxMin = -1f

    private var motionSamples = 0
    private var motionSquares = 0.0
    private var motionMax = 0.0

    fun start() {
        if (sensors == null) return
        Log.i(Storage.TAG, "sensors: light=${light != null} accelerometer=${accelerometer != null}")
        openWindow()
    }

    fun stop() {
        handler.removeCallbacksAndMessages(null)
        closeWindow()
    }

    /** Listen for a slice, then sleep until the next minute. */
    private fun openWindow() {
        val sm = sensors ?: return
        windowStartedAtMs = System.currentTimeMillis()
        light?.let { sm.registerListener(this, it, SAMPLING_PERIOD_US) }
        accelerometer?.let { sm.registerListener(this, it, SAMPLING_PERIOD_US) }
        listening = true
        handler.postDelayed(::closeWindow, SAMPLE_WINDOW_MILLIS)
    }

    private fun closeWindow() {
        if (!listening) return
        sensors?.unregisterListener(this)
        listening = false
        flush(System.currentTimeMillis())
        handler.postDelayed(::openWindow, (WINDOW_MILLIS - SAMPLE_WINDOW_MILLIS).coerceAtLeast(1L))
    }

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_LIGHT -> {
                val lux = event.values[0]
                luxSamples++
                luxSum += lux
                if (luxMax < 0 || lux > luxMax) luxMax = lux
                if (luxMin < 0 || lux < luxMin) luxMin = lux
            }
            Sensor.TYPE_ACCELEROMETER -> {
                // Magnitude minus gravity: what remains is movement,
                // independent of how the phone happens to be lying. Squared
                // here and rooted at flush so the statistic is an RMS rather
                // than a mean of absolutes.
                val magnitude =
                    sqrt(
                        (event.values[0] * event.values[0] +
                            event.values[1] * event.values[1] +
                            event.values[2] * event.values[2])
                            .toDouble()
                    )
                val residual = abs(magnitude - SensorManager.GRAVITY_EARTH)
                motionSamples++
                motionSquares += residual * residual
                if (residual > motionMax) motionMax = residual
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
        // Not recorded: this sensor's accuracy flag says nothing a lux value
        // does not, and a line per transition would be noise in the log.
    }

    /**
     * Close the window and write one record.
     *
     * Silent when nothing was sampled. A minute with no reading is a real
     * observation about the sensor, but writing a row of nulls every minute
     * the phone is idle would bury the ones that carry data.
     */
    private fun flush(now: Long) {
        if (luxSamples > 0 || motionSamples > 0) {
            // Kept in memory as well as written, because an instrument about
            // to start needs its covariates now and the log is a file.
            lastReading =
                Reading(
                    luxMean = if (luxSamples == 0) null else round(luxSum / luxSamples),
                    motionRms =
                        if (motionSamples == 0) null else round(sqrt(motionSquares / motionSamples)),
                )
            Events.record(
                ctx,
                "ambient_context",
                "window_seconds", ((now - windowStartedAtMs) / 1000L).coerceAtLeast(1L),
                "lux_mean", if (luxSamples == 0) null else round(luxSum / luxSamples),
                "lux_min", if (luxSamples == 0) null else round(luxMin.toDouble()),
                "lux_max", if (luxSamples == 0) null else round(luxMax.toDouble()),
                "lux_samples", luxSamples,
                "motion_rms",
                if (motionSamples == 0) null else round(sqrt(motionSquares / motionSamples)),
                "motion_max", if (motionSamples == 0) null else round(motionMax),
                "motion_samples", motionSamples,
            )
        }
        windowStartedAtMs = now
        luxSamples = 0
        luxSum = 0.0
        luxMax = -1f
        luxMin = -1f
        motionSamples = 0
        motionSquares = 0.0
        motionMax = 0.0
    }

    data class Reading(val luxMean: Double?, val motionRms: Double?)

    private var lastReading: Reading?
        get() = latest
        set(value) {
            latest = value
        }

    companion object {
        /**
         * The most recent reduced window, for instrument covariates.
         *
         * Process-wide rather than per-instance because the reader is an
         * instrument in another Activity and the writer is the capture service:
         * both live in this one process, and threading a reference between them
         * would be a binder for a value that is two doubles wide.
         */
        @Volatile var latest: Reading? = null

        /** One record a minute: fine enough for circadian work, coarse enough to ignore. */
        private const val WINDOW_MILLIS = 60_000L

        /**
         * How much of each minute the sensors are actually listened to.
         *
         * Duty-cycled rather than rate-limited because neither lever the API
         * offers works on this device: the sampling period is only a hint and
         * this platform answers every request with 50 Hz, and the BMI220
         * reports no batching FIFO, so a report-latency window changes nothing.
         * Measured: 3000 accelerometer callbacks a minute either way.
         *
         * Ten seconds is plenty to characterise a minute of stillness or
         * motion, and it cuts the callbacks by six. What is lost is a movement
         * that both starts and ends inside the unsampled fifty seconds; what is
         * gained is a lane that can run all day.
         */
        private const val SAMPLE_WINDOW_MILLIS = 10_000L

        /** Only a hint on this platform, kept because it costs nothing where it is honoured. */
        private const val SAMPLING_PERIOD_US = 200_000

        /** Two decimals: lux and m/s² are not meaningful past that, and humans read the log too. */
        private fun round(v: Double): Double = (v * 100.0).roundToLong() / 100.0
    }
}
