package dev.sinnix.phone.core

import android.content.Context
import android.os.Build
import android.util.Log
import java.io.File
import org.json.JSONObject

/**
 * The apparatus a measurement was taken on.
 *
 * A reaction time is a property of a person *and* a device: the panel's
 * refresh rate, the digitizer's sampling, the OS build's input path. Comparing
 * results across a changed apparatus measures the apparatus. So every result
 * carries an epoch id, and results are only comparable within one.
 *
 * An epoch is [Build.FINGERPRINT] plus the measured touch-latency offset. When
 * the fingerprint changes — an OS update, a different device — the epoch is
 * invalidated and the offset must be measured again; the app says so rather
 * than silently carrying the old number forward.
 *
 * This is deliberately NOT a device profile. An earlier design carried a
 * per-sample-rate verdict table here, on the theory that a rate could be
 * accepted by the recorder and return silence. That was false, and a record
 * shaped around a false theory is worse than no record.
 */
data class Epoch(
    val id: String,
    val fingerprint: String,
    val openedAt: String,
    val touchOffsetMs: Int,
    val touchOffsetSdMs: Int,
) {

    val isCalibrated: Boolean get() = touchOffsetMs != UNCALIBRATED

    /** True when this record describes a different apparatus than the one running. */
    val invalidated: Boolean get() = Build.FINGERPRINT != fingerprint

    /** Record a completed touch-latency calibration against this epoch. */
    fun withTouchOffset(ctx: Context, meanMs: Int, sdMs: Int): Epoch {
        val next = copy(touchOffsetMs = meanMs, touchOffsetSdMs = sdMs)
        next.write(ctx)
        Events.record(ctx, "epoch_calibrated", "epoch", id, "touch_offset_ms", meanMs, "sd_ms", sdMs)
        return next
    }

    private fun write(ctx: Context) {
        val f = file(ctx) ?: return
        val o = JSONObject()
        o.put("schema", SCHEMA)
        o.put("epoch", id)
        o.put("fingerprint", fingerprint)
        o.put("opened_at", openedAt)
        o.put("touch_offset_ms", touchOffsetMs)
        o.put("touch_offset_sd_ms", touchOffsetSdMs)
        Storage.writeAtomically(f, o.toString(2).toByteArray(Charsets.UTF_8))
    }

    companion object {
        private const val FILE_NAME = "epoch.json"
        private const val SCHEMA = "sinnix.phone.epoch/1"

        /** Touch offset is unknown until the tick-and-tap calibration has run. */
        const val UNCALIBRATED = -1

        private fun file(ctx: Context): File? =
            Storage.estateDir(ctx, null)?.let { File(it, FILE_NAME) }

        fun read(ctx: Context): Epoch? {
            val text = Storage.readText(file(ctx)) ?: return null
            return try {
                val o = JSONObject(text)
                Epoch(
                    id = o.optString("epoch", "e1"),
                    fingerprint = o.optString("fingerprint", ""),
                    openedAt = o.optString("opened_at", ""),
                    touchOffsetMs = o.optInt("touch_offset_ms", UNCALIBRATED),
                    touchOffsetSdMs = o.optInt("touch_offset_sd_ms", UNCALIBRATED),
                )
            } catch (e: Exception) {
                Log.w(Storage.TAG, "$FILE_NAME is not readable JSON", e)
                null
            }
        }

        /**
         * The current epoch, opening a new one if the apparatus changed.
         *
         * Opening is cheap and always safe: it records what the device is now.
         * What it deliberately does not do is inherit the previous offset,
         * because the offset is the part a firmware change is most likely to
         * move.
         */
        fun current(ctx: Context): Epoch {
            val stored = read(ctx)
            if (stored != null && !stored.invalidated) return stored

            var generation = 1
            if (stored != null) {
                // Epoch ids are e1, e2, … — an ordinal, not a hash, because
                // they are printed on results and a human has to be able to
                // say "that was e3".
                generation = stored.id.drop(1).toIntOrNull()?.plus(1) ?: 2
                Events.record(
                    ctx,
                    "epoch_invalidated",
                    "from", stored.id,
                    "was_fingerprint", stored.fingerprint,
                    "now_fingerprint", Build.FINGERPRINT,
                )
            }
            val opened =
                Epoch(
                    id = "e$generation",
                    fingerprint = Build.FINGERPRINT,
                    openedAt = Stamps.iso(System.currentTimeMillis()),
                    touchOffsetMs = UNCALIBRATED,
                    touchOffsetSdMs = UNCALIBRATED,
                )
            opened.write(ctx)
            Events.record(ctx, "epoch_opened", "epoch", opened.id, "fingerprint", opened.fingerprint)
            return opened
        }
    }
}
