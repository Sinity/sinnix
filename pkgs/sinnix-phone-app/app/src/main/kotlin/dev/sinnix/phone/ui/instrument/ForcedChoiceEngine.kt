package dev.sinnix.phone.ui.instrument

import android.view.Choreographer
import android.view.MotionEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInteropFilter
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.core.Epoch
import dev.sinnix.phone.instruments.Instrument
import dev.sinnix.phone.instruments.RunRecord
import dev.sinnix.phone.ui.ProgressArc
import dev.sinnix.phone.ui.theme.Palette
import kotlin.random.Random
import kotlinx.coroutines.delay

/**
 * N alternatives, one correct, latency and accuracy both recorded.
 *
 * Stroop lives here, and so does every deck whose engine is `forced_choice` —
 * expression reading at an exposure, name–face binding, affect labelling,
 * prosody intent. The engine knows nothing about any of them: a trial is a
 * prompt, a set of option labels, an optional colour per option, and an index
 * that is correct. That is exactly the contract a JSON deck can satisfy, which
 * is what makes the instrument catalogue open-ended without an app release.
 */
@Composable
fun ForcedChoiceEngine(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val epoch = remember { Epoch.current(ctx) }
    val startedAt = remember { System.currentTimeMillis() }

    val trialCount = (instrument.config["trials"] as? Int) ?: 30
    val exposureMs = (instrument.config["exposure_ms"] as? Int) ?: 0
    @Suppress("UNCHECKED_CAST")
    val deckTrials = instrument.config["trials_data"] as? List<Map<String, Any?>>

    val trials =
        remember(instrument.id) {
            deckTrials?.map { t ->
                Trial(
                    prompt = t["prompt"]?.toString().orEmpty(),
                    promptColor = (t["prompt_color"] as? Long)?.let { Color(it.toULong()) },
                    options = (t["options"] as? List<*>)?.map { it.toString() }.orEmpty(),
                    correct = (t["correct"] as? Int) ?: 0,
                    tag = t["tag"]?.toString().orEmpty(),
                )
            }
                ?: stroopTrials(
                    trialCount,
                    (instrument.config["incongruent_fraction"] as? Double) ?: 0.5,
                )
        }

    var index by remember { mutableStateOf(0) }
    var visible by remember { mutableStateOf(false) }
    var stimulusAtMs by remember { mutableStateOf(0L) }
    var feedback by remember { mutableStateOf(false) }
    val latencies = remember { mutableListOf<Int>() }
    val correctLatencies = remember { mutableListOf<Int>() }
    var correctCount by remember { mutableStateOf(0) }
    var discarded by remember { mutableStateOf(0) }
    val congruentRt = remember { mutableListOf<Int>() }
    val incongruentRt = remember { mutableListOf<Int>() }

    LaunchedEffect(index) {
        if (index >= trials.size) {
            val medianCorrect =
                correctLatencies.sorted().let { if (it.isEmpty()) null else it[it.size / 2].toDouble() }
            val interference =
                if (congruentRt.isNotEmpty() && incongruentRt.isNotEmpty()) {
                    incongruentRt.average() - congruentRt.average()
                } else null
            RunRecord.write(
                ctx,
                instrument,
                startedAt,
                mapOf(
                    "trials" to trials.size,
                    "accuracy" to correctCount.toDouble() / trials.size.coerceAtLeast(1),
                    "rt_ms" to latencies.toList(),
                    "median_correct_rt_ms" to medianCorrect,
                    "interference_ms" to interference,
                    "discarded" to discarded,
                ),
            )
            onDone(
                Outcome(
                    primaryLabel = if (interference != null) "interference_ms" else "median_correct_rt_ms",
                    primary = interference ?: medianCorrect,
                    primaryUnit = "ms",
                    lowerIsBetter = true,
                    fields = emptyMap(),
                    note =
                        "$correctCount/${trials.size} correct" +
                            if (interference != null) " · incongruent minus congruent" else "",
                )
            )
            return@LaunchedEffect
        }
        visible = false
        delay(400)
        Choreographer.getInstance().postFrameCallback { nanos ->
            stimulusAtMs = nanos / 1_000_000L
            visible = true
        }
        if (exposureMs > 0) {
            // A flash-then-respond deck: the stimulus goes away, the options
            // stay. Exposure is the manipulated variable, so it must not depend
            // on how fast the operator looks up.
            delay(exposureMs.toLong())
            visible = false
        }
    }

    val trial = trials.getOrNull(index)

    Column(
        Modifier.fillMaxSize()
            .background(if (feedback) Palette.SurfaceHigh else Palette.Background)
            .pointerInteropFilter { event ->
                if (event.actionMasked == MotionEvent.ACTION_DOWN && event.pointerCount >= 2) {
                    discarded++
                    index = index // re-present the same trial: no advance
                    visible = false
                }
                false
            }
    ) {
        Box(Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
            if (trial != null && (visible || exposureMs == 0)) {
                Text(
                    trial.prompt,
                    style = MaterialTheme.typography.displaySmall,
                    color = trial.promptColor ?: Palette.Text,
                )
            } else if (trial != null) {
                Text("?", style = MaterialTheme.typography.displaySmall, color = Palette.TextFaint)
            }
        }
        if (trial != null) {
            Column(
                Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                trial.options.chunked(2).forEach { row ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        row.forEach { option ->
                            val optionIndex = trial.options.indexOf(option)
                            dev.sinnix.phone.ui.VerbButton(option, Modifier.weight(1f)) {
                                val rt = (System.currentTimeMillis() - stimulusAtMs).toInt()
                                val corrected =
                                    if (epoch.isCalibrated) (rt - epoch.touchOffsetMs).coerceAtLeast(1)
                                    else rt
                                latencies.add(corrected)
                                if (optionIndex == trial.correct) {
                                    correctCount++
                                    correctLatencies.add(corrected)
                                    if (trial.tag == "congruent") congruentRt.add(corrected)
                                    if (trial.tag == "incongruent") incongruentRt.add(corrected)
                                }
                                feedback = true
                                index++
                            }
                        }
                    }
                }
                Box(Modifier.height(12.dp))
                ProgressArc(index.toFloat() / trials.size.coerceAtLeast(1))
            }
        }
    }

    if (feedback) {
        LaunchedEffect(index) {
            delay(60)
            feedback = false
        }
    }
}

private data class Trial(
    val prompt: String,
    val promptColor: Color?,
    val options: List<String>,
    val correct: Int,
    val tag: String,
)

/**
 * Stroop, generated rather than shipped.
 *
 * Kept because it survives repetition better than n-back or digit span: naming
 * ink colour does not become a different task on the fiftieth run the way a
 * working-memory span does, so a longitudinal series measures state rather
 * than learning.
 */
private fun stroopTrials(n: Int, incongruentFraction: Double): List<Trial> {
    val names = listOf("RED", "GREEN", "BLUE", "AMBER")
    val colors =
        listOf(Palette.Broken, Palette.Evidenced, Color(0xFF6FA8DC), Palette.Unverified)
    return (0 until n).map {
        val wordIdx = Random.nextInt(names.size)
        val incongruent = Random.nextDouble() < incongruentFraction
        val inkIdx =
            if (!incongruent) wordIdx
            else ((wordIdx + 1 + Random.nextInt(names.size - 1)) % names.size)
        Trial(
            prompt = names[wordIdx],
            promptColor = colors[inkIdx],
            options = names,
            correct = inkIdx,
            tag = if (incongruent) "incongruent" else "congruent",
        )
    }
}
