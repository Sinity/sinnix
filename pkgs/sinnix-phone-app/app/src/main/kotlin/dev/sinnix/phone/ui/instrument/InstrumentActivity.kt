package dev.sinnix.phone.ui.instrument

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.instruments.Catalogue
import dev.sinnix.phone.instruments.Engine
import dev.sinnix.phone.instruments.Instrument
import dev.sinnix.phone.instruments.OfferPolicy
import dev.sinnix.phone.instruments.RunRecord
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.Sparkline
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import dev.sinnix.phone.ui.theme.SinnixTheme

/**
 * The runner.
 *
 * Its own Activity, fullscreen, outside the navigation graph: the whole
 * surface is the response target, so anything the system draws over it is a
 * target the operator might hit mid-trial, and an alarm or a notification
 * should be able to launch straight into a run without the app's tab bar
 * appearing underneath.
 *
 * A Check is a queue of instruments; a shelf run is a queue of one. The
 * between-instrument screen is deliberately plain — a result, a sentence, and
 * the next thing — because a summary screen with anything to explore is a
 * summary screen people stop on.
 */
class InstrumentActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val ids = intent?.getStringArrayExtra(EXTRA_IDS)?.toList().orEmpty()
        val queue =
            if (ids.isEmpty()) OfferPolicy.assembleCheck(this) else ids.mapNotNull(dev.sinnix.phone.decks.Decks::resolve)

        setContent {
            SinnixTheme {
                Box(Modifier.fillMaxSize().background(Palette.Background)) {
                    if (queue.isEmpty()) {
                        NothingToRun { finish() }
                    } else {
                        RunnerFlow(queue) { finish() }
                    }
                }
            }
        }
    }

    companion object {
        private const val EXTRA_IDS = "instrument_ids"

        fun launchCheck(ctx: Context) {
            ctx.startActivity(
                Intent(ctx, InstrumentActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }

        fun launchOne(ctx: Context, id: String) {
            ctx.startActivity(
                Intent(ctx, InstrumentActivity::class.java)
                    .putExtra(EXTRA_IDS, arrayOf(id))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        }
    }
}

@Composable
private fun NothingToRun(onDone: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Nothing to run", style = MaterialTheme.typography.headlineSmall, color = Palette.Text)
        Text(
            "Every instrument was either just measured or is waiting on a condition.",
            style = MaterialTheme.typography.bodySmall,
            color = Palette.TextDim,
        )
        Spacer(Modifier.height(24.dp))
        VerbButton("Back", Modifier.fillMaxWidth(), onDone)
    }
}

private sealed interface Stage {
    data class PreFlight(val index: Int) : Stage

    data class Running(val index: Int) : Stage

    data class Result(val index: Int, val outcome: Outcome) : Stage
}

/** What an engine hands back. [primary] is the one number the result screen shows. */
data class Outcome(
    val primaryLabel: String,
    val primary: Double?,
    val primaryUnit: String,
    val lowerIsBetter: Boolean,
    val fields: Map<String, Any?>,
    val note: String = "",
)

@Composable
private fun RunnerFlow(queue: List<Instrument>, onFinished: () -> Unit) {
    var stage by remember { mutableStateOf<Stage>(Stage.PreFlight(0)) }

    when (val s = stage) {
        is Stage.PreFlight ->
            PreFlightScreen(queue[s.index], queue.size, s.index) {
                stage = Stage.Running(s.index)
            }
        is Stage.Running ->
            EngineHost(queue[s.index]) { outcome -> stage = Stage.Result(s.index, outcome) }
        is Stage.Result ->
            ResultScreen(queue[s.index], s.outcome, s.index + 1 < queue.size) {
                if (s.index + 1 < queue.size) stage = Stage.PreFlight(s.index + 1) else onFinished()
            }
    }
}

/**
 * Pre-flight as a strip, not a gate.
 *
 * Conditions are shown and the start button is always enabled, relabelling
 * itself when something is unmet. Hard blocks exist only where the instrument
 * is meaningless without the condition — an auditory staircase over the phone
 * speaker measures the room, not the ear. Everything else is recorded as a
 * covariate, because a bureaucratic gate kills compliance faster than an
 * annotated trial harms the data.
 */
@Composable
private fun PreFlightScreen(
    instrument: Instrument,
    total: Int,
    index: Int,
    onStart: () -> Unit,
) {
    val ctx = LocalContext.current
    val unmet = remember(instrument) { unmetConditions(ctx, instrument) }
    val blocked = instrument.needsHeadphones && !OfferPolicy.headphonesConnected(ctx)

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        SectionLabel("${index + 1} of $total")
        Text(
            instrument.title,
            style = MaterialTheme.typography.displaySmall,
            color = Palette.Text,
        )
        Spacer(Modifier.height(8.dp))
        Text(instrument.blurb, style = MaterialTheme.typography.bodyMedium, color = Palette.TextDim)
        Spacer(Modifier.height(20.dp))
        if (unmet.isNotEmpty()) {
            Card {
                SectionLabel("Conditions")
                unmet.forEach {
                    Text("◌ $it", style = MaterialTheme.typography.bodySmall, color = Palette.Unverified)
                }
            }
            Spacer(Modifier.height(16.dp))
        }
        VerbButton(
            when {
                blocked -> "Cannot run — ${unmet.firstOrNull() ?: "condition unmet"}"
                unmet.isEmpty() -> "Start"
                else -> "Start anyway — ${unmet.size} recorded as covariates"
            },
            Modifier.fillMaxWidth(),
        ) {
            if (!blocked) onStart()
        }
    }
}

private fun unmetConditions(ctx: Context, instrument: Instrument): List<String> {
    val out = ArrayList<String>()
    if (instrument.needsHeadphones && !OfferPolicy.headphonesConnected(ctx)) {
        out += "headphones not connected"
    }
    dev.sinnix.phone.capture.AmbientSensors.latest?.let { r ->
        if (instrument.engine == Engine.HOLD_STILL && (r.motionRms ?: 0.0) > 0.4) {
            out += "phone is moving"
        }
        if (instrument.needsCamera && (r.luxMean ?: 0.0) > 2000) out += "very bright — cover the lens fully"
    }
    return out
}

@Composable
private fun EngineHost(instrument: Instrument, onDone: (Outcome) -> Unit) {
    when (instrument.engine) {
        Engine.REACTION -> ReactionEngine(instrument, onDone)
        Engine.FORCED_CHOICE -> ForcedChoiceEngine(instrument, onDone)
        Engine.STAIRCASE -> StaircaseEngine(instrument, onDone)
        Engine.HOLD_STILL -> HoldStillEngine(instrument, onDone)
        Engine.COUNTING -> CountingEngine(instrument, onDone)
    }
}

/**
 * One number, its history, and one sentence.
 *
 * For an instrument prime scores, the number is absent and the screen says so
 * — the receipt is the ending. That is not a downgrade: a live heart-rate
 * readout would invite exactly the realtime self-steering this design excludes
 * on purpose.
 */
@Composable
private fun ResultScreen(
    instrument: Instrument,
    outcome: Outcome,
    hasNext: Boolean,
    onNext: () -> Unit,
) {
    val ctx = LocalContext.current
    val history =
        remember(instrument.id) {
            RunRecord.history(ctx, instrument.id, outcome.primaryLabel.lowercase().replace(' ', '_'))
        }

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        SectionLabel(instrument.title)
        if (outcome.primary != null) {
            Text(
                "${format(outcome.primary)} ${outcome.primaryUnit}",
                style = MaterialTheme.typography.displaySmall,
                color = Palette.Text,
            )
            Spacer(Modifier.height(12.dp))
            if (history.size >= 2) {
                Sparkline(history + outcome.primary, invertGood = outcome.lowerIsBetter)
                Spacer(Modifier.height(8.dp))
            }
            Text(
                RunRecord.context(history, outcome.primary, outcome.lowerIsBetter),
                style = MaterialTheme.typography.bodyMedium,
                color = Palette.TextDim,
            )
        } else {
            Text("Captured", style = MaterialTheme.typography.displaySmall, color = Palette.Text)
            Text(
                "Prime scores this one. The result comes back as a notification.",
                style = MaterialTheme.typography.bodyMedium,
                color = Palette.TextDim,
            )
        }
        if (outcome.note.isNotEmpty()) {
            Spacer(Modifier.height(8.dp))
            Text(outcome.note, style = MaterialTheme.typography.labelSmall, color = Palette.TextFaint)
        }
        Spacer(Modifier.height(28.dp))
        VerbButton(if (hasNext) "Next" else "Done", Modifier.fillMaxWidth(), onNext)
    }
}

private fun format(v: Double): String =
    if (v >= 100) v.toInt().toString() else String.format("%.1f", v)
