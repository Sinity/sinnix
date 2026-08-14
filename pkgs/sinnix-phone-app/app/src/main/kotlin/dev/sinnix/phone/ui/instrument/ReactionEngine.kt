package dev.sinnix.phone.ui.instrument

import android.view.Choreographer
import android.view.MotionEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInteropFilter
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import dev.sinnix.phone.core.Epoch
import dev.sinnix.phone.instruments.Instrument
import dev.sinnix.phone.instruments.RunRecord
import dev.sinnix.phone.ui.ProgressArc
import dev.sinnix.phone.ui.theme.Palette
import kotlin.math.roundToInt
import kotlin.random.Random
import kotlinx.coroutines.delay

/**
 * The reaction engine: PVT, tapping, go/no-go.
 *
 * Three timing decisions carry the whole instrument, and none of them is
 * optional:
 *
 * 1. The stimulus timestamp is taken in a [Choreographer] frame callback, so
 *    it is when the frame was *presented*, not when the composition asked for
 *    it. The difference is a whole frame and it is systematic, which is worse
 *    than noise.
 * 2. The response timestamp is [MotionEvent.getEventTime], the digitizer's own
 *    clock, not when the handler happened to run. Under load those diverge by
 *    tens of milliseconds — the same order as the effect being measured.
 * 3. The epoch's touch offset is subtracted if it has been calibrated, and the
 *    record says whether it was. An uncalibrated run is still comparable with
 *    other uncalibrated runs on the same apparatus; silently mixing corrected
 *    and uncorrected numbers is what would not be.
 *
 * Two fingers discard the current trial. Misfires are frequent on a phone held
 * one-handed, and an unforgiving trial UX poisons the data harder than a
 * discarded trial does.
 */
@Composable
fun ReactionEngine(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val epoch = remember { Epoch.current(ctx) }
    val startedAt = remember { System.currentTimeMillis() }

    val freeTap = instrument.config["mode"] == "free_tap"
    val trials = (instrument.config["trials"] as? Int) ?: 25
    val isiMin = (instrument.config["isi_min_ms"] as? Int) ?: 2000
    val isiMax = (instrument.config["isi_max_ms"] as? Int) ?: 10000
    val noGoFraction = (instrument.config["nogo_fraction"] as? Double) ?: 0.0
    val tapDuration = (instrument.config["duration_ms"] as? Int) ?: 30000

    val rts = remember { mutableListOf<Int>() }
    val tapIntervals = remember { mutableListOf<Int>() }
    var falseStarts by remember { mutableStateOf(0) }
    var commissions by remember { mutableStateOf(0) }
    var omissions by remember { mutableStateOf(0) }
    var discarded by remember { mutableStateOf(0) }
    var interruptions by remember { mutableStateOf(0) }

    var trial by remember { mutableStateOf(0) }
    var lit by remember { mutableStateOf(false) }
    var isNoGo by remember { mutableStateOf(false) }
    var stimulusAtMs by remember { mutableStateOf(0L) }
    var flash by remember { mutableStateOf(false) }
    var lastTapAt by remember { mutableStateOf(0L) }
    var paused by remember { mutableStateOf(false) }
    var discardTrial by remember { mutableStateOf(false) }

    // A call, a heads-up notification, a hand over the proximity sensor: the
    // trial in flight is invalid, and recording it as a slow response would be
    // a lie the series carries forever. Discard it and re-present at the same
    // position; the run's `interruptions` count is what survives.
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_PAUSE) {
                paused = true
                if (lit) {
                    interruptions++
                    discardTrial = true
                }
            } else if (event == Lifecycle.Event.ON_RESUME) {
                paused = false
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }

    if (freeTap) {
        LaunchedEffect(Unit) {
            delay(tapDuration.toLong())
            val mean = tapIntervals.takeIf { it.isNotEmpty() }?.average()
            val sd =
                tapIntervals.takeIf { it.size > 1 }?.let { xs ->
                    val m = xs.average()
                    kotlin.math.sqrt(xs.sumOf { (it - m) * (it - m) } / (xs.size - 1.0))
                }
            RunRecord.write(
                ctx,
                instrument,
                startedAt,
                mapOf(
                    "taps" to tapIntervals.size + 1,
                    "interval_ms" to tapIntervals.toList(),
                    "interval_mean_ms" to mean,
                    "interval_sd_ms" to sd,
                    "interruptions" to interruptions,
                ),
            )
            onDone(
                Outcome(
                    primaryLabel = "interval_sd_ms",
                    primary = sd,
                    primaryUnit = "ms SD",
                    lowerIsBetter = true,
                    fields = emptyMap(),
                    note = "${tapIntervals.size + 1} taps · variability moves before rate does",
                )
            )
        }
    } else {
        LaunchedEffect(trial, discardTrial, paused) {
            if (paused) return@LaunchedEffect
            if (discardTrial) {
                discardTrial = false
                lit = false
                return@LaunchedEffect
            }
            if (trial >= trials) {
                val median = rts.sorted().let { if (it.isEmpty()) null else it[it.size / 2].toDouble() }
                RunRecord.write(
                    ctx,
                    instrument,
                    startedAt,
                    mapOf(
                        "trials" to trials,
                        "rt_ms" to rts.toList(),
                        "median_rt_ms" to median,
                        "mean_rt_ms" to rts.takeIf { it.isNotEmpty() }?.average(),
                        "lapses" to rts.count { it >= LAPSE_MS },
                        "false_starts" to falseStarts,
                        "commissions" to commissions,
                        "omissions" to omissions,
                        "discarded" to discarded,
                        "interruptions" to interruptions,
                        "touch_offset_applied_ms" to
                            if (epoch.isCalibrated) epoch.touchOffsetMs else null,
                    ),
                )
                onDone(
                    Outcome(
                        primaryLabel = "median_rt_ms",
                        primary = median,
                        primaryUnit = "ms",
                        lowerIsBetter = true,
                        fields = emptyMap(),
                        note =
                            "${rts.size} valid · ${rts.count { it >= LAPSE_MS }} lapses" +
                                if (!epoch.isCalibrated) " · touch latency uncalibrated (${epoch.id})"
                                else " · ${epoch.id}",
                    )
                )
                return@LaunchedEffect
            }

            lit = false
            delay(Random.nextInt(isiMin, isiMax + 1).toLong())
            isNoGo = noGoFraction > 0 && Random.nextDouble() < noGoFraction
            // Timestamp the frame that actually shows the stimulus, not the
            // recomposition that requested it.
            Choreographer.getInstance().postFrameCallback { frameTimeNanos ->
                stimulusAtMs = frameTimeNanos / 1_000_000L
                lit = true
            }
            if (noGoFraction > 0) {
                // A no-go trial ends by nothing happening, so it needs its own
                // deadline; a go trial that times out is an omission either way.
                delay(NO_RESPONSE_MS.toLong())
                if (lit) {
                    if (isNoGo) rts.add(0) else omissions++
                    lit = false
                    trial++
                }
            }
        }
    }

    Box(
        Modifier.fillMaxSize()
            .background(
                when {
                    flash -> Palette.Text
                    lit && isNoGo -> Color.Transparent
                    lit -> Palette.Accent
                    else -> Palette.Background
                }
            )
            .pointerInteropFilter { event ->
                if (event.actionMasked != MotionEvent.ACTION_DOWN) return@pointerInteropFilter true
                // Digitizer time, not handler time.
                val eventMs = event.eventTime
                if (event.pointerCount >= 2) {
                    // Two fingers: the operator says that one did not count.
                    if (lit) {
                        discarded++
                        discardTrial = true
                    }
                    return@pointerInteropFilter true
                }
                if (freeTap) {
                    if (lastTapAt != 0L) tapIntervals.add((eventMs - lastTapAt).toInt())
                    lastTapAt = eventMs
                    flash = true
                    return@pointerInteropFilter true
                }
                if (!lit) {
                    // Anticipation. Recorded, and the trial continues — a false
                    // start that silently reset the trial would hide the very
                    // impulsivity it is evidence of.
                    falseStarts++
                    return@pointerInteropFilter true
                }
                if (isNoGo) {
                    commissions++
                } else {
                    val raw = (eventMs - stimulusAtMs).toInt()
                    val corrected =
                        if (epoch.isCalibrated) (raw - epoch.touchOffsetMs).coerceAtLeast(1) else raw
                    if (corrected in 1..NO_RESPONSE_MS) rts.add(corrected)
                }
                lit = false
                flash = true
                trial++
                true
            },
        contentAlignment = Alignment.Center,
    ) {
        if (flash) {
            LaunchedEffect(trial, tapIntervals.size) {
                delay(60)
                flash = false
            }
        }
        Column(
            Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (!lit && !freeTap) {
                Text(
                    if (trial == 0) "Tap the instant it changes" else "",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Palette.TextFaint,
                )
            }
            if (freeTap) {
                Text(
                    "${tapIntervals.size + if (lastTapAt == 0L) 0 else 1}",
                    style = MaterialTheme.typography.displaySmall,
                    color = Palette.TextDim,
                )
            }
            if (lit && isNoGo) {
                Text("○", style = MaterialTheme.typography.displaySmall, color = Palette.TextDim)
            }
        }
        if (!freeTap) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.BottomCenter) {
                ProgressArc(trial.toFloat() / trials.coerceAtLeast(1))
            }
        }
    }
}

/** A response this slow is a lapse of attention, not a slow reaction. */
private const val LAPSE_MS = 500

/** Ceiling for a missed stimulus, so one wandering trial cannot stall the run. */
private const val NO_RESPONSE_MS = 10_000
