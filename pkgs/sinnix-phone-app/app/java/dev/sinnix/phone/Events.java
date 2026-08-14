package dev.sinnix.phone;

import android.content.Context;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/**
 * The app's own record: append-only JSONL, one file per UTC day.
 *
 * <p>Everything historical the UI shows is a reduction of this -- the
 * continuity ribbon, holes, grant transitions, instrument runs. Append-only
 * because a reducer can always re-read a log, while a file the app rewrites is
 * a file the app can corrupt; and because the drain takes whole files, so a
 * record that is only ever extended is never in a half-written state when it
 * is collected.
 *
 * <p>Each line carries at least {@code kind} and {@code ts}. Unknown kinds are
 * preserved on read rather than dropped: a consumer written before a kind
 * existed should skip it, not lose it.
 */
final class Events {

  private static final String DIR = "events";
  private static final String PREFIX = "events-";
  private static final String SUFFIX = ".jsonl";

  /** A single line longer than this is treated as corruption, not a record. */
  private static final int MAX_LINE_BYTES = 1 << 20;

  private Events() {}

  private static SimpleDateFormat dayFormat() {
    SimpleDateFormat f = new SimpleDateFormat("yyyyMMdd", Locale.US);
    f.setTimeZone(TimeZone.getTimeZone("UTC"));
    return f;
  }

  static File fileFor(Context ctx, long atMs) {
    File dir = Storage.estateDir(ctx, DIR);
    if (dir == null) {
      return null;
    }
    return new File(dir, PREFIX + dayFormat().format(new Date(atMs)) + SUFFIX);
  }

  /**
   * Append one record, stamping {@code ts} when the caller has not.
   *
   * <p>Opened in append mode per call rather than held open: the recorder can
   * be killed at any moment, and a descriptor kept across that boundary buys
   * nothing a 100-byte write needs.
   */
  static void append(Context ctx, JSONObject record) {
    if (record == null) {
      return;
    }
    long now = System.currentTimeMillis();
    try {
      if (!record.has("ts")) {
        record.put("ts", Status.isoStamp(now));
      }
    } catch (JSONException e) {
      Log.w(AmbientService.TAG, "event missing a usable ts", e);
    }
    File file = fileFor(ctx, now);
    if (file == null) {
      return;
    }
    byte[] line = (record.toString() + "\n").getBytes(StandardCharsets.UTF_8);
    try (FileOutputStream out = new FileOutputStream(file, true)) {
      out.write(line);
      // Not fsynced: an event lost to a crash is a missing observation, while
      // an fsync per event on a phone's flash is a durable cost paid forever.
      // The chunks themselves are what get fsynced.
    } catch (IOException e) {
      Log.w(AmbientService.TAG, "could not append event to " + file, e);
    }
  }

  /** Convenience for the common shape: a kind plus flat key/value pairs. */
  static void record(Context ctx, String kind, Object... keyValues) {
    JSONObject o = new JSONObject();
    try {
      o.put("kind", kind);
      for (int i = 0; i + 1 < keyValues.length; i += 2) {
        o.put(String.valueOf(keyValues[i]), keyValues[i + 1]);
      }
    } catch (JSONException e) {
      Log.w(AmbientService.TAG, "could not build event " + kind, e);
      return;
    }
    append(ctx, o);
  }

  /**
   * Records from the last {@code days} UTC day-files, oldest first.
   *
   * <p>Reads by day-file rather than by scanning everything: the ribbon only
   * ever asks for a week, and a log that grows for months should not be walked
   * to answer that.
   */
  static List<JSONObject> recent(Context ctx, int days) {
    List<JSONObject> out = new ArrayList<>();
    SimpleDateFormat fmt = dayFormat();
    Calendar cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"));
    File dir = Storage.estateDir(ctx, DIR);
    if (dir == null) {
      return out;
    }
    cal.add(Calendar.DAY_OF_YEAR, -(days - 1));
    for (int i = 0; i < days; i++) {
      File file = new File(dir, PREFIX + fmt.format(cal.getTime()) + SUFFIX);
      readInto(file, out);
      cal.add(Calendar.DAY_OF_YEAR, 1);
    }
    return out;
  }

  private static void readInto(File file, List<JSONObject> out) {
    if (!file.isFile()) {
      return;
    }
    try (RandomAccessFile in = new RandomAccessFile(file, "r")) {
      String line;
      while ((line = in.readLine()) != null) {
        if (line.isEmpty() || line.length() > MAX_LINE_BYTES) {
          continue;
        }
        // A truncated final line is the normal shape of a log whose writer was
        // killed mid-append. Skip it and keep the rest rather than discarding
        // the file.
        try {
          out.add(new JSONObject(line));
        } catch (JSONException ignored) {
          // not a record; the next line still might be
        }
      }
    } catch (IOException e) {
      Log.w(AmbientService.TAG, "could not read events from " + file, e);
    }
  }
}
