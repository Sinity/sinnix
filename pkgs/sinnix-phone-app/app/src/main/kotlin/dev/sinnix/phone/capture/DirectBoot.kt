package dev.sinnix.phone.capture

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.io.File

/**
 * Capture between power-on and first unlock.
 *
 * The limit this closes, stated exactly: this device uses file-based
 * encryption with a screen lock, so `/sdcard` is not mounted and
 * `BOOT_COMPLETED` is not delivered until the operator first unlocks. A phone
 * rebooted at 3am and left on the nightstand until morning recorded nothing —
 * and nothing said so, because from the outside a phone that is off and a
 * phone that is on but locked look identical in the lake.
 *
 * What runs before unlock is **device-protected storage**: a small area
 * available from `LOCKED_BOOT_COMPLETED`, encrypted with a device key rather
 * than a credential key. This service records there and migrates on unlock.
 *
 * ### What this does not fix, said plainly
 *
 * - **It is a buffer, not the archive.** Device-protected storage is small and
 *   shares the data partition, so the buffer is capped and the oldest chunk is
 *   dropped when it fills. A phone left locked for a week keeps the last hours,
 *   not the week.
 * - **MIUI can still refuse.** If the vendor does not deliver
 *   `LOCKED_BOOT_COMPLETED` to a background app, nothing here runs. That is the
 *   same autostart question the grants screen already renders as unverifiable,
 *   and this service does not make it verifiable — it only records a `boot`
 *   event when it does run, so the absence is visible.
 * - **The microphone may not be available at all.** Some devices withhold it
 *   before unlock. That is a per-device fact, so the service records what it
 *   got rather than assuming: a locked-boot window with zero chunks and a
 *   recorded failure is a much better artefact than silence.
 */
class LockedBootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent?) {
        val action = intent?.action
        Log.i(Storage.TAG, "locked boot receiver: $action")
        when (action) {
            Intent.ACTION_LOCKED_BOOT_COMPLETED -> {
                // Recorded in device-protected storage, since the estate's
                // event log lives on /sdcard and is not mounted yet.
                DirectBoot.note(ctx, "locked_boot")
                if (DirectBoot.enabled(ctx)) DirectBootService.start(ctx)
            }
            Intent.ACTION_USER_UNLOCKED -> {
                DirectBoot.note(ctx, "user_unlocked")
                DirectBootService.stop(ctx)
                DirectBoot.migrate(ctx)
            }
        }
    }
}

object DirectBoot {

    /** Chunks recorded before unlock, and the pre-unlock note log. */
    fun bufferDir(ctx: Context): File? {
        val protected =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                ctx.createDeviceProtectedStorageContext()
            } else {
                return null
            }
        val dir = File(protected.filesDir, "locked-boot")
        return if (dir.isDirectory || dir.mkdirs()) dir else null
    }

    fun enabled(ctx: Context): Boolean {
        // The capture preference lives in credential-protected storage and is
        // unreadable before unlock, so the direct-boot decision is mirrored
        // into device-protected storage whenever capture starts normally. An
        // absent mirror means "never ran while unlocked", and the safe reading
        // of that is to record: a phone whose owner enabled capture and then
        // rebooted should not go quiet because the mirror was not written yet.
        val dir = bufferDir(ctx) ?: return false
        val flag = File(dir, "enabled")
        return !flag.isFile || flag.readText().trim() != "false"
    }

    /** Mirror the capture preference where a locked boot can read it. */
    fun mirror(ctx: Context, enabled: Boolean) {
        val dir = bufferDir(ctx) ?: return
        try {
            File(dir, "enabled").writeText(if (enabled) "true" else "false")
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not mirror the capture flag", e)
        }
    }

    fun note(ctx: Context, what: String) {
        val dir = bufferDir(ctx) ?: return
        try {
            File(dir, "notes.jsonl").appendText(
                """{"kind":"$what","ts":"${Stamps.iso(System.currentTimeMillis())}"}""" + "\n"
            )
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not note $what", e)
        }
    }

    /**
     * Move the locked-boot buffer into the real lane, once /sdcard exists.
     *
     * Chunks are renamed into the ordinary chunk directory under the ordinary
     * naming convention, so the drain, the audit and the ribbon treat them as
     * what they are: audio from that hour. Nothing downstream needs to know
     * they took a different route to get there.
     */
    fun migrate(ctx: Context) {
        val buffer = bufferDir(ctx) ?: return
        val dest = Storage.chunkDir(ctx) ?: return
        var moved = 0
        buffer.listFiles { _, name -> name.endsWith(".m4a") }?.forEach { chunk ->
            val target = File(dest, chunk.name)
            if (chunk.renameTo(target) || copyThenDelete(chunk, target)) moved++
        }

        // The pre-unlock notes become ordinary events now that the log is
        // reachable, so a locked boot appears in the same timeline as
        // everything else.
        val notes = File(buffer, "notes.jsonl")
        if (notes.isFile) {
            notes.readLines().forEach { line ->
                try {
                    val o = org.json.JSONObject(line)
                    Events.record(
                        ctx,
                        "boot",
                        "action", o.optString("kind"),
                        "ts", o.optString("ts"),
                        "before_unlock", true,
                    )
                } catch (ignored: Exception) {
                    // a truncated final line is the normal shape of a log whose
                    // writer was killed; the rest still counts
                }
            }
            notes.delete()
        }
        if (moved > 0) {
            Events.record(ctx, "direct_boot_migrated", "chunks", moved)
            Log.i(Storage.TAG, "migrated $moved locked-boot chunk(s)")
        }
    }

    private fun copyThenDelete(from: File, to: File): Boolean =
        try {
            from.copyTo(to, overwrite = true)
            from.delete()
            true
        } catch (e: Exception) {
            // Cross-filesystem rename fails between the data partition and
            // /sdcard on some devices; a copy is the fallback, and a failed
            // copy leaves the chunk in the buffer for the next attempt rather
            // than losing it.
            Log.w(Storage.TAG, "could not migrate ${from.name}", e)
            false
        }

    /** Oldest-first eviction, so a long lock keeps the most recent audio. */
    fun trim(ctx: Context) {
        val dir = bufferDir(ctx) ?: return
        val chunks = dir.listFiles { _, n -> n.endsWith(".m4a") }?.sortedBy { it.name } ?: return
        var total = chunks.sumOf { it.length() }
        for (chunk in chunks) {
            if (total <= BUFFER_BYTES) break
            total -= chunk.length()
            chunk.delete()
        }
    }

    /** ~30 chunks at the archive grade. Enough for a night, not for a week. */
    private const val BUFFER_BYTES = 120L * 1024 * 1024
}

/**
 * The recorder that runs before unlock.
 *
 * Deliberately simpler than AmbientService: no rotation ladder, no status
 * file, no sensor lane. Every one of those reads or writes something on
 * /sdcard or in credential-protected preferences, none of which exist yet.
 * This does one thing — put audio somewhere it will survive — and hands over
 * to the real service the moment there is a real filesystem.
 */
class DirectBootService : android.app.Service() {

    private var recorder: MediaRecorder? = null
    private var current: File? = null
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())

    override fun onBind(intent: Intent?): android.os.IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            close()
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(
            NOTIFICATION_ID,
            android.app.Notification.Builder(this, dev.sinnix.phone.core.Notifications.CHANNEL_STATUS)
                .setContentTitle("Sinnix capture (locked)")
                .setContentText("recording until unlock")
                .setSmallIcon(dev.sinnix.phone.R.drawable.ic_capture)
                .setOngoing(true)
                .build(),
        )
        rotate()
        return START_STICKY
    }

    private fun rotate() {
        close()
        val dir = DirectBoot.bufferDir(this)
        if (dir == null) {
            stopSelf()
            return
        }
        DirectBoot.trim(this)
        val part = File(dir, "ambient-${Stamps.compact(System.currentTimeMillis())}.m4a")
        val r =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(this)
            else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioChannels(1)
        r.setAudioSamplingRate(48_000)
        r.setAudioEncodingBitRate(96_000)
        r.setOutputFile(part.absolutePath)
        try {
            r.prepare()
            r.start()
            recorder = r
            current = part
        } catch (e: Exception) {
            // The microphone may simply not be available before unlock on this
            // device. Recorded rather than retried forever: a locked-boot
            // window with a named failure is evidence, and a silent retry loop
            // would only be a battery drain that looked like capture.
            Log.w(Storage.TAG, "locked-boot recorder failed", e)
            DirectBoot.note(this, "locked_boot_mic_unavailable")
            part.delete()
            stopSelf()
            return
        }
        handler.postDelayed(::rotate, AmbientService.CHUNK_MILLIS)
    }

    private fun close() {
        val r = recorder ?: return
        recorder = null
        try {
            r.stop()
        } catch (ignored: Exception) {
            current?.delete()
        } finally {
            try {
                r.release()
            } catch (ignored: Exception) {
                // a released recorder is the desired end state either way
            }
        }
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        close()
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "dev.sinnix.phone.DIRECT_BOOT_STOP"
        private const val NOTIFICATION_ID = 4715

        fun start(ctx: Context) {
            try {
                ctx.startForegroundService(Intent(ctx, DirectBootService::class.java))
            } catch (e: Exception) {
                Log.w(Storage.TAG, "could not start the locked-boot recorder", e)
            }
        }

        fun stop(ctx: Context) {
            ctx.startService(
                Intent(ctx, DirectBootService::class.java).setAction(ACTION_STOP)
            )
        }
    }
}
