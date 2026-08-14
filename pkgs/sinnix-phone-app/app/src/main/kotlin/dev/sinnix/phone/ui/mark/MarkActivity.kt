package dev.sinnix.phone.ui.mark

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.service.quicksettings.TileService
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.capture.AmbientSensors
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.talk.TalkActivity
import dev.sinnix.phone.ui.theme.Palette
import dev.sinnix.phone.ui.theme.SinnixTheme

/**
 * Mark: a timestamp with a word attached.
 *
 * The cheapest capture in the whole design, and the one that multiplies
 * everything else at join time. A reaction-time series is a curve; a
 * reaction-time series with caffeine doses on it is a dose–response curve, and
 * the difference is one tap at the moment of drinking.
 *
 * Budget: three seconds from a cold phone. That is why it is a sheet over
 * whatever was on screen rather than a screen in the app, why the common marks
 * are one tap with no confirmation, and why the tile and the widget both land
 * here directly.
 */
class MarkActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val preset = intent?.getStringExtra(EXTRA_MARK)
        if (preset != null) {
            // Launched from a notification action or a widget button: the mark
            // is already decided, so no UI at all.
            record(this, preset, null)
            finish()
            return
        }
        setContent {
            SinnixTheme {
                Box(
                    Modifier.fillMaxSize().padding(20.dp),
                    contentAlignment = Alignment.BottomCenter,
                ) {
                    MarkSheet(onDone = { finish() })
                }
            }
        }
    }

    companion object {
        private const val EXTRA_MARK = "mark"

        val COMMON = listOf("caffeine", "meal", "med", "nap", "exercise", "alcohol")

        fun launch(ctx: Context) {
            ctx.startActivity(
                Intent(ctx, MarkActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }

        fun intentFor(ctx: Context, mark: String): Intent =
            Intent(ctx, MarkActivity::class.java)
                .putExtra(EXTRA_MARK, mark)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

        /**
         * Marks carry the passive covariates that were true at the moment,
         * because the join later is against those same fields and a mark
         * without them can only be matched on time.
         */
        fun record(ctx: Context, mark: String, note: String?) {
            val sensors = AmbientSensors.latest
            Events.record(
                ctx,
                "mark",
                "mark", mark,
                "note", note,
                "lux_mean", sensors?.luxMean,
                "motion_rms", sensors?.motionRms,
            )
        }
    }
}

@Composable
private fun MarkSheet(onDone: () -> Unit) {
    val ctx = LocalContext.current
    var custom by remember { mutableStateOf("") }

    Column(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(Palette.Surface)
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        SectionLabel("Mark")
        MarkActivity.COMMON.chunked(3).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { mark ->
                    VerbButton(mark, Modifier.weight(1f)) {
                        MarkActivity.record(ctx, mark, null)
                        onDone()
                    }
                }
            }
        }
        OutlinedTextField(
            value = custom,
            onValueChange = { custom = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("something else") },
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            VerbButton("Log it", Modifier.weight(1f)) {
                if (custom.isNotBlank()) MarkActivity.record(ctx, custom.trim(), null)
                onDone()
            }
            // A mark with a voice tail, for the cases where the word is not
            // enough and typing would cost more than the mark is worth.
            VerbButton("+ voice", Modifier.weight(1f)) {
                MarkActivity.record(ctx, custom.ifBlank { "note" }.trim(), "voice tail follows")
                TalkActivity.launch(ctx)
                onDone()
            }
        }
        Text(
            "Marks are what make every other series interpretable.",
            style = MaterialTheme.typography.labelSmall,
            color = Palette.TextFaint,
        )
    }
}

/** One tap from the shade, no app launch. */
class MarkTileService : TileService() {
    override fun onClick() {
        super.onClick()
        @Suppress("DEPRECATION")
        startActivityAndCollapse(
            Intent(this, MarkActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
    }
}
