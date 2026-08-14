package dev.sinnix.phone.ui.capture

import android.app.ActivityManager
import android.content.Context
import android.os.PowerManager
import android.os.StatFs
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import dev.sinnix.phone.capture.AmbientService
import dev.sinnix.phone.capture.Coverage
import dev.sinnix.phone.capture.Grade
import dev.sinnix.phone.capture.Status
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import dev.sinnix.phone.instruments.OfferPolicy
import dev.sinnix.phone.sync.Inbox
import dev.sinnix.phone.sync.Outbox
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.GradeRow
import dev.sinnix.phone.ui.RibbonView
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.StatRow
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import java.util.Date

/**
 * The organ's own room — and the only place in the app where trust grading
 * lives.
 *
 * The reason it lives here and stops here: on this device, and in this
 * program's measured history, capture failure impersonates success. Termux
 * truncation delivered chunks every five minutes containing 148 seconds of
 * audio. Reboot death left every visible policy setting intact. Arbitration
 * silence produced a full-bitrate, exact-duration, valid-container file
 * containing digital zeroes. MIUI revoked a grant with no event at all.
 *
 * Against that, "the service is running" is not evidence and must not be drawn
 * as though it were. Everything on this screen either quotes a measurement or
 * says it has none.
 *
 * The phone-side ribbon and the lake-side drain are separate objects on
 * purpose. They answer different questions — "did the microphone work" and
 * "did the audio get out" — and a single indicator conflating them would hide
 * whichever one was fine.
 */
@Composable
fun CaptureScreen(nav: NavController) {
    val ctx = LocalContext.current
    var coverage by remember { mutableStateOf(Coverage.of(ctx, System.currentTimeMillis())) }
    var status by remember { mutableStateOf(Status.read(ctx)) }
    var enabled by remember { mutableStateOf(Prefs.enabled(ctx)) }

    val updatedAt = status?.optString("updated_at").orEmpty()
    val heartbeatAge =
        Stamps.parse(updatedAt).let {
            if (it == 0L) -1L else (System.currentTimeMillis() - it) / 1000L
        }
    val alive = heartbeatAge in 0..120
    val recording = status?.optBoolean("recording") == true
    val muted = status?.optBoolean("muted") == true
    val amplitude = status?.optInt("last_amplitude", -1) ?: -1

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Phone side · 7 days")
            RibbonView(coverage)
            Text(
                "unbroken ${coverage.unbrokenHours()}h · " +
                    "${coverage.coveredHours()} of ${coverage.knownHours()} known hours",
                style = MaterialTheme.typography.labelSmall,
                color = Palette.TextDim,
            )
        }

        Card {
            SectionLabel("Right now")
            GradeRow(
                Grade.of(measured = heartbeatAge >= 0, healthy = alive),
                if (alive) "the recorder is there" else "no recent heartbeat",
                if (heartbeatAge < 0) "status.json has never been written"
                else "status.json ${heartbeatAge}s old",
            )
            GradeRow(
                Grade.of(measured = alive && amplitude >= 0, healthy = recording && !muted),
                when {
                    !alive -> "microphone state unknown"
                    muted -> "microphone is producing digital silence"
                    recording -> "microphone is producing sound"
                    else -> "not recording"
                },
                if (amplitude < 0) "no amplitude sample yet"
                else "last amplitude $amplitude · " +
                    "${status?.optInt("silent_samples", 0) ?: 0} consecutive zero samples",
            )
            status?.let { s ->
                StatRow(
                    "chunk",
                    "${s.optInt("current_chunk_elapsed_seconds")}s / " +
                        "${s.optInt("chunk_seconds_target")}s",
                )
                StatRow("closed since start", s.optInt("chunks_closed").toString())
                StatRow("sampling rate", "${s.optInt("sampling_rate")} Hz")
                if (s.optInt("failures") > 0) {
                    StatRow("failures", s.optInt("failures").toString(), Palette.Broken)
                    Text(
                        s.optString("last_error"),
                        style = MaterialTheme.typography.labelSmall,
                        color = Palette.Broken,
                    )
                }
            }
        }

        // The lake side, deliberately its own object. A phone off wifi for
        // hours is a real, non-alarming gap in the drain and says nothing at
        // all about whether the microphone worked.
        Card {
            SectionLabel("Lake side")
            val pending = Outbox.pendingCount(ctx)
            val inboxAge = Inbox.ageSeconds(ctx, Inbox.GLANCE)
            GradeRow(
                Grade.of(measured = inboxAge >= 0, healthy = inboxAge in 0..7200),
                if (inboxAge < 0) "the drain has never reached this phone"
                else "last drain contact ${OfferPolicy.stalenessOf(ctx, Inbox.GLANCE)}",
                if (inboxAge < 0) "no inbox file has ever arrived"
                else "inbox/glance.json is ${inboxAge}s old",
            )
            StatRow("queued for the drain", pending.toString())
            val dir = Storage.chunkDir(ctx)
            StatRow("chunk directory", dir?.absolutePath ?: "none writable")
            if (dir != null && dir.absolutePath != Storage.SHARED_DIR) {
                Text(
                    "This is app-private storage. Termux cannot read it, so nothing " +
                        "here will ever drain — grant all-files access.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Palette.Broken,
                )
            }
        }

        SelfAccounting()

        if (coverage.holes.isNotEmpty()) {
            Card {
                SectionLabel("Holes")
                coverage.holes.takeLast(8).reversed().forEach { hole ->
                    Column(Modifier.padding(vertical = 6.dp)) {
                        Text(
                            "${Stamps.iso(hole.startMs).drop(5).dropLast(4)} · ${hole.hours}h",
                            style = MaterialTheme.typography.labelMedium,
                            color = Palette.Unverified,
                        )
                        Text(
                            hole.cause,
                            style = MaterialTheme.typography.labelSmall,
                            color = Palette.TextFaint,
                        )
                    }
                }
            }
        }

        Card {
            SectionLabel("Recent chunks")
            Events.recentOfKind(ctx, 2, "chunk_closed").takeLast(12).reversed().forEach { e ->
                val silent = e.optBoolean("captured_nothing", false)
                GradeRow(
                    if (silent) Grade.BROKEN else Grade.EVIDENCED,
                    e.optString("chunk"),
                    "${e.optLong("seconds")}s · ${e.optLong("bytes") / 1024}kB · " +
                        if (silent) "peak amplitude 0 — captured nothing"
                        else "peak amplitude ${e.optInt("peak_amplitude")}",
                )
            }
        }

        VerbButton("Grants", Modifier.fillMaxWidth()) { nav.navigate("grants") }
        VerbButton("Settings", Modifier.fillMaxWidth()) { nav.navigate("settings") }

        Card {
            SectionLabel("Control")
            VerbButton(
                if (enabled) "Stop capture" else "Start capture",
                Modifier.fillMaxWidth(),
            ) {
                // Flipping the preference is the load-bearing half. Sending the
                // stop intent alone would let the watchdog resurrect capture ten
                // minutes later, which makes the button a lie.
                val next = !enabled
                Prefs.setEnabled(ctx, next)
                enabled = next
                if (next) AmbientService.start(ctx) else AmbientService.stop(ctx)
                Events.record(
                    ctx,
                    "capture_toggle",
                    "state", if (next) "started" else "stopped",
                    "by", "capture_screen",
                )
            }
            if (!enabled) {
                Text(
                    "Capture stays off across reboots until you start it here.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Palette.Unverified,
                )
            }
        }
    }
}

/**
 * What this app costs the phone.
 *
 * The same evidence rule turned on the app itself: an archive lane that
 * quietly fills the disk or eats the battery is a failure mode like any other,
 * and it should be visible before it is a problem rather than after.
 */
@Composable
private fun SelfAccounting() {
    val ctx = LocalContext.current
    val (freeBytes, daysLeft) = remember { storageOutlook(ctx) }
    val thermal = remember { thermalHeadroom(ctx) }

    Card {
        SectionLabel("This app's footprint")
        StatRow("free on /sdcard", "${freeBytes / 1_000_000_000.0} GB".take(7) + " GB")
        StatRow(
            "at 3.6 MB / 5 min",
            if (daysLeft > 999) "years" else "$daysLeft days until full",
            if (daysLeft < 3) Palette.Broken else Palette.Text,
        )
        thermal?.let { StatRow("thermal headroom", String.format("%.2f", it)) }
    }
}

private fun storageOutlook(ctx: Context): Pair<Long, Long> {
    return try {
        val stat = StatFs(Storage.chunkDir(ctx)?.absolutePath ?: "/sdcard")
        val free = stat.availableBytes
        // One 300s chunk is ~3.6 MB, so a day of unbroken capture is ~1 GB.
        val perDay = 1_037_000_000L
        free to (free / perDay)
    } catch (e: Exception) {
        0L to 0L
    }
}

private fun thermalHeadroom(ctx: Context): Float? =
    try {
        ctx.getSystemService(PowerManager::class.java)?.getThermalHeadroom(60)?.takeIf {
            !it.isNaN()
        }
    } catch (e: Exception) {
        null
    }
