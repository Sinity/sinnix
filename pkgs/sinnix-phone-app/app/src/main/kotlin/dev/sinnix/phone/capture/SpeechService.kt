package dev.sinnix.phone.capture

import android.app.Notification
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.IBinder
import android.os.PowerManager
import android.util.Base64
import android.util.Log
import dev.sinnix.phone.R
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Notifications
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import dev.sinnix.phone.sync.Outbox
import java.io.File
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import org.json.JSONObject

/**
 * The phone as a network microphone.
 *
 * This is the lane sinnix-uyvt.4 asked for and prime's receiver has been
 * waiting on since it was written: the phone decides what is speech and
 * streams only that, so leaving the desk does not mean leaving the estate's
 * reach.
 *
 * **No wifi gate and no charging gate**, and both omissions are deliberate.
 * The bulk archive drain is gated because it moves gigabytes of mostly-silence
 * and has no deadline; an utterance is kilobytes and its entire value is being
 * timely. A lane that only worked on home wifi while plugged in would work
 * precisely when the operator is already at the desk with a keyboard — that
 * is, never when it matters.
 *
 * It runs alongside AmbientService rather than replacing it. Two recorders on
 * this device coexist on separate input ports with no loss (measured
 * 2026-08-13), and they answer different questions: the ambient lane is an
 * archive of the room at archive grade, this one is 16 kHz mono because that
 * is what a recogniser wants and anything more is bytes on a wire for nothing.
 *
 * When the receiver does not answer the utterance goes to the outbox, like
 * every other verb in this app. The lane degrades to drain cadence rather than
 * dropping what was said.
 */
class SpeechService : Service() {

    private val running = AtomicBoolean(false)
    private var worker: Thread? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP || !Prefs.speechLane(this)) {
            stopSelf()
            return START_NOT_STICKY
        }
        if (running.getAndSet(true)) return START_STICKY

        // Microphone type, like the ambient service: without it the platform
        // silences the recorder the moment the screen goes off, which for a
        // lane whose whole purpose is hands-off listening would mean it worked
        // only while being watched.
        startForeground(NOTIFICATION_ID, notification("listening"))
        acquireWakeLock()
        Events.record(this, "speech_lane", "state", "started")

        worker = thread(name = "speech-vad", isDaemon = true) { loop() }
        return START_STICKY
    }

    override fun onDestroy() {
        running.set(false)
        worker?.join(2_000)
        wakeLock?.takeIf { it.isHeld }?.release()
        Events.record(this, "speech_lane", "state", "stopped")
        super.onDestroy()
    }

    private fun acquireWakeLock() {
        val pm = getSystemService(PowerManager::class.java)
        wakeLock =
            pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "sinnix:speech")?.apply {
                setReferenceCounted(false)
                acquire()
            }
    }

    /**
     * Read, gate, segment, send.
     *
     * The state machine is the whole service. Silero says how speech-like each
     * 32 ms window is; this turns a stream of those into utterances, with two
     * pieces of hysteresis that matter more than the threshold does:
     *
     * - a **pre-roll**, because a detector fires after onset and an utterance
     *   clipped at the front loses the word that decides what it meant;
     * - a **hangover**, because the pause inside a sentence is longer than the
     *   threshold and without it every clause ships as its own utterance.
     */
    @Suppress("MissingPermission") // RECORD_AUDIO is checked before the lane can be enabled
    private fun loop() {
        val minBuffer =
            AudioRecord.getMinBufferSize(
                SileroVad.SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
            )
        val recorder =
            try {
                AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    SileroVad.SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    maxOf(minBuffer, SileroVad.WINDOW * 16),
                )
            } catch (e: Exception) {
                Log.w(Storage.TAG, "speech lane could not open the microphone", e)
                Events.record(this, "speech_lane", "state", "failed", "detail", e.message)
                stopSelf()
                return
            }

        val vad =
            try {
                SileroVad(this)
            } catch (e: Exception) {
                Log.w(Storage.TAG, "speech lane could not load the VAD", e)
                Events.record(this, "speech_lane", "state", "failed", "detail", "vad: ${e.message}")
                recorder.release()
                stopSelf()
                return
            }

        val shorts = ShortArray(SileroVad.WINDOW)
        val window = FloatArray(SileroVad.WINDOW)
        val preRoll = ArrayDeque<ShortArray>()
        val utterance = ArrayList<Short>()
        var inSpeech = false
        var silentWindows = 0
        var speechWindows = 0

        // Liveness for the lane itself. Without it a speech lane that hears
        // digital silence is indistinguishable from a quiet room -- which is
        // the exact failure this app has already been bitten by twice on the
        // ambient side, and the reason the amplitude heartbeat exists there.
        var windowsSeen = 0L
        var peakSeen = 0
        var maxProbability = 0f
        var lastReportAt = System.currentTimeMillis()

        recorder.startRecording()
        Log.i(Storage.TAG, "speech lane listening")

        try {
            while (running.get()) {
                val read = recorder.read(shorts, 0, shorts.size)
                if (read <= 0) continue
                for (i in 0 until read) window[i] = shorts[i] / 32768f
                if (read < window.size) java.util.Arrays.fill(window, read, window.size, 0f)

                val p = vad.probability(window)

                windowsSeen++
                for (i in 0 until read) {
                    val a = kotlin.math.abs(shorts[i].toInt())
                    if (a > peakSeen) peakSeen = a
                }
                if (p > maxProbability) maxProbability = p
                val nowMs = System.currentTimeMillis()
                if (nowMs - lastReportAt >= REPORT_MILLIS) {
                    // A peak of exactly zero across a whole minute is the
                    // platform handing this client silence, not a silent room:
                    // a live microphone reports its own noise floor.
                    Events.record(
                        this,
                        "speech_lane_health",
                        "windows", windowsSeen,
                        "peak_amplitude", peakSeen,
                        "max_probability", maxProbability.toDouble(),
                        "muted", peakSeen == 0,
                    )
                    Log.i(
                        Storage.TAG,
                        "speech lane: $windowsSeen windows, peak $peakSeen, max p=$maxProbability",
                    )
                    windowsSeen = 0
                    peakSeen = 0
                    maxProbability = 0f
                    lastReportAt = nowMs
                }

                if (!inSpeech) {
                    preRoll.addLast(shorts.copyOf(read))
                    while (preRoll.size > PRE_ROLL_WINDOWS) preRoll.removeFirst()
                    if (p >= THRESHOLD) {
                        speechWindows++
                        if (speechWindows >= MIN_SPEECH_WINDOWS) {
                            inSpeech = true
                            silentWindows = 0
                            utterance.clear()
                            preRoll.forEach { chunk -> chunk.forEach { utterance.add(it) } }
                            preRoll.clear()
                        }
                    } else {
                        speechWindows = 0
                    }
                    continue
                }

                for (i in 0 until read) utterance.add(shorts[i])
                if (p < NEG_THRESHOLD) {
                    silentWindows++
                    if (silentWindows >= HANGOVER_WINDOWS) {
                        emit(utterance)
                        utterance.clear()
                        inSpeech = false
                        speechWindows = 0
                        vad.reset()
                    }
                } else {
                    silentWindows = 0
                }

                // A VAD that never closes is a VAD that has failed open --
                // a fan, a television, a car. Cutting at the ceiling keeps the
                // lane alive and keeps every line under the receiver's own
                // limit, which is derived from exactly this number.
                if (utterance.size >= MAX_UTTERANCE_SAMPLES) {
                    emit(utterance)
                    utterance.clear()
                    inSpeech = false
                    speechWindows = 0
                    vad.reset()
                }
            }
        } catch (e: Exception) {
            Log.w(Storage.TAG, "speech lane loop failed", e)
            Events.record(this, "speech_lane", "state", "failed", "detail", e.message)
        } finally {
            try {
                recorder.stop()
            } catch (ignored: Exception) {
                // stopping a recorder that already died is not actionable
            }
            recorder.release()
            vad.close()
        }
    }

    /** One utterance, to the receiver if it answers and to the outbox if not. */
    private fun emit(samples: List<Short>) {
        if (samples.size < SileroVad.SAMPLE_RATE / 4) return // under 250 ms is a cough
        val pcm = ByteArray(samples.size * 2)
        for (i in samples.indices) {
            val v = samples[i].toInt()
            pcm[i * 2] = (v and 0xFF).toByte()
            pcm[i * 2 + 1] = ((v shr 8) and 0xFF).toByte()
        }
        val seconds = samples.size.toDouble() / SileroVad.SAMPLE_RATE
        val line =
            JSONObject()
                .put("kind", "speech")
                .put("ts", Stamps.iso(System.currentTimeMillis()))
                .put("codec", "pcm_s16le")
                .put("rate", SileroVad.SAMPLE_RATE)
                .put("seconds", seconds)
                .put("audio_b64", Base64.encodeToString(pcm, Base64.NO_WRAP))

        if (stream(line)) {
            Events.record(this, "speech_utterance", "seconds", seconds, "path", "live")
            return
        }
        // The receiver is not there. The utterance still exists, so it goes
        // where everything else goes when the tailnet is absent.
        val blob = Outbox.blobFile(this, "speech", "wav")
        if (blob == null) {
            Events.record(this, "speech_utterance", "seconds", seconds, "path", "dropped")
            return
        }
        try {
            blob.writeBytes(wavHeader(pcm.size) + pcm)
            Outbox.writeSidecar(
                this,
                blob,
                JSONObject()
                    .put("kind", "speech")
                    .put("seconds", seconds)
                    .put("rate", SileroVad.SAMPLE_RATE)
                    .put("recorded_at", Stamps.iso(System.currentTimeMillis())),
            )
            Events.record(this, "speech_utterance", "seconds", seconds, "path", "queued")
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not queue utterance", e)
        }
    }

    /**
     * One line, one connection.
     *
     * Not a held socket: this phone sleeps, roams, and changes networks
     * mid-sentence, and a connection kept open across all of that is a
     * connection that is usually stale in a way neither end has noticed. A
     * fresh connect per utterance costs a handshake on a link whose RTT is
     * single-digit milliseconds and removes an entire class of silent failure.
     */
    private fun stream(line: JSONObject): Boolean =
        Prefs.receiverCandidates(this).any { streamTo(it, line) }

    private fun streamTo(target: String, line: JSONObject): Boolean {
        val host = target.substringBeforeLast(':', target)
        val port = target.substringAfterLast(':', "8940").toIntOrNull() ?: 8940
        return try {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(host, port), CONNECT_TIMEOUT_MS)
                socket.soTimeout = CONNECT_TIMEOUT_MS
                socket.getOutputStream().apply {
                    write((line.toString() + "\n").toByteArray())
                    flush()
                }
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun wavHeader(dataBytes: Int): ByteArray {
        val rate = SileroVad.SAMPLE_RATE
        val out = java.io.ByteArrayOutputStream(44)
        fun i32(v: Int) {
            out.write(v and 0xFF); out.write((v shr 8) and 0xFF)
            out.write((v shr 16) and 0xFF); out.write((v shr 24) and 0xFF)
        }
        fun i16(v: Int) { out.write(v and 0xFF); out.write((v shr 8) and 0xFF) }
        out.write("RIFF".toByteArray()); i32(36 + dataBytes); out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray()); i32(16); i16(1); i16(1)
        i32(rate); i32(rate * 2); i16(2); i16(16)
        out.write("data".toByteArray()); i32(dataBytes)
        return out.toByteArray()
    }

    private fun notification(detail: String): Notification {
        Notifications.ensureChannels(this)
        return Notification.Builder(this, Notifications.CHANNEL_STATUS)
            .setContentTitle("Sinnix speech lane")
            .setContentText(detail)
            .setSmallIcon(R.drawable.ic_talk)
            .setOngoing(true)
            .setContentIntent(Notifications.openApp(this, "capture"))
            .build()
    }

    companion object {
        const val ACTION_STOP = "dev.sinnix.phone.SPEECH_STOP"
        private const val NOTIFICATION_ID = 4714

        /** Silero's own default. Above this a window counts as speech. */
        private const val THRESHOLD = 0.5f

        /** Deliberately lower than THRESHOLD: leaving speech should be harder
         *  than entering it, or a breath mid-word ends the utterance. */
        private const val NEG_THRESHOLD = 0.35f

        /** ~108 ms of speech before the lane believes it. Rejects a door click. */
        private const val MIN_SPEECH_WINDOWS = 3

        /** ~0.7 s of quiet before an utterance is considered finished — longer
         *  than the pause inside a sentence, shorter than the one between. */
        private const val HANGOVER_WINDOWS = 20

        /** ~0.6 s kept before onset, because a detector always fires late. */
        private const val PRE_ROLL_WINDOWS = 16

        /** The receiver's line limit is derived from 120 s; stay under it. */
        private const val MAX_UTTERANCE_SAMPLES = SileroVad.SAMPLE_RATE * 110

        private const val CONNECT_TIMEOUT_MS = 2_000

        /** How often the lane says what it is actually hearing. */
        private const val REPORT_MILLIS = 60_000L

        fun start(ctx: Context) {
            if (!Prefs.speechLane(ctx)) return
            ctx.startForegroundService(Intent(ctx, SpeechService::class.java))
        }

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, SpeechService::class.java).setAction(ACTION_STOP))
        }
    }
}
