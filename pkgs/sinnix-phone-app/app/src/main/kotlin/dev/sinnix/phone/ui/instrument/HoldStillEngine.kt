package dev.sinnix.phone.ui.instrument

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.ImageReader
import android.graphics.ImageFormat
import android.os.Handler
import android.os.HandlerThread
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.instruments.Instrument
import dev.sinnix.phone.instruments.RunRecord
import dev.sinnix.phone.sync.Outbox
import dev.sinnix.phone.ui.HoldRing
import dev.sinnix.phone.ui.theme.Palette
import java.io.File
import kotlinx.coroutines.delay
import org.json.JSONObject

/**
 * One capture pattern, three measurements: finger PPG, tremor spectrum,
 * postural sway.
 *
 * All three are "hold something still for N seconds and stream a trace", and
 * none of them is scored here. The phone owns stimulus timing and raw signal;
 * prime owns the model. That split falls out of not shipping ML, and it is the
 * right architecture anyway — a live heart-rate readout would invite exactly
 * the realtime self-steering this design excludes.
 *
 * The trace leaves as a blob in the outbox with a JSON sidecar; a receipt
 * comes back when prime has scored it.
 *
 * Frame timestamps are recorded per sample rather than assumed from a nominal
 * rate. A PPG trace timed by "30 fps, probably" is a trace whose heart-rate
 * variability is the camera's jitter.
 */
@Composable
fun HoldStillEngine(instrument: Instrument, onDone: (Outcome) -> Unit) {
    val ctx = LocalContext.current
    val startedAt = remember { System.currentTimeMillis() }
    val durationMs = (instrument.config["duration_ms"] as? Int) ?: 30_000
    val mode = instrument.config["mode"]?.toString() ?: "imu"

    var progress by remember { mutableStateOf(0f) }
    var samples by remember { mutableStateOf(0) }
    var failure by remember { mutableStateOf<String?>(null) }

    val collector = remember { TraceCollector(ctx, mode) }

    DisposableEffect(Unit) {
        val started = collector.start { failure = it }
        if (!started && failure == null) failure = "could not start the sensor"
        onDispose { collector.stop() }
    }

    LaunchedEffect(Unit) {
        val step = 100L
        var elapsed = 0L
        while (elapsed < durationMs && failure == null) {
            delay(step)
            elapsed += step
            progress = elapsed.toFloat() / durationMs
            samples = collector.count()
        }
        collector.stop()
        if (failure != null) {
            RunRecord.write(ctx, instrument, startedAt, mapOf("failed" to failure))
            onDone(Outcome("", null, "", true, emptyMap(), failure ?: "failed"))
            return@LaunchedEffect
        }
        val blob = collector.flush(instrument)
        RunRecord.write(
            ctx,
            instrument,
            startedAt,
            mapOf(
                "mode" to mode,
                "samples" to collector.count(),
                "trace_file" to (blob?.name ?: JSONObject.NULL),
                "duration_ms" to durationMs,
            ),
        )
        onDone(
            Outcome(
                primaryLabel = "",
                primary = null,
                primaryUnit = "",
                lowerIsBetter = true,
                fields = emptyMap(),
                note = "${collector.count()} samples handed to prime",
            )
        )
    }

    Column(
        Modifier.fillMaxSize().padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(Modifier.size(180.dp), contentAlignment = Alignment.Center) {
            HoldRing(progress, Modifier.fillMaxSize())
            Text(
                "${((1f - progress) * durationMs / 1000).toInt()}",
                style = MaterialTheme.typography.displaySmall,
                color = Palette.TextDim,
            )
        }
        Text(
            failure ?: instrument.blurb,
            style = MaterialTheme.typography.bodyMedium,
            color = if (failure != null) Palette.Broken else Palette.TextDim,
        )
        Text(
            "$samples samples",
            style = MaterialTheme.typography.labelSmall,
            color = Palette.TextFaint,
        )
    }
}

/**
 * Collects a trace and writes it as CSV next to a JSON sidecar.
 *
 * CSV rather than JSON for the samples: a sixty-second PPG trace is tens of
 * thousands of rows, and a JSON array of objects would triple the bytes the
 * drain has to move for no gain — prime reads it with one pandas call either
 * way.
 */
private class TraceCollector(private val ctx: Context, private val mode: String) {

    private val rows = StringBuilder()
    private var n = 0
    private var sensorManager: SensorManager? = null
    private var listener: SensorEventListener? = null
    private var cameraThread: HandlerThread? = null
    private var camera: CameraDevice? = null
    private var reader: ImageReader? = null

    fun count(): Int = n

    fun start(onFailure: (String) -> Unit): Boolean =
        when (mode) {
            "ppg" -> startPpg(onFailure)
            else -> startImu()
        }

    private fun startImu(): Boolean {
        val sm = ctx.getSystemService(SensorManager::class.java) ?: return false
        val accel = sm.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) ?: return false
        val gyro = sm.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
        rows.append("t_ns,sensor,x,y,z\n")
        val l =
            object : SensorEventListener {
                override fun onSensorChanged(e: SensorEvent) {
                    // The event's own timestamp, not the delivery time: tremor
                    // is a frequency measurement, and jitter introduced by the
                    // main looper would land in the spectrum as signal.
                    rows.append(e.timestamp)
                        .append(',')
                        .append(if (e.sensor.type == Sensor.TYPE_GYROSCOPE) "gyro" else "accel")
                        .append(',')
                        .append(e.values[0])
                        .append(',')
                        .append(e.values[1])
                        .append(',')
                        .append(e.values[2])
                        .append('\n')
                    n++
                }

                override fun onAccuracyChanged(s: Sensor?, a: Int) {}
            }
        // SENSOR_DELAY_FASTEST: tremor sits at 4–12 Hz and physiological
        // components run to ~25 Hz, so the usual 50 Hz UI rate is right at the
        // edge of aliasing the thing being measured.
        sm.registerListener(l, accel, SensorManager.SENSOR_DELAY_FASTEST)
        gyro?.let { sm.registerListener(l, it, SensorManager.SENSOR_DELAY_FASTEST) }
        sensorManager = sm
        listener = l
        return true
    }

    @Suppress("MissingPermission")
    private fun startPpg(onFailure: (String) -> Unit): Boolean {
        val cm = ctx.getSystemService(CameraManager::class.java) ?: return false
        val id =
            cm.cameraIdList.firstOrNull {
                cm.getCameraCharacteristics(it)
                    .get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK
            } ?: return false
        rows.append("t_ns,mean_r,mean_g,mean_b\n")
        val thread = HandlerThread("ppg").apply { start() }
        val handler = Handler(thread.looper)
        cameraThread = thread
        // Small frames on purpose: this measures the mean of a channel, and a
        // 12-megapixel frame gives the same mean as a thumbnail at a hundred
        // times the cost per sample.
        val ir = ImageReader.newInstance(320, 240, ImageFormat.YUV_420_888, 4)
        reader = ir
        ir.setOnImageAvailableListener({ r ->
            val image = r.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val y = image.planes[0].buffer
                var sum = 0L
                var i = 0
                while (i < y.remaining()) {
                    sum += (y.get(i).toInt() and 0xFF)
                    i += 16 // every sixteenth byte: the mean is stable long before every pixel is read
                }
                val count = (y.remaining() / 16).coerceAtLeast(1)
                rows.append(image.timestamp).append(',').append(sum / count).append(",,\n")
                n++
            } finally {
                image.close()
            }
        }, handler)

        return try {
            cm.openCamera(
                id,
                object : CameraDevice.StateCallback() {
                    override fun onOpened(device: CameraDevice) {
                        camera = device
                        val request =
                            device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply {
                                addTarget(ir.surface)
                                // The torch is the light source. Finger PPG
                                // without it measures ambient light through a
                                // finger, which is a different and much worse
                                // signal.
                                set(CaptureRequest.FLASH_MODE, CaptureRequest.FLASH_MODE_TORCH)
                                set(
                                    CaptureRequest.CONTROL_AE_MODE,
                                    CaptureRequest.CONTROL_AE_MODE_OFF,
                                )
                            }
                        @Suppress("DEPRECATION")
                        device.createCaptureSession(
                            listOf(ir.surface),
                            object : android.hardware.camera2.CameraCaptureSession.StateCallback() {
                                override fun onConfigured(
                                    session: android.hardware.camera2.CameraCaptureSession
                                ) {
                                    session.setRepeatingRequest(request.build(), null, handler)
                                }

                                override fun onConfigureFailed(
                                    session: android.hardware.camera2.CameraCaptureSession
                                ) {
                                    onFailure("camera session refused")
                                }
                            },
                            handler,
                        )
                    }

                    override fun onDisconnected(device: CameraDevice) {
                        device.close()
                        camera = null
                    }

                    override fun onError(device: CameraDevice, error: Int) {
                        device.close()
                        camera = null
                        onFailure("camera error $error")
                    }
                },
                handler,
            )
            true
        } catch (e: SecurityException) {
            onFailure("camera permission not granted")
            false
        } catch (e: Exception) {
            onFailure("camera unavailable: ${e.message}")
            false
        }
    }

    fun stop() {
        listener?.let { sensorManager?.unregisterListener(it) }
        listener = null
        camera?.close()
        camera = null
        reader?.close()
        reader = null
        cameraThread?.quitSafely()
        cameraThread = null
    }

    /** Write the trace and its sidecar into the outbox for the drain to collect. */
    fun flush(instrument: Instrument): File? {
        if (n == 0) return null
        val blob = Outbox.blobFile(ctx, "trace-${instrument.id}", "csv") ?: return null
        return try {
            blob.writeText(rows.toString())
            Outbox.writeSidecar(
                ctx,
                blob,
                JSONObject()
                    .put("kind", "trace")
                    .put("instrument", instrument.id)
                    .put("mode", mode)
                    .put("samples", n)
                    .put("recorded_at", Stamps.iso(System.currentTimeMillis())),
            )
            blob
        } catch (e: Exception) {
            null
        }
    }
}
