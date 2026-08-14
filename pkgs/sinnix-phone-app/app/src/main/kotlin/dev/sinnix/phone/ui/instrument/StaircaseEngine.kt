package dev.sinnix.phone.ui.instrument

import android.hardware.camera2.CameraManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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
import dev.sinnix.phone.ui.ProgressArc
import dev.sinnix.phone.ui.theme.Palette
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin
import kotlin.random.Random
import kotlinx.coroutines.delay

/**
 * One adaptive ladder, three instruments.
 *
 * The design property that makes an auditory threshold measurable on an
 * uncalibrated phone: **both intervals are rendered into one PCM buffer and
 * played once.** The measurand is then a difference internal to that buffer,
 * so output latency, route latency and clock drift affect both intervals
 * identically and cancel. Contrast sensitivity has no such trick — the
 * apparatus modifies the stimulus itself — which is why it is not in the
 * catalogue and this is.
 *
 * The ladder is a two-down-one-up transformed staircase converging on ~71%
 * correct. A discarded trial re-presents at the same level and does **not**
 * count as a reversal: penalising the reversal count for a misfire corrupts
 * the threshold estimate rather than just costing a trial.
 */
@Composable
fun StaircaseEngine(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val startedAt = remember { System.currentTimeMillis() }
    val torchMode = instrument.config["mode"] == "torch"

    if (torchMode) {
        TorchCffEngine(instrument, onDone)
        return
    }

    val gapMode = instrument.id == "gap_detection"
    val baseHz = (instrument.config["base_hz"] as? Double) ?: 1000.0
    val toneMs = (instrument.config["tone_ms"] as? Int) ?: 400
    val silenceMs = (instrument.config["gap_ms"] as? Int) ?: 300
    val maxReversals = (instrument.config["reversals"] as? Int) ?: 8
    val minLevel =
        (if (gapMode) instrument.config["min_gap_ms"] else instrument.config["min_delta_hz"])
            as? Double ?: 1.0
    val startLevel =
        (if (gapMode) instrument.config["start_gap_ms"] else instrument.config["start_delta_hz"])
            as? Double ?: 40.0

    var level by remember { mutableStateOf(startLevel) }
    var correctRun by remember { mutableStateOf(0) }
    var lastDirection by remember { mutableStateOf(0) }
    val reversals = remember { mutableListOf<Double>() }
    var trials by remember { mutableStateOf(0) }
    var targetInterval by remember { mutableStateOf(0) }
    var playing by remember { mutableStateOf(false) }
    var awaitingResponse by remember { mutableStateOf(false) }
    var flashHalf by remember { mutableStateOf(-1) }

    LaunchedEffect(trials) {
        if (reversals.size >= maxReversals) {
            // The threshold is the mean of the reversals after the first two:
            // early reversals are still descending from the starting level and
            // describe the ladder, not the ear.
            val used = reversals.drop(2).ifEmpty { reversals }
            val threshold = used.average()
            RunRecord.write(
                ctx,
                instrument,
                startedAt,
                mapOf(
                    "threshold" to threshold,
                    "unit" to if (gapMode) "ms" else "hz",
                    "reversal_levels" to reversals.toList(),
                    "trials" to trials,
                    "base_hz" to baseHz,
                ),
            )
            onDone(
                Outcome(
                    primaryLabel = "threshold",
                    primary = threshold,
                    primaryUnit = if (gapMode) "ms gap" else "Hz",
                    lowerIsBetter = true,
                    fields = emptyMap(),
                    note = "${reversals.size} reversals over $trials trials",
                )
            )
            return@LaunchedEffect
        }
        delay(500)
        targetInterval = Random.nextInt(2)
        playing = true
        val pcm =
            if (gapMode) {
                gapPair(baseHz, toneMs, silenceMs, level, targetInterval)
            } else {
                tonePair(baseHz, level, toneMs, silenceMs, targetInterval)
            }
        playOnce(pcm)
        playing = false
        awaitingResponse = true
    }

    fun respond(half: Int) {
        if (!awaitingResponse) return
        awaitingResponse = false
        flashHalf = half
        val correct = half == targetInterval
        if (correct) {
            correctRun++
            if (correctRun >= 2) {
                correctRun = 0
                if (lastDirection == 1) reversals.add(level)
                lastDirection = -1
                level = (level / STEP_FACTOR).coerceAtLeast(minLevel)
            }
        } else {
            correctRun = 0
            if (lastDirection == -1) reversals.add(level)
            lastDirection = 1
            level *= STEP_FACTOR
        }
        trials++
    }

    Column(Modifier.fillMaxSize()) {
        Row(Modifier.weight(1f).fillMaxWidth()) {
            listOf(0, 1).forEach { half ->
                Box(
                    Modifier.weight(1f)
                        .fillMaxHeight()
                        .background(
                            when {
                                flashHalf == half -> Palette.Accent
                                playing -> Palette.SurfaceHigh
                                else -> Palette.Surface
                            }
                        )
                        .clickable { respond(half) },
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        if (half == 0) "first" else "second",
                        style = MaterialTheme.typography.titleMedium,
                        color = if (awaitingResponse) Palette.Text else Palette.TextFaint,
                    )
                }
            }
        }
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (playing) "listen" else if (awaitingResponse) "which half?" else "…",
                style = MaterialTheme.typography.bodyMedium,
                color = Palette.TextDim,
            )
            ProgressArc(reversals.size.toFloat() / maxReversals)
        }
    }

    if (flashHalf >= 0) {
        LaunchedEffect(trials) {
            delay(60)
            flashHalf = -1
        }
    }
}

private const val SAMPLE_RATE = 44_100

/** Two-down-one-up on a multiplicative ladder: geometric steps suit thresholds. */
private const val STEP_FACTOR = 1.6

/**
 * Both tones in one buffer. The whole reason the instrument survives an
 * uncalibrated device — see the class comment.
 */
private fun tonePair(
    baseHz: Double,
    deltaHz: Double,
    toneMs: Int,
    gapMs: Int,
    higherInterval: Int,
): ShortArray {
    val toneN = SAMPLE_RATE * toneMs / 1000
    val gapN = SAMPLE_RATE * gapMs / 1000
    val out = ShortArray(toneN * 2 + gapN)
    val f0 = if (higherInterval == 0) baseHz + deltaHz else baseHz
    val f1 = if (higherInterval == 1) baseHz + deltaHz else baseHz
    writeTone(out, 0, toneN, f0)
    writeTone(out, toneN + gapN, toneN, f1)
    return out
}

private fun gapPair(
    baseHz: Double,
    toneMs: Int,
    gapMs: Int,
    gapLenMs: Double,
    gapInterval: Int,
): ShortArray {
    val toneN = SAMPLE_RATE * toneMs / 1000
    val gapN = SAMPLE_RATE * gapMs / 1000
    val out = ShortArray(toneN * 2 + gapN)
    writeTone(out, 0, toneN, baseHz)
    writeTone(out, toneN + gapN, toneN, baseHz)
    val silentN = (SAMPLE_RATE * gapLenMs / 1000.0).toInt().coerceAtLeast(1)
    val centre = if (gapInterval == 0) toneN / 2 else toneN + gapN + toneN / 2
    for (i in centre until (centre + silentN).coerceAtMost(out.size)) out[i] = 0
    return out
}

/** 5 ms raised-cosine ramps, so the onset is not itself a click to detect. */
private fun writeTone(buf: ShortArray, offset: Int, n: Int, hz: Double) {
    val ramp = (SAMPLE_RATE * 0.005).toInt().coerceAtLeast(1)
    for (i in 0 until n) {
        val env =
            when {
                i < ramp -> 0.5 * (1 - kotlin.math.cos(PI * i / ramp))
                i > n - ramp -> 0.5 * (1 - kotlin.math.cos(PI * (n - i) / ramp))
                else -> 1.0
            }
        val v = sin(2.0 * PI * hz * i / SAMPLE_RATE) * env * 0.35
        buf[offset + i] = (v * Short.MAX_VALUE).toInt().toShort()
    }
}

private suspend fun playOnce(pcm: ShortArray) {
    val track =
        AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(SAMPLE_RATE)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setTransferMode(AudioTrack.MODE_STATIC)
            .setBufferSizeInBytes(pcm.size * 2)
            .build()
    track.write(pcm, 0, pcm.size)
    track.play()
    delay((pcm.size * 1000L / SAMPLE_RATE) + 50)
    track.stop()
    track.release()
}

/**
 * Critical flicker fusion through the torch LED.
 *
 * The panel cannot do this: a 120 Hz display puts a 60 Hz Nyquist ceiling
 * exactly where foveal CFF sits, before any of the PWM-dimming arguments even
 * apply. The LED has no such ceiling — but `setTorchMode` is a binder round
 * trip, so whether it can switch fast enough is an empirical question about
 * this device.
 *
 * So the instrument measures its own apparatus first and writes the verdict
 * either way. If the LED cannot be driven fast enough for a real staircase,
 * that is a finding worth having in the log, not a reason to ship a UI that
 * measures the binder.
 */
@Composable
private fun TorchCffEngine(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val startedAt = remember { System.currentTimeMillis() }
    var feasibleHz by remember { mutableStateOf<Double?>(null) }
    var switchMs by remember { mutableStateOf(0.0) }

    LaunchedEffect(Unit) {
        val cm = ctx.getSystemService(CameraManager::class.java)
        val id = cm?.cameraIdList?.firstOrNull { camId ->
            cm.getCameraCharacteristics(camId)
                .get(android.hardware.camera2.CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
        }
        if (cm == null || id == null) {
            RunRecord.write(
                ctx,
                instrument,
                startedAt,
                mapOf("feasible" to false, "reason" to "no torch on this device"),
            )
            onDone(
                Outcome("feasibility", null, "", true, emptyMap(), "no torch — instrument not viable")
            )
            return@LaunchedEffect
        }
        // Measure the switch cost before trusting it with a threshold.
        val samples = 40
        val t0 = System.nanoTime()
        repeat(samples) { i ->
            try {
                cm.setTorchMode(id, i % 2 == 0)
            } catch (e: Exception) {
                // A torch busy with the camera is a normal refusal, not a fault.
            }
        }
        try {
            cm.setTorchMode(id, false)
        } catch (e: Exception) {
            // ditto
        }
        switchMs = (System.nanoTime() - t0) / 1_000_000.0 / samples
        // A usable staircase needs headroom above foveal CFF (~60 Hz), so the
        // switch has to cost well under half a period at the top of the range.
        val achievable = if (switchMs <= 0) 0.0 else 1000.0 / (2 * switchMs)
        feasibleHz = achievable
        RunRecord.write(
            ctx,
            instrument,
            startedAt,
            mapOf(
                "feasible" to (achievable >= 70.0),
                "switch_ms" to switchMs,
                "achievable_hz" to achievable,
                "reason" to if (achievable >= 70.0) "torch switching is fast enough" else
                    "torch switching caps the stimulus below foveal CFF",
            ),
        )
        onDone(
            Outcome(
                primaryLabel = "achievable_hz",
                primary = achievable,
                primaryUnit = "Hz ceiling",
                lowerIsBetter = false,
                fields = emptyMap(),
                note =
                    "%.2f ms per switch — %s".format(
                        switchMs,
                        if (achievable >= 70.0) "a staircase is viable here"
                        else "below foveal CFF; the threshold would measure the binder, not the eye",
                    ),
            )
        )
    }

    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Text(
            "measuring the torch…",
            style = MaterialTheme.typography.bodyMedium,
            color = Palette.TextDim,
        )
    }
}
