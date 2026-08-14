package dev.sinnix.phone;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.Build;
import android.os.PowerManager;
import android.util.Log;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;

/**
 * Desktop-observable liveness.
 *
 * <p>Writes {@code status.json} next to the chunks. That location is
 * deliberate: it rides the same drain path the audio already uses, so the
 * desktop can answer "is capture alive and producing?" over the existing ssh
 * surface with no extra listening port on a phone that roams networks.
 *
 * <p>The distinction that matters is alive-and-producing versus merely
 * installed. Both the closed-chunk history and the growth of the file
 * currently open are reported, because a recorder that is running while the
 * platform feeds it silence looks identical to a healthy one from the outside.
 */
final class Status {

  private static final String FILE_NAME = "status.json";
  private static final String SCHEMA = "sinnix.phone.ambient/1";

  /** A chunk file that has not grown in this long is not really recording. */
  private static final long STALL_MILLIS = 90_000L;

  /**
   * Consecutive zero-amplitude heartbeats before the microphone counts as
   * muted. Four samples is 80s at the current cadence -- long enough that a
   * momentary handover between audio clients does not trip it, short enough
   * that a chunk is never mostly silence before anyone notices.
   */
  private static final int MUTED_SAMPLES = 4;

  private Context ctx;

  private long serviceStartedAtMs;
  private String currentChunk;
  private long currentChunkStartedAtMs;
  private long currentChunkBytes;
  private int samplingRate;

  private String lastChunk;
  private long lastChunkSeconds;
  private long lastChunkBytes;
  private long lastChunkClosedAtMs;
  private int lastChunkPeakAmplitude;

  private int chunksClosed;
  private int failures;
  private String lastError;
  private long lastErrorAtMs;

  private long lastGrowthAtMs;
  private long lastObservedBytes = -1;
  private boolean recording;

  private int lastAmplitude = -1;
  private int chunkPeakAmplitude;
  private int silentSamples;

  synchronized void attach(Context context) {
    this.ctx = context.getApplicationContext();
  }

  synchronized void serviceStarted() {
    serviceStartedAtMs = System.currentTimeMillis();
    write();
  }

  synchronized void serviceStopped() {
    recording = false;
    currentChunk = null;
    write();
  }

  synchronized void chunkOpened(File part, long startedAtMs, int rate) {
    currentChunk = part.getName();
    currentChunkStartedAtMs = startedAtMs;
    currentChunkBytes = 0;
    samplingRate = rate;
    recording = true;
    lastObservedBytes = -1;
    lastGrowthAtMs = startedAtMs;
    chunkPeakAmplitude = 0;
    silentSamples = 0;
    lastAmplitude = -1;
    write();
  }

  /**
   * Peak amplitude seen during the open chunk.
   *
   * <p>Read before {@link #chunkClosed}, which rolls it into the last-chunk
   * fields and starts the next one over. Zero across a whole chunk means the
   * microphone produced no sample at all -- the failure that looks exactly
   * like success from the file's side.
   */
  synchronized int chunkPeak() {
    return chunkPeakAmplitude;
  }

  synchronized void chunkClosed(File file, long startedAtMs, long closedAtMs) {
    lastChunk = file.getName();
    lastChunkBytes = file.length();
    lastChunkSeconds = Math.max(0L, (closedAtMs - startedAtMs) / 1000L);
    lastChunkClosedAtMs = closedAtMs;
    lastChunkPeakAmplitude = chunkPeakAmplitude;
    chunksClosed++;
    recording = false;
    currentChunk = null;
    write();
  }

  synchronized void heartbeat(long currentBytes, long elapsedSeconds, int amplitude) {
    currentChunkBytes = currentBytes;
    if (currentBytes > lastObservedBytes) {
      lastObservedBytes = currentBytes;
      lastGrowthAtMs = System.currentTimeMillis();
    }
    if (amplitude >= 0) {
      lastAmplitude = amplitude;
      if (amplitude > chunkPeakAmplitude) {
        chunkPeakAmplitude = amplitude;
      }
      // Exactly zero, not "low". A working microphone reports its own noise
      // floor even in a silent room; a run of exact zeroes is the platform
      // substituting silence for audio it decided not to give us.
      if (amplitude == 0) {
        silentSamples++;
      } else {
        silentSamples = 0;
      }
    }
    write();
  }

  synchronized void recordFailure(String detail) {
    failures++;
    lastError = detail;
    lastErrorAtMs = System.currentTimeMillis();
    recording = false;
    write();
  }

  /** True when a chunk is nominally open but its file has stopped growing. */
  synchronized boolean stalled() {
    if (!recording || lastGrowthAtMs == 0) {
      return false;
    }
    return System.currentTimeMillis() - lastGrowthAtMs > STALL_MILLIS;
  }

  /** True when the recorder is nominally running but the microphone reads as silence. */
  synchronized boolean muted() {
    return recording && silentSamples >= MUTED_SAMPLES;
  }

  synchronized int chunksClosed() {
    return chunksClosed;
  }

  synchronized String lastErrorShort() {
    if (lastError == null) {
      return "idle";
    }
    return lastError.length() > 80 ? lastError.substring(0, 80) : lastError;
  }

  // --- serialisation -----------------------------------------------------

  private void write() {
    if (ctx == null) {
      return;
    }
    File dir = Storage.chunkDir(ctx);
    if (dir == null) {
      return;
    }
    JSONObject o = new JSONObject();
    try {
      o.put("schema", SCHEMA);
      o.put("app_version", BuildId.VERSION);
      o.put("package", ctx.getPackageName());
      o.put("updated_at", isoStamp(System.currentTimeMillis()));
      o.put("service_running", AmbientService.running);
      o.put("recording", recording);
      o.put("chunk_dir", dir.getAbsolutePath());
      o.put("chunk_dir_is_shared", Storage.SHARED_DIR.equals(dir.getAbsolutePath()));
      o.put("all_files_access", Storage.haveAllFilesAccess());
      o.put("chunk_seconds_target", AmbientService.CHUNK_MILLIS / 1000L);
      o.put("sampling_rate", samplingRate);
      o.put("service_started_at", isoOrNull(serviceStartedAtMs));
      o.put("uptime_seconds", serviceStartedAtMs == 0 ? 0 : (System.currentTimeMillis() - serviceStartedAtMs) / 1000L);
      o.put("current_chunk", currentChunk == null ? JSONObject.NULL : currentChunk);
      o.put("current_chunk_started_at", isoOrNull(currentChunkStartedAtMs));
      o.put("current_chunk_bytes", currentChunkBytes);
      o.put("current_chunk_elapsed_seconds",
          currentChunkStartedAtMs == 0 || !recording
              ? 0
              : (System.currentTimeMillis() - currentChunkStartedAtMs) / 1000L);
      o.put("current_chunk_peak_amplitude", chunkPeakAmplitude);
      o.put("last_amplitude", lastAmplitude);
      o.put("silent_samples", silentSamples);
      o.put("muted", recording && silentSamples >= MUTED_SAMPLES);
      o.put("last_chunk", lastChunk == null ? JSONObject.NULL : lastChunk);
      o.put("last_chunk_seconds", lastChunkSeconds);
      o.put("last_chunk_bytes", lastChunkBytes);
      o.put("last_chunk_closed_at", isoOrNull(lastChunkClosedAtMs));
      o.put("last_chunk_peak_amplitude", lastChunkPeakAmplitude);
      o.put("chunks_closed", chunksClosed);
      o.put("failures", failures);
      o.put("last_error", lastError == null ? JSONObject.NULL : lastError);
      o.put("last_error_at", isoOrNull(lastErrorAtMs));
      o.put("screen_interactive", screenInteractive());
      o.put("battery_percent", batteryPercent());
      o.put("boot_at", isoStamp(System.currentTimeMillis() - android.os.SystemClock.elapsedRealtime()));
    } catch (Exception e) {
      Log.w(AmbientService.TAG, "status assembly failed", e);
      return;
    }

    // Rename-into-place: the desktop polls this file, and a torn read of a
    // half-written JSON document would look like a crashed capture.
    File tmp = new File(dir, FILE_NAME + ".tmp");
    File dest = new File(dir, FILE_NAME);
    try (FileOutputStream out = new FileOutputStream(tmp)) {
      out.write(o.toString(2).getBytes(StandardCharsets.UTF_8));
      out.write('\n');
      out.getFD().sync();
    } catch (IOException | org.json.JSONException e) {
      Log.w(AmbientService.TAG, "status write failed", e);
      return;
    }
    if (!tmp.renameTo(dest)) {
      Log.w(AmbientService.TAG, "status rename failed");
    }
  }

  private boolean screenInteractive() {
    try {
      PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
      return pm != null && pm.isInteractive();
    } catch (Exception e) {
      return false;
    }
  }

  private int batteryPercent() {
    try {
      Intent battery = ctx.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
      if (battery == null) {
        return -1;
      }
      int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
      int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
      return (level < 0 || scale <= 0) ? -1 : Math.round(level * 100f / scale);
    } catch (Exception e) {
      return -1;
    }
  }

  private static Object isoOrNull(long ms) {
    return ms == 0 ? JSONObject.NULL : isoStamp(ms);
  }

  /** Extended ISO-8601, the shape every timestamp FIELD uses (filenames use utcStamp). */
  static String isoStamp(long ms) {
    SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
    f.setTimeZone(TimeZone.getTimeZone("UTC"));
    return f.format(new Date(ms));
  }

  /** Chunk filename stamp, matching the ambient-<UTC ISO basic>.m4a convention in the lake. */
  static String utcStamp(long ms) {
    SimpleDateFormat f = new SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US);
    f.setTimeZone(TimeZone.getTimeZone("UTC"));
    return f.format(new Date(ms));
  }
}
