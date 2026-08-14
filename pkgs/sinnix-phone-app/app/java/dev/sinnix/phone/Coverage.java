package dev.sinnix.phone;

import android.content.Context;

import org.json.JSONObject;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TimeZone;

/**
 * What the last week of capture actually looks like, one cell per hour.
 *
 * <p>A reduction of the event log, not of the chunk directory: chunks leave
 * the phone on the next drain, so a listing answers "what is still here",
 * which is a question about the drain rather than about capture.
 *
 * <p>Hours are graded, not merely present/absent. An hour whose chunks all
 * captured silence is not coverage -- that is the whole lesson of the archive
 * that turned out 29/111 empty -- so it renders as a hole with a cause.
 */
final class Coverage {

  static final int DAYS = 7;
  static final int HOURS = 24;
  static final int CELLS = DAYS * HOURS;

  /** No chunk claimed this hour. Before the app was installed, this is simply unknown. */
  static final int UNKNOWN = 0;

  /** Chunks closed in this hour and carried sound. */
  static final int COVERED = 1;

  /** Chunks closed, and every one of them was silent. */
  static final int SILENT = 2;

  /** Bounded by two covered hours with nothing between them: a real gap. */
  static final int HOLE = 3;

  /** One contiguous run of hours that captured nothing, with what is known about why. */
  static final class Hole {
    final long startMs;
    final long endMs;
    final String cause;

    Hole(long startMs, long endMs, String cause) {
      this.startMs = startMs;
      this.endMs = endMs;
      this.cause = cause;
    }

    long hours() {
      return Math.max(1L, (endMs - startMs) / 3_600_000L);
    }
  }

  final int[] cells = new int[CELLS];
  final List<Hole> holes = new ArrayList<>();

  /** UTC hour the first cell represents. */
  final long originMs;

  private Coverage(long originMs) {
    this.originMs = originMs;
  }

  private static SimpleDateFormat stampFormat() {
    SimpleDateFormat f = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
    f.setTimeZone(TimeZone.getTimeZone("UTC"));
    return f;
  }

  /**
   * Parse either timestamp shape the log contains.
   *
   * <p>Records written before 2026-08-14 carry the compact filename stamp
   * ({@code 20260814T002141Z}) because the event writer reached for the wrong
   * helper; everything since carries extended ISO. The log is append-only, so
   * the old lines cannot be rewritten -- and a reducer that silently returned
   * 0 for them would drop real coverage on the floor and show an empty ribbon
   * over a week that was fully captured.
   */
  static long parseStamp(String stamp) {
    if (stamp == null || stamp.isEmpty()) {
      return 0L;
    }
    SimpleDateFormat fmt = stamp.indexOf('-') > 0 ? stampFormat() : compactStampFormat();
    try {
      return fmt.parse(stamp).getTime();
    } catch (ParseException e) {
      return 0L;
    }
  }

  private static SimpleDateFormat compactStampFormat() {
    SimpleDateFormat f = new SimpleDateFormat("yyyyMMdd'T'HHmmss'Z'", Locale.US);
    f.setTimeZone(TimeZone.getTimeZone("UTC"));
    return f;
  }

  private static long hourFloor(long ms) {
    return ms - (ms % 3_600_000L);
  }

  /** Reduce the week's events. {@code nowMs} is the last cell. */
  static Coverage of(Context ctx, long nowMs) {
    long origin = hourFloor(nowMs) - (CELLS - 1L) * 3_600_000L;
    Coverage c = new Coverage(origin);

    boolean[] sawChunk = new boolean[CELLS];
    boolean[] sawSound = new boolean[CELLS];

    for (JSONObject e : Events.recent(ctx, DAYS + 1)) {
      if (!"chunk_closed".equals(e.optString("kind"))) {
        continue;
      }
      long startedAt = parseStamp(e.optString("started_at"));
      if (startedAt == 0L) {
        startedAt = parseStamp(e.optString("ts"));
      }
      int idx = (int) ((hourFloor(startedAt) - origin) / 3_600_000L);
      if (idx < 0 || idx >= CELLS) {
        continue;
      }
      sawChunk[idx] = true;
      if (!e.optBoolean("captured_nothing", false)) {
        sawSound[idx] = true;
      }
    }

    // An hour with no chunk only counts as a hole once capture has been seen
    // on both sides of it. Leading emptiness is the time before the app
    // existed, and trailing emptiness is usually the hour still in progress --
    // neither is a failure, and calling them one would make the ribbon cry
    // wolf on every fresh install.
    int first = -1;
    int last = -1;
    for (int i = 0; i < CELLS; i++) {
      if (sawChunk[i]) {
        if (first < 0) {
          first = i;
        }
        last = i;
      }
    }

    for (int i = 0; i < CELLS; i++) {
      if (sawChunk[i]) {
        c.cells[i] = sawSound[i] ? COVERED : SILENT;
      } else if (first >= 0 && i > first && i < last) {
        c.cells[i] = HOLE;
      } else {
        c.cells[i] = UNKNOWN;
      }
    }

    c.collectHoles();
    return c;
  }

  /**
   * Holes as objects rather than as gaps someone has to spot.
   *
   * <p>A silent run and an absent run are both holes, and they get different
   * causes because they need different fixes: one is a recorder that was never
   * running, the other a recorder that was running and being fed nothing.
   */
  private void collectHoles() {
    int i = 0;
    while (i < CELLS) {
      int state = cells[i];
      if (state != HOLE && state != SILENT) {
        i++;
        continue;
      }
      int j = i;
      while (j + 1 < CELLS && cells[j + 1] == state) {
        j++;
      }
      long start = originMs + i * 3_600_000L;
      long end = originMs + (j + 1L) * 3_600_000L;
      holes.add(
          new Hole(
              start,
              end,
              state == SILENT
                  ? "recorder running, microphone produced no sample"
                  : "no chunk closed in this window"));
      i = j + 1;
    }
  }

  int coveredHours() {
    int n = 0;
    for (int cell : cells) {
      if (cell == COVERED) {
        n++;
      }
    }
    return n;
  }

  int knownHours() {
    int n = 0;
    for (int cell : cells) {
      if (cell != UNKNOWN) {
        n++;
      }
    }
    return n;
  }
}
