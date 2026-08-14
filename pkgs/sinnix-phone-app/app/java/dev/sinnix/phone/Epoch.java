package dev.sinnix.phone;

import android.content.Context;
import android.os.Build;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;

/**
 * The apparatus a measurement was taken on.
 *
 * <p>A reaction time is a property of a person *and* a device: the panel's
 * refresh rate, the digitizer's sampling, the OS build's input path. Comparing
 * results across a changed apparatus measures the apparatus. So every result
 * carries an epoch id, and results are only comparable within one.
 *
 * <p>An epoch is {@link Build#FINGERPRINT} plus the measured touch-latency
 * offset. When the fingerprint changes -- an OS update, a different device --
 * the epoch is invalidated and the offset must be measured again; the app says
 * so rather than silently carrying the old number forward.
 *
 * <p>This is deliberately NOT a device profile. An earlier design carried a
 * per-sample-rate verdict table here, on the theory that a rate could be
 * accepted by the recorder and return silence. That was false, and a record
 * shaped around a false theory is worse than no record. Sample rates are the
 * recorder's business; this file is the instruments'.
 */
final class Epoch {

  private static final String FILE_NAME = "epoch.json";
  private static final String SCHEMA = "sinnix.phone.epoch/1";

  /** Touch offset is unknown until the tick-and-tap calibration has run. */
  static final int UNCALIBRATED = -1;

  final String id;
  final String fingerprint;
  final String openedAt;
  final int touchOffsetMs;
  final int touchOffsetSdMs;

  private Epoch(String id, String fingerprint, String openedAt, int offset, int sd) {
    this.id = id;
    this.fingerprint = fingerprint;
    this.openedAt = openedAt;
    this.touchOffsetMs = offset;
    this.touchOffsetSdMs = sd;
  }

  boolean isCalibrated() {
    return touchOffsetMs != UNCALIBRATED;
  }

  /** True when this record describes a different apparatus than the one running. */
  boolean invalidated() {
    return !Build.FINGERPRINT.equals(fingerprint);
  }

  /**
   * The current epoch, opening a new one if the apparatus changed.
   *
   * <p>Opening is cheap and always safe: it records what the device is now.
   * What it deliberately does not do is inherit the previous offset, because
   * the offset is the part that a firmware change is most likely to move.
   */
  static Epoch current(Context ctx) {
    Epoch stored = read(ctx);
    if (stored != null && !stored.invalidated()) {
      return stored;
    }
    int generation = 1;
    if (stored != null) {
      // Epoch ids are e1, e2, ... -- an ordinal, not a hash, because they are
      // printed on results and a human has to be able to say "that was e3".
      try {
        generation = Integer.parseInt(stored.id.substring(1)) + 1;
      } catch (RuntimeException ignored) {
        generation = 2;
      }
      Events.record(
          ctx,
          "epoch_invalidated",
          "from", stored.id,
          "was_fingerprint", stored.fingerprint,
          "now_fingerprint", Build.FINGERPRINT);
    }
    Epoch opened =
        new Epoch(
            "e" + generation,
            Build.FINGERPRINT,
            Status.utcStamp(System.currentTimeMillis()),
            UNCALIBRATED,
            UNCALIBRATED);
    opened.write(ctx);
    Events.record(ctx, "epoch_opened", "epoch", opened.id, "fingerprint", opened.fingerprint);
    return opened;
  }

  /** Record a completed touch-latency calibration against this epoch. */
  Epoch withTouchOffset(Context ctx, int meanMs, int sdMs) {
    Epoch next = new Epoch(id, fingerprint, openedAt, meanMs, sdMs);
    next.write(ctx);
    Events.record(ctx, "epoch_calibrated", "epoch", id, "touch_offset_ms", meanMs, "sd_ms", sdMs);
    return next;
  }

  private static File file(Context ctx) {
    File dir = Storage.estateDir(ctx, null);
    return dir == null ? null : new File(dir, FILE_NAME);
  }

  static Epoch read(Context ctx) {
    File f = file(ctx);
    if (f == null || !f.isFile()) {
      return null;
    }
    StringBuilder sb = new StringBuilder();
    try (RandomAccessFile in = new RandomAccessFile(f, "r")) {
      String line;
      while ((line = in.readLine()) != null) {
        sb.append(line);
      }
    } catch (IOException e) {
      Log.w(AmbientService.TAG, "could not read " + FILE_NAME, e);
      return null;
    }
    try {
      JSONObject o = new JSONObject(sb.toString());
      return new Epoch(
          o.optString("epoch", "e1"),
          o.optString("fingerprint", ""),
          o.optString("opened_at", ""),
          o.optInt("touch_offset_ms", UNCALIBRATED),
          o.optInt("touch_offset_sd_ms", UNCALIBRATED));
    } catch (JSONException e) {
      Log.w(AmbientService.TAG, FILE_NAME + " is not readable JSON", e);
      return null;
    }
  }

  private void write(Context ctx) {
    File f = file(ctx);
    if (f == null) {
      return;
    }
    JSONObject o = new JSONObject();
    try {
      o.put("schema", SCHEMA);
      o.put("epoch", id);
      o.put("fingerprint", fingerprint);
      o.put("opened_at", openedAt);
      o.put("touch_offset_ms", touchOffsetMs);
      o.put("touch_offset_sd_ms", touchOffsetSdMs);
    } catch (JSONException e) {
      Log.w(AmbientService.TAG, "could not render " + FILE_NAME, e);
      return;
    }
    // Same atomic shape as status.json: a reader must never see half a record.
    File tmp = new File(f.getParentFile(), FILE_NAME + ".tmp");
    try (FileOutputStream out = new FileOutputStream(tmp)) {
      out.write(o.toString(2).getBytes(StandardCharsets.UTF_8));
    } catch (IOException | JSONException e) {
      Log.w(AmbientService.TAG, "could not write " + FILE_NAME, e);
      return;
    }
    if (!tmp.renameTo(f)) {
      Log.w(AmbientService.TAG, "could not replace " + FILE_NAME);
    }
  }
}
