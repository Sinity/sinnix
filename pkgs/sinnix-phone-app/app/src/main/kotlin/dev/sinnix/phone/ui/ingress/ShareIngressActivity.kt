package dev.sinnix.phone.ui.ingress

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import dev.sinnix.phone.sync.Outbox
import dev.sinnix.phone.ui.theme.Palette
import dev.sinnix.phone.ui.theme.SinnixTheme
import kotlinx.coroutines.delay
import org.json.JSONObject

/**
 * The phone's universal export verb.
 *
 * One manifest entry turns the app into a target in every share sheet on the
 * device, which is the cheapest possible ingress into the lake: a URL from the
 * browser, a photo from the gallery, a quote from a reader, all land in the
 * outbox and drain like anything else.
 *
 * It is also the sanctioned workaround for Android's background-clipboard-read
 * ban. Since Android 10 a backgrounded app cannot read the clipboard, so the
 * phone→desktop direction of clipboard sync is simply not available — but
 * *sharing* is push-shaped and always allowed, which gets the same content
 * across without an AccessibilityService or a foregrounded Termux.
 *
 * The whole interaction is a confirmation that appears and leaves. Anything
 * that feels like the app opening has already cost more than the share was
 * worth.
 */
class ShareIngressActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val summary = ingest(intent)
        setContent {
            SinnixTheme {
                Box(
                    Modifier.fillMaxSize().padding(20.dp),
                    contentAlignment = Alignment.BottomCenter,
                ) {
                    Confirmation(summary) { finish() }
                }
            }
        }
    }

    /** Everything is written before a pixel is drawn: the sheet reports, it does not work. */
    private fun ingest(intent: Intent?): String {
        if (intent == null) return "nothing shared"
        val texts = ArrayList<String>()
        val uris = ArrayList<Uri>()

        when (intent.action) {
            Intent.ACTION_SEND -> {
                intent.getStringExtra(Intent.EXTRA_TEXT)?.let { texts.add(it) }
                @Suppress("DEPRECATION")
                (intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM))?.let { uris.add(it) }
            }
            Intent.ACTION_SEND_MULTIPLE -> {
                @Suppress("DEPRECATION")
                intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)?.let { uris.addAll(it) }
            }
            Intent.ACTION_PROCESS_TEXT -> {
                intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.let {
                    texts.add(it.toString())
                }
            }
        }

        val subject = intent.getStringExtra(Intent.EXTRA_SUBJECT)
        var n = 0

        if (texts.isNotEmpty()) {
            Outbox.writeIntent(
                this,
                "shared_text",
                "text", texts.joinToString("\n\n"),
                "subject", subject,
                "from", intent.getStringExtra(Intent.EXTRA_REFERRER_NAME),
                "shared_at", Stamps.iso(System.currentTimeMillis()),
            )
            n += texts.size
        }

        for (uri in uris) {
            // Copied rather than referenced. A content:// URI is a permission
            // grant that dies with this Activity, so a drain half an hour later
            // would find nothing at the other end of it.
            val copied = copyToOutbox(uri)
            if (copied != null) n++
        }

        return when {
            n == 0 -> "nothing to take"
            n == 1 -> "1 item queued for the lake"
            else -> "$n items queued for the lake"
        }
    }

    private fun copyToOutbox(uri: Uri): String? {
        val name = uri.lastPathSegment?.substringAfterLast('/')?.take(64) ?: "shared"
        val extension = name.substringAfterLast('.', "bin")
        val dest = Outbox.blobFile(this, "shared", extension) ?: return null
        return try {
            contentResolver.openInputStream(uri)?.use { input ->
                dest.outputStream().use { output -> input.copyTo(output) }
            } ?: return null
            Outbox.writeSidecar(
                this,
                dest,
                JSONObject()
                    .put("kind", "shared_file")
                    .put("original_name", name)
                    .put("mime", contentResolver.getType(uri))
                    .put("bytes", dest.length())
                    .put("shared_at", Stamps.iso(System.currentTimeMillis())),
            )
            dest.name
        } catch (e: Exception) {
            android.util.Log.w(Storage.TAG, "could not copy shared $uri", e)
            dest.delete()
            null
        }
    }
}

@Composable
private fun Confirmation(summary: String, onDone: () -> Unit) {
    LaunchedEffect(Unit) {
        delay(1100)
        onDone()
    }
    Column(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(Palette.Surface)
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(summary, style = MaterialTheme.typography.titleMedium, color = Palette.Text)
        Text(
            "it goes out with the next drain",
            style = MaterialTheme.typography.labelSmall,
            color = Palette.TextFaint,
        )
    }
}
