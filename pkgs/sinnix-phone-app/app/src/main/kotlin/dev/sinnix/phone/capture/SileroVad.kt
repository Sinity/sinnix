package dev.sinnix.phone.capture

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.util.Log
import dev.sinnix.phone.core.Storage
import java.io.File
import java.nio.FloatBuffer
import java.nio.LongBuffer

/**
 * Silero VAD, the same model the desktop lane runs.
 *
 * One VAD for the whole estate is worth a dependency. The alternative was an
 * energy threshold, which is not a detector so much as a way of streaming
 * every fridge compressor and passing car to prime — and the point of gating
 * at all is that the phone sends utterances, not hours.
 *
 * The model ships as an app asset rather than being fetched. The speech lane
 * has no network gate by design, so it must be able to start on a phone that
 * is nowhere near the tailnet; a model that needed one download first would
 * have made "always on" mean "always on once you have been home".
 *
 * Silero's contract, which the shapes below encode: 576 samples per window at
 * 16 kHz (36 ms), a carried 2×1×128 state, and one probability out. The state
 * is why this is a class rather than a function — the model is recurrent, and
 * feeding windows through a fresh state each time would make every window a
 * cold start and every boundary wrong.
 */
class SileroVad(ctx: Context) : AutoCloseable {

    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val session: OrtSession
    private var state = FloatArray(2 * 1 * 128)

    init {
        val modelFile = File(ctx.filesDir, MODEL_NAME)
        if (!modelFile.isFile) {
            // Copied out of assets once: ORT wants a path or a byte array, and
            // holding 2 MB of model in memory to re-parse on every service
            // start is worse than one file.
            ctx.assets.open(MODEL_NAME).use { input ->
                modelFile.outputStream().use { output -> input.copyTo(output) }
            }
        }
        session = env.createSession(modelFile.absolutePath, OrtSession.SessionOptions())
        Log.i(Storage.TAG, "silero vad loaded: ${session.inputNames}")
    }

    /** Probability that [window] (exactly [WINDOW] samples, −1..1) is speech. */
    fun probability(window: FloatArray): Float {
        val inputs =
            mapOf(
                "input" to
                    OnnxTensor.createTensor(
                        env,
                        FloatBuffer.wrap(window),
                        longArrayOf(1, window.size.toLong()),
                    ),
                "state" to
                    OnnxTensor.createTensor(
                        env,
                        FloatBuffer.wrap(state),
                        longArrayOf(2, 1, 128),
                    ),
                "sr" to OnnxTensor.createTensor(env, LongBuffer.wrap(longArrayOf(SAMPLE_RATE.toLong())), longArrayOf(1)),
            )
        return try {
            session.run(inputs).use { result ->
                @Suppress("UNCHECKED_CAST")
                val prob = (result[0].value as Array<FloatArray>)[0][0]
                @Suppress("UNCHECKED_CAST")
                val next = result[1].value as Array<Array<FloatArray>>
                var i = 0
                for (a in next) for (b in a) for (v in b) state[i++] = v
                prob
            }
        } catch (e: Exception) {
            Log.w(Storage.TAG, "vad inference failed", e)
            0f
        } finally {
            inputs.values.forEach { it.close() }
        }
    }

    /** Forget the carried state. Used between utterances, not between windows. */
    fun reset() {
        state = FloatArray(2 * 1 * 128)
    }

    override fun close() {
        try {
            session.close()
        } catch (ignored: Exception) {
            // a closed session is the desired end state either way
        }
    }

    companion object {
        const val MODEL_NAME = "silero_vad.onnx"

        /**
         * Silero's window at 16 kHz, and emphatically not a tunable — the
         * model is traced at this size and a different one does not error, it
         * just stops working.
         *
         * v6 moved this from v5's 512 to 576, which is the kind of change that
         * produces no exception and no warning. Measured against known-clean
         * speech through this exact model: at 512 the peak probability over a
         * whole utterance is 0.0028 and nothing ever crosses the threshold; at
         * 576 it is 1.0 and 92% of windows fire. The lane had been listening
         * perfectly and detecting nothing.
         */
        const val WINDOW = 576

        const val SAMPLE_RATE = 16_000
    }
}
