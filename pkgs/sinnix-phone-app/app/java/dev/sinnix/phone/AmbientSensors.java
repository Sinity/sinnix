package dev.sinnix.phone;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
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

  private final Context ctx;
  private final SensorManager sensors;
  private final Sensor light;
  private final Sensor accelerometer;

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
    windowStartedAtMs = System.currentTimeMillis();
    // SENSOR_DELAY_NORMAL, and nothing faster: the measurand is a minute-scale
    // average, so a higher rate would buy resolution that is discarded on the
    // next line while costing wakeups on a phone that must last the day.
    if (light != null) {
      sensors.registerListener(this, light, SensorManager.SENSOR_DELAY_NORMAL);
    }
    if (accelerometer != null) {
      sensors.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_NORMAL);
    }
    Log.i(
        AmbientService.TAG,
        "sensors: light=" + (light != null) + " accelerometer=" + (accelerometer != null));
  }

  void stop() {
    if (sensors != null) {
      sensors.unregisterListener(this);
    }
    flush(System.currentTimeMillis());
  }

  @Override
  public void onSensorChanged(SensorEvent event) {
    long now = System.currentTimeMillis();
    if (now - windowStartedAtMs >= WINDOW_MILLIS) {
      flush(now);
    }
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
