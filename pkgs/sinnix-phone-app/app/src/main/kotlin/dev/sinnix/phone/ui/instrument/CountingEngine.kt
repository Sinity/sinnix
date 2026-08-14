package dev.sinnix.phone.ui.instrument

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.instruments.Instrument
import dev.sinnix.phone.instruments.RunRecord
import dev.sinnix.phone.ui.HoldRing
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import kotlinx.coroutines.delay

/**
 * Counting: breath counting, and Schandry heartbeat counting.
 *
 * Breath counting is the interesting one. It is a validated objective measure
 * of meta-awareness rather than a relaxation exercise, and the reason is the
 * two failure modes it separates:
 *
 * - **unaware miscount** — you pressed "nine" at the wrong position, so
 *   attention had already left and you did not notice.
 * - **self-caught reset** — you noticed you had lost count and said so.
 *
 * These are never summed, here or anywhere downstream. Noticing that you
 * drifted is a different (and better) state than drifting without noticing,
 * and a single "errors" number would erase exactly the distinction the
 * instrument exists to measure.
 */
@Composable
fun CountingEngine(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val startedAt = remember { System.currentTimeMillis() }
    val schandry = instrument.config["mode"] == "schandry"

    if (schandry) {
        SchandryCounting(instrument, onDone)
        return
    }

    val cycle = (instrument.config["cycle"] as? Int) ?: 9
    var position by remember { mutableStateOf(1) }
    var cyclesCorrect by remember { mutableStateOf(0) }
    var unawareMiscounts by remember { mutableStateOf(0) }
    var selfCaughtResets by remember { mutableStateOf(0) }
    var done by remember { mutableStateOf(false) }

    fun finish() {
        if (done) return
        done = true
        RunRecord.write(
            ctx,
            instrument,
            startedAt,
            mapOf(
                "cycles_correct" to cyclesCorrect,
                "unaware_miscounts" to unawareMiscounts,
                "self_caught_resets" to selfCaughtResets,
                "cycle_length" to cycle,
            ),
        )
        val total = cyclesCorrect + unawareMiscounts
        val accuracy = if (total == 0) null else cyclesCorrect.toDouble() / total
        onDone(
            Outcome(
                primaryLabel = "cycles_correct",
                primary = accuracy?.times(100),
                primaryUnit = "% cycles held",
                lowerIsBetter = false,
                fields = emptyMap(),
                note =
                    "$unawareMiscounts unnoticed · $selfCaughtResets caught yourself" +
                        " — these are kept apart on purpose",
            )
        )
    }

    Column(Modifier.fillMaxSize()) {
        Box(
            Modifier.weight(1f)
                .fillMaxWidth()
                .background(Palette.Background)
                .clickable {
                    // The big zone is 1–8. Pressing it on nine is an unaware
                    // miscount: the count ran past the cycle without being
                    // noticed.
                    if (position == cycle) {
                        unawareMiscounts++
                        position = 1
                    } else {
                        position++
                    }
                },
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "$position",
                    style = MaterialTheme.typography.displaySmall,
                    color = Palette.Text,
                )
                Text(
                    "breath",
                    style = MaterialTheme.typography.labelSmall,
                    color = Palette.TextFaint,
                )
            }
        }
        Box(
            Modifier.fillMaxWidth()
                .height(120.dp)
                .background(Palette.SurfaceHigh)
                .clickable {
                    // The small zone is nine, and only nine. Pressing it early
                    // is also an unaware miscount — the same failure from the
                    // other direction.
                    if (position == cycle) cyclesCorrect++ else unawareMiscounts++
                    position = 1
                },
            contentAlignment = Alignment.Center,
        ) {
            Text("nine", style = MaterialTheme.typography.titleLarge, color = Palette.Accent)
        }
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            VerbButton("I lost count", Modifier.fillMaxWidth()) {
                selfCaughtResets++
                position = 1
            }
            VerbButton("Done", Modifier.fillMaxWidth()) { finish() }
        }
    }
}

/**
 * Heartbeat counting with the phone supplying its own ground truth.
 *
 * The Schandry task normally needs an ECG in the room to score against, which
 * is what keeps interoceptive accuracy a lab measure. Running finger PPG in
 * the same session solves that: the operator counts what they feel, the camera
 * records what actually happened, and prime compares the two.
 *
 * The count is never shown against the truth on the device. Seeing your own
 * accuracy immediately would train the estimate rather than measure it.
 */
@Composable
private fun SchandryCounting(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val startedAt = remember { System.currentTimeMillis() }
    @Suppress("UNCHECKED_CAST")
    val windows = (instrument.config["windows_ms"] as? List<Int>) ?: listOf(25_000, 35_000, 45_000)

    var windowIndex by remember { mutableStateOf(0) }
    var counting by remember { mutableStateOf(false) }
    var count by remember { mutableStateOf(0) }
    var progress by remember { mutableStateOf(0f) }
    val counts = remember { mutableListOf<Int>() }

    LaunchedEffect(windowIndex, counting) {
        if (!counting) return@LaunchedEffect
        val duration = windows[windowIndex].toLong()
        var elapsed = 0L
        while (elapsed < duration) {
            delay(100)
            elapsed += 100
            progress = elapsed.toFloat() / duration
        }
        counts.add(count)
        counting = false
        count = 0
        progress = 0f
        if (windowIndex + 1 >= windows.size) {
            RunRecord.write(
                ctx,
                instrument,
                startedAt,
                mapOf(
                    "counted" to counts.toList(),
                    "window_ms" to windows,
                    "scored_by" to "prime",
                ),
            )
            onDone(
                Outcome(
                    primaryLabel = "",
                    primary = null,
                    primaryUnit = "",
                    lowerIsBetter = false,
                    fields = emptyMap(),
                    note = "counted ${counts.joinToString(", ")} — accuracy comes back as a receipt",
                )
            )
        } else {
            windowIndex++
        }
    }

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.height(200.dp).fillMaxWidth(), contentAlignment = Alignment.Center) {
            HoldRing(progress, Modifier.fillMaxSize())
            Text("$count", style = MaterialTheme.typography.displaySmall, color = Palette.Text)
        }
        Text(
            if (counting) "count the beats you feel — do not take your pulse"
            else "window ${windowIndex + 1} of ${windows.size}",
            style = MaterialTheme.typography.bodyMedium,
            color = Palette.TextDim,
        )
        Box(Modifier.height(20.dp))
        if (counting) {
            VerbButton("beat", Modifier.fillMaxWidth()) { count++ }
        } else {
            VerbButton("Start window ${windowIndex + 1}", Modifier.fillMaxWidth()) {
                counting = true
            }
        }
    }
}
