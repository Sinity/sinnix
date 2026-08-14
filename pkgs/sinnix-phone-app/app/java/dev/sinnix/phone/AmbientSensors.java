package dev.sinnix.phone;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

/**
 * Passive context alongside the audio: ambient light and body motion.
 *
 * <p>Light exposure is the reason this exists. It is the best non-invasive
 * predictor of circadian phase, nothing else in the estate can produce it, and
 * it costs the operator nothing at all -- no prompt, no decision, no screen.
 * Motion comes along because the same listener loop already runs and because
 * "was the phone on a desk or in a pocket" is the covariate that makes a lux
 * reading interpretable.
 *
 * <p>Reduced on the phone, scored on prime. Raw sensor streams are tens of
 * samples a second of very little information; what leaves here is one line a
 * minute carrying the statistics that survive aggregation. Prime holds the
 * history to say what a given lux profile means.
 *
 * <p>Attached to the capture service rather than run on its own schedule: that
 * process is already alive continuously with a wakelock held, so this adds a
 * listener rather than a reason to wake up.
 */
final class AmbientSensors implements SensorEventListener {

  /** One record a minute: fine enough for circadian work, coarse enough to ignore. */
  private static final long WINDOW_MILLIS = 60_000L;

  /**
   * How much of each minute the sensors are actually listened to.
   *
   * <p>Duty-cycled rather than rate-limited because neither lever the API
   * offers works on this device: the sampling period is only a hint and this
   * platform answers every request with 50 Hz, and the BMI220 reports no
   * batching FIFO, so a report-latency window changes nothing. Measured: 3000
   * accelerometer callbacks a minute either way.
   *
   * <p>Ten seconds is plenty to characterise a minute of stillness or motion,
   * and it cuts the callbacks by six. What is lost is a movement that both
   * starts and ends inside the unsampled fifty seconds; what is gained is a
   * lane that can run all day.
   */
  private static final long SAMPLE_WINDOW_MILLIS = 10_000L;

  /** Only a hint on this platform, kept because it costs nothing where it is honoured. */
  private static final int SAMPLING_PERIOD_US = 200_000;

  private final Context ctx;
  private final SensorManager sensors;
  private final Sensor light;
  private final Sensor accelerometer;

  private final Handler handler = new Handler(Looper.getMainLooper());
  private boolean listening;
  private long windowStartedAtMs;

  private int luxSamples;
  private double luxSum;
  private float luxMax = -1f;
  private float luxMin = -1f;

  private int motionSamples;
  private double motionSquares;
  private double motionMax;

  AmbientSensors(Context context) {
    this.ctx = context.getApplicationContext();
    this.sensors = (SensorManager) ctx.getSystemService(Context.SENSOR_SERVICE);
    this.light = sensors == null ? null : sensors.getDefaultSensor(Sensor.TYPE_LIGHT);
    this.accelerometer = sensors == null ? null : sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
  }

  void start() {
    if (sensors == null) {
      return;
    }
    Log.i(
        AmbientService.TAG,
        "sensors: light=" + (light != null) + " accelerometer=" + (accelerometer != null));
    openWindow();
  }

  void stop() {
    handler.removeCallbacksAndMessages(null);
    closeWindow();
  }

  /** Listen for a slice, then sleep until the next minute. */
  private void openWindow() {
    windowStartedAtMs = System.currentTimeMillis();
    if (light != null) {
      sensors.registerListener(this, light, SAMPLING_PERIOD_US);
    }
    if (accelerometer != null) {
      sensors.registerListener(this, accelerometer, SAMPLING_PERIOD_US);
    }
    listening = true;
    handler.postDelayed(this::closeWindow, SAMPLE_WINDOW_MILLIS);
  }

  private void closeWindow() {
    if (!listening) {
      return;
    }
    sensors.unregisterListener(this);
    listening = false;
    flush(System.currentTimeMillis());
    handler.postDelayed(this::openWindow, Math.max(1L, WINDOW_MILLIS - SAMPLE_WINDOW_MILLIS));
  }

  @Override
  public void onSensorChanged(SensorEvent event) {
    switch (event.sensor.getType()) {
      case Sensor.TYPE_LIGHT:
        float lux = event.values[0];
        luxSamples++;
        luxSum += lux;
        if (luxMax < 0 || lux > luxMax) {
          luxMax = lux;
        }
        if (luxMin < 0 || lux < luxMin) {
          luxMin = lux;
        }
        break;
      case Sensor.TYPE_ACCELEROMETER:
        // Magnitude minus gravity: what remains is movement, independent of
        // how the phone happens to be lying. Squared here and rooted at flush
        // so the statistic is an RMS rather than a mean of absolutes.
        double magnitude =
            Math.sqrt(
                event.values[0] * event.values[0]
                    + event.values[1] * event.values[1]
                    + event.values[2] * event.values[2]);
        double residual = Math.abs(magnitude - SensorManager.GRAVITY_EARTH);
        motionSamples++;
        motionSquares += residual * residual;
        if (residual > motionMax) {
          motionMax = residual;
        }
        break;
      default:
        break;
    }
  }

  @Override
  public void onAccuracyChanged(Sensor sensor, int accuracy) {
    // Not recorded: this sensor's accuracy flag says nothing a lux value does
    // not, and a line per transition would be noise in the log.
  }

  /**
   * Close the window and write one record.
   *
   * <p>Silent when nothing was sampled. A minute with no reading is a real
   * observation about the sensor, but writing a row of nulls every minute the
   * phone is idle would bury the ones that carry data.
   */
  private void flush(long now) {
    if (luxSamples > 0 || motionSamples > 0) {
      Events.record(
          ctx,
          "ambient_context",
          "window_seconds", Math.max(1L, (now - windowStartedAtMs) / 1000L),
          "lux_mean", luxSamples == 0 ? null : round(luxSum / luxSamples),
          "lux_min", luxSamples == 0 ? null : round(luxMin),
          "lux_max", luxSamples == 0 ? null : round(luxMax),
          "lux_samples", luxSamples,
          "motion_rms", motionSamples == 0 ? null : round(Math.sqrt(motionSquares / motionSamples)),
          "motion_max", motionSamples == 0 ? null : round(motionMax),
          "motion_samples", motionSamples);
    }
    windowStartedAtMs = now;
    luxSamples = 0;
    luxSum = 0;
    luxMax = -1f;
    luxMin = -1f;
    motionSamples = 0;
    motionSquares = 0;
    motionMax = 0;
  }

  /** Two decimals: lux and m/s^2 are not meaningful past that, and the log is read by humans too. */
  private static double round(double v) {
    return Math.round(v * 100.0) / 100.0;
  }
}
