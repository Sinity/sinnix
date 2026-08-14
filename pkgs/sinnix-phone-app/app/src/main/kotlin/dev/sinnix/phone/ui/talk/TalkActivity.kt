package dev.sinnix.phone.ui.talk

import android.content.Context
import android.content.Intent
import android.media.MediaRecorder
import android.os.Build
import android.os.Bundle
import android.service.quicksettings.TileService
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.core.Epoch
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import dev.sinnix.phone.sync.Outbox
import dev.sinnix.phone.ui.HoldRing
import dev.sinnix.phone.ui.theme.Palette
import dev.sinnix.phone.ui.theme.SinnixTheme
import java.io.File
import kotlinx.coroutines.delay
import org.json.JSONObject

/**
 * Hold to talk.
 *
 * Its own recorder, running concurrently with the ambient lane — measured on
 * this device as two AudioRecord clients on separate input ports with no loss
 * on either. Ambient capture is not paused for a voice note, because a note is
 * exactly the moment you would least want a hole in the archive.
 *
 * No transcription here. Prime's engine is better than anything that would fit
 * on the device, and the receipt pattern is a feature rather than a
 * consolation: a note that answers back instantly invites the realtime
 * self-steering this design avoids on purpose.
 */
class TalkActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val jobId = intent?.getStringExtra(EXTRA_JOB_ID)
        setContent {
            SinnixTheme {
                Box(Modifier.fillMaxSize().background(Palette.Background)) {
                    TalkSurface(jobId) { finish() }
                }
            }
        }
    }

    companion object {
        private const val EXTRA_JOB_ID = "job_id"

        fun launch(ctx: Context) {
            ctx.startActivity(
                Intent(ctx, TalkActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }

        /** Speaking an answer to an agent that asked a question. */
        fun launchForJob(ctx: Context, jobId: String) {
            ctx.startActivity(
                Intent(ctx, TalkActivity::class.java)
                    .putExtra(EXTRA_JOB_ID, jobId)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }
}

@Composable
private fun TalkSurface(jobId: String?, onDone: () -> Unit) {
    val ctx = LocalContext.current
    var recording by remember { mutableStateOf(false) }
    var seconds by remember { mutableStateOf(0) }
    var saved by remember { mutableStateOf<String?>(null) }
    val session = remember { TalkSession(ctx) }

    DisposableEffect(Unit) { onDispose { session.stopIfRunning(ctx, jobId) } }

    LaunchedEffect(recording) {
        if (!recording) return@LaunchedEffect
        while (recording) {
            delay(1000)
            seconds++
        }
    }

    Column(
        Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            if (jobId != null) "Answering an agent" else "Voice note",
            style = MaterialTheme.typography.titleMedium,
            color = Palette.TextDim,
        )
        Box(
            Modifier.size(220.dp)
                .pointerInput(Unit) {
                    detectTapGestures(
                        onPress = {
                            if (session.start()) {
                                recording = true
                                seconds = 0
                                // Hold, not toggle. A toggle that is left on is
                                // a recorder running in a pocket, and the whole
                                // value of this verb is that it costs nothing to
                                // use badly.
                                tryAwaitRelease()
                                recording = false
                                saved = session.stop(ctx, jobId)
                            }
                        }
                    )
                },
            contentAlignment = Alignment.Center,
        ) {
            HoldRing(if (recording) ((seconds % 60) / 60f) else 0f, Modifier.fillMaxSize())
            Text(
                if (recording) "${seconds}s" else "hold",
                style = MaterialTheme.typography.displaySmall,
                color = if (recording) Palette.Accent else Palette.TextDim,
            )
        }
        Text(
            saved
                ?: if (jobId != null) "Prime transcribes it and hands it to the agent."
                else "Prime transcribes it. The text comes back as a notification.",
            style = MaterialTheme.typography.bodySmall,
            color = Palette.TextDim,
        )
        if (saved != null) {
            LaunchedEffect(saved) {
                delay(1200)
                onDone()
            }
        }
    }
}

/** One recorder, one file, one sidecar. */
private class TalkSession(private val ctx: Context) {

    private var recorder: MediaRecorder? = null
    private var file: File? = null
    private var startedAt = 0L

    fun start(): Boolean {
        val target = Outbox.blobFile(ctx, "voice", "m4a") ?: return false
        val r =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) MediaRecorder(ctx)
            else @Suppress("DEPRECATION") MediaRecorder()
        r.setAudioSource(MediaRecorder.AudioSource.MIC)
        r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
        r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
        r.setAudioChannels(1)
        // Speech, not archive: 44.1 kHz at 64 kbps is generous for a voice note
        // and keeps the file small enough that a drain over a phone hotspot is
        // not an event.
        r.setAudioSamplingRate(44_100)
        r.setAudioEncodingBitRate(64_000)
        r.setOutputFile(target.absolutePath)
        return try {
            r.prepare()
            r.start()
            recorder = r
            file = target
            startedAt = System.currentTimeMillis()
            true
        } catch (e: Exception) {
            android.util.Log.w(Storage.TAG, "talk recorder failed to start", e)
            try {
                r.release()
            } catch (ignored: Exception) {}
            false
        }
    }

    fun stop(ctx: Context, jobId: String?): String? {
        val r = recorder ?: return null
        val f = file
        recorder = null
        file = null
        val seconds = ((System.currentTimeMillis() - startedAt) / 1000L).coerceAtLeast(0L)
        return try {
            r.stop()
            r.release()
            if (f == null || !f.isFile || f.length() == 0L) {
                f?.delete()
                return "nothing recorded"
            }
            if (seconds < 1) {
                // A tap that was not a hold. Deleting it is kinder than
                // shipping prime a 300 ms file to transcribe.
                f.delete()
                return "too short"
            }
            Outbox.writeSidecar(
                ctx,
                f,
                JSONObject()
                    .put("kind", if (jobId != null) "job_answer_voice" else "voice_note")
                    .put("seconds", seconds)
                    .put("recorded_at", Stamps.iso(startedAt))
                    .put("epoch", Epoch.current(ctx).id)
                    .apply { if (jobId != null) put("job_id", jobId) },
            )
            "${seconds}s handed to prime"
        } catch (e: Exception) {
            f?.delete()
            "recording failed"
        }
    }

    fun stopIfRunning(ctx: Context, jobId: String?) {
        // An interrupted note is still a note: the operator said something, and
        // discarding it because a call arrived would lose the thing they meant
        // to keep.
        if (recorder != null) stop(ctx, jobId)
    }
}

/** Quick-settings tile: pocket to recording in one tap, which is the whole feature. */
class TalkTileService : TileService() {
    override fun onClick() {
        super.onClick()
        val intent =
            Intent(this, TalkActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        @Suppress("DEPRECATION")
        startActivityAndCollapse(intent)
    }
}
