package dev.sinnix.phone.capture

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import dev.sinnix.phone.core.BuildId
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.io.File
import org.json.JSONObject

/**
 * Desktop-observable liveness.
 *
 * Writes `status.json` next to the chunks. That location is deliberate: it
 * rides the same drain path the audio already uses, so the desktop can answer
 * "is capture alive and producing?" over the existing surface with no extra
 * listening port on a phone that roams networks.
 *
 * The distinction that matters is alive-and-producing versus merely installed.
 * Both the closed-chunk history and the growth of the file currently open are
 * reported, because a recorder that is running while the platform feeds it
 * silence looks identical to a healthy one from the outside.
 *
 * Every key here is a contract with `sinnix-phone app-status` and `app-soak`.
 * Renaming one is a desktop-side breakage, not a refactor.
 */
class Status {

    private var ctx: Context? = null

    private var serviceStartedAtMs = 0L
    private var currentChunk: String? = null
    private var currentChunkStartedAtMs = 0L
    private var currentChunkBytes = 0L
    private var samplingRate = 0

    private var lastChunk: String? = null
    private var lastChunkSeconds = 0L
    private var lastChunkBytes = 0L
    private var lastChunkClosedAtMs = 0L
    private var lastChunkPeakAmplitude = 0

    private var chunksClosedCount = 0
    private var failures = 0
    private var lastError: String? = null
    private var lastErrorAtMs = 0L

    private var lastGrowthAtMs = 0L
    private var lastObservedBytes = -1L
    private var recording = false

    private var lastAmplitude = -1
    private var chunkPeakAmplitude = 0
    private var silentSamples = 0

    @Synchronized
    fun attach(context: Context) {
        ctx = context.applicationContext
    }

    @Synchronized
    fun serviceStarted() {
        serviceStartedAtMs = System.currentTimeMillis()
        write()
    }

    @Synchronized
    fun serviceStopped() {
        recording = false
        currentChunk = null
        write()
    }

    @Synchronized
    fun chunkOpened(part: File, startedAtMs: Long, rate: Int) {
        currentChunk = part.name
        currentChunkStartedAtMs = startedAtMs
        currentChunkBytes = 0
        samplingRate = rate
        recording = true
        lastObservedBytes = -1
        lastGrowthAtMs = startedAtMs
        chunkPeakAmplitude = 0
        silentSamples = 0
        lastAmplitude = -1
        write()
    }

    /**
     * Peak amplitude seen during the open chunk.
     *
     * Read before [chunkClosed], which rolls it into the last-chunk fields and
     * starts the next one over. Zero across a whole chunk means the microphone
     * produced no sample at all — the failure that looks exactly like success
     * from the file's side.
     */
    @Synchronized fun chunkPeak(): Int = chunkPeakAmplitude

    @Synchronized
    fun chunkClosed(file: File, startedAtMs: Long, closedAtMs: Long) {
        lastChunk = file.name
        lastChunkBytes = file.length()
        lastChunkSeconds = ((closedAtMs - startedAtMs) / 1000L).coerceAtLeast(0L)
        lastChunkClosedAtMs = closedAtMs
        lastChunkPeakAmplitude = chunkPeakAmplitude
        chunksClosedCount++
        recording = false
        currentChunk = null
        write()
    }

    @Synchronized
    fun heartbeat(currentBytes: Long, elapsedSeconds: Long, amplitude: Int) {
        currentChunkBytes = currentBytes
        if (currentBytes > lastObservedBytes) {
            lastObservedBytes = currentBytes
            lastGrowthAtMs = System.currentTimeMillis()
        }
        if (amplitude >= 0) {
            lastAmplitude = amplitude
            if (amplitude > chunkPeakAmplitude) chunkPeakAmplitude = amplitude
            // Exactly zero, not "low". A working microphone reports its own
            // noise floor even in a silent room; a run of exact zeroes is the
            // platform substituting silence for audio it decided not to give us.
            if (amplitude == 0) silentSamples++ else silentSamples = 0
        }
        write()
    }

    @Synchronized
    fun recordFailure(detail: String) {
        failures++
        lastError = detail
        lastErrorAtMs = System.currentTimeMillis()
        recording = false
        write()
    }

    /** True when a chunk is nominally open but its file has stopped growing. */
    @Synchronized
    fun stalled(): Boolean {
        if (!recording || lastGrowthAtMs == 0L) return false
        return System.currentTimeMillis() - lastGrowthAtMs > STALL_MILLIS
    }

    /** True when the recorder is nominally running but the microphone reads as silence. */
    @Synchronized fun muted(): Boolean = recording && silentSamples >= MUTED_SAMPLES

    @Synchronized fun chunksClosed(): Int = chunksClosedCount

    @Synchronized
    fun lastErrorShort(): String {
        val e = lastError ?: return "idle"
        return if (e.length > 80) e.substring(0, 80) else e
    }

    private fun write() {
        val c = ctx ?: return
        val dir = Storage.chunkDir(c) ?: return
        val o = JSONObject()
        try {
            val now = System.currentTimeMillis()
            o.put("schema", SCHEMA)
            o.put("app_version", BuildId.VERSION)
            o.put("package", c.packageName)
            o.put("updated_at", Stamps.iso(now))
            o.put("service_running", AmbientService.running)
            o.put("recording", recording)
            o.put("chunk_dir", dir.absolutePath)
            o.put("chunk_dir_is_shared", dir.absolutePath == Storage.SHARED_DIR)
            o.put("all_files_access", Storage.haveAllFilesAccess())
            o.put("chunk_seconds_target", AmbientService.CHUNK_MILLIS / 1000L)
            o.put("sampling_rate", samplingRate)
            o.put("service_started_at", isoOrNull(serviceStartedAtMs))
            o.put(
                "uptime_seconds",
                if (serviceStartedAtMs == 0L) 0L else (now - serviceStartedAtMs) / 1000L,
            )
            o.put("current_chunk", currentChunk ?: JSONObject.NULL)
            o.put("current_chunk_started_at", isoOrNull(currentChunkStartedAtMs))
            o.put("current_chunk_bytes", currentChunkBytes)
            o.put(
                "current_chunk_elapsed_seconds",
                if (currentChunkStartedAtMs == 0L || !recording) 0L
                else (now - currentChunkStartedAtMs) / 1000L,
            )
            o.put("current_chunk_peak_amplitude", chunkPeakAmplitude)
            o.put("last_amplitude", lastAmplitude)
            o.put("silent_samples", silentSamples)
            o.put("muted", recording && silentSamples >= MUTED_SAMPLES)
            o.put("last_chunk", lastChunk ?: JSONObject.NULL)
            o.put("last_chunk_seconds", lastChunkSeconds)
            o.put("last_chunk_bytes", lastChunkBytes)
            o.put("last_chunk_closed_at", isoOrNull(lastChunkClosedAtMs))
            o.put("last_chunk_peak_amplitude", lastChunkPeakAmplitude)
            o.put("chunks_closed", chunksClosedCount)
            o.put("failures", failures)
            o.put("last_error", lastError ?: JSONObject.NULL)
            o.put("last_error_at", isoOrNull(lastErrorAtMs))
            o.put("screen_interactive", screenInteractive(c))
            o.put("battery_percent", batteryPercent(c))
            o.put("boot_at", Stamps.iso(now - SystemClock.elapsedRealtime()))
        } catch (e: Exception) {
            Log.w(Storage.TAG, "status assembly failed", e)
            return
        }
        // Rename-into-place: the desktop polls this file, and a torn read of a
        // half-written JSON document would look like a crashed capture.
        Storage.writeAtomically(
            File(dir, FILE_NAME),
            (o.toString(2) + "\n").toByteArray(Charsets.UTF_8),
        )
    }

    private fun screenInteractive(c: Context): Boolean =
        try {
            c.getSystemService(PowerManager::class.java)?.isInteractive == true
        } catch (e: Exception) {
            false
        }

    private fun batteryPercent(c: Context): Int =
        try {
            val battery = c.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
            val level = battery?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
            val scale = battery?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
            if (level < 0 || scale <= 0) -1 else Math.round(level * 100f / scale)
        } catch (e: Exception) {
            -1
        }

    private fun isoOrNull(ms: Long): Any = if (ms == 0L) JSONObject.NULL else Stamps.iso(ms)

    companion object {
        private const val FILE_NAME = "status.json"
        private const val SCHEMA = "sinnix.phone.ambient/1"

        /** A chunk file that has not grown in this long is not really recording. */
        private const val STALL_MILLIS = 90_000L

        /**
         * Consecutive zero-amplitude heartbeats before the microphone counts
         * as muted. Four samples is 80s at the current cadence — long enough
         * that a momentary handover between audio clients does not trip it,
         * short enough that a chunk is never mostly silence before anyone
         * notices.
         */
        private const val MUTED_SAMPLES = 4

        /** Read `status.json` from wherever chunks are currently written. */
        fun read(ctx: Context): JSONObject? {
            val dir = Storage.chunkDir(ctx) ?: return null
            val text = Storage.readText(File(dir, FILE_NAME)) ?: return null
            return try {
                JSONObject(text)
            } catch (e: Exception) {
                null
            }
        }
    }
}
