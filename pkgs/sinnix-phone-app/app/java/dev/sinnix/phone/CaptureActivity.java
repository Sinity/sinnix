package dev.sinnix.phone;

import android.content.Intent;
import android.os.Bundle;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.File;
import java.io.RandomAccessFile;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Capture, diagnosable.
 *
 * <p>This is one of the two screens that carries trust grades, and it carries
 * them because the distinction is real here: a chunk with a perfect duration,
 * a full bitrate and a valid container can contain nothing at all. Rendering
 * "measured OK" identically to "assumed OK" would hide precisely the failure
 * this screen exists to surface.
 *
 * <p>The open chunk is never green. It renders as in-progress with its live
 * amplitude, because a chunk that has not been closed has not been judged.
 */
public final class CaptureActivity extends Screen {

  private static final int CHUNKS_SHOWN = 12;

  private LinearLayout root;
  private LinearLayout statusCard;
  private LinearLayout chunkCard;
  private LinearLayout holeCard;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    root = mount();
    root.addView(backRow());

    statusCard = card();
    root.addView(statusCard);
    root.addView(spacer(dp(12)));

    root.addView(sectionLabel("chunks"));
    chunkCard = column();
    root.addView(chunkCard);
    root.addView(spacer(dp(12)));

    root.addView(sectionLabel("holes"));
    holeCard = column();
    root.addView(holeCard);
    root.addView(spacer(dp(12)));

    root.addView(lakeCard());
    root.addView(spacer(dp(16)));
    root.addView(stopRow());
  }

  @Override
  protected void onResume() {
    super.onResume();
    refresh();
  }

  private TextView sectionLabel(String s) {
    TextView t = mono(s.toUpperCase(), 10, TEXT_GHOST);
    t.setPadding(0, 0, 0, dp(6));
    return t;
  }

  private void refresh() {
    statusCard.removeAllViews();
    chunkCard.removeAllViews();
    holeCard.removeAllViews();

    JSONObject status = readStatus();
    buildStatus(status);
    buildChunks();
    buildHoles();
  }

  /**
   * status.json is the service's own account of itself, read rather than
   * asked for: the service may be in another process, and a file it rewrites
   * every 20s is a cheaper and more honest source than a binder call that
   * could answer while the recorder is wedged.
   */
  private JSONObject readStatus() {
    File dir = Storage.chunkDir(this);
    if (dir == null) {
      return null;
    }
    File f = new File(dir, "status.json");
    if (!f.isFile()) {
      return null;
    }
    StringBuilder sb = new StringBuilder();
    try (RandomAccessFile in = new RandomAccessFile(f, "r")) {
      String line;
      while ((line = in.readLine()) != null) {
        sb.append(line);
      }
      return new JSONObject(sb.toString());
    } catch (Exception e) {
      return null;
    }
  }

  private void buildStatus(JSONObject s) {
    if (s == null) {
      statusCard.addView(mono("no status.json — the service has never run here", 12, Grade.BROKEN.color));
      return;
    }
    long updated = Coverage.parseStamp(s.optString("updated_at"));
    long ageSec = updated == 0 ? -1 : (System.currentTimeMillis() - updated) / 1000L;
    boolean recording = s.optBoolean("recording", false);
    boolean muted = s.optBoolean("muted", false);
    int amplitude = s.optInt("last_amplitude", -1);

    // Liveness is judged from the heartbeat's age, never from the file merely
    // existing: a stale status.json still claims recording=true, and that
    // claim is exactly what a dead recorder leaves behind.
    Grade live = Grade.of(ageSec >= 0, ageSec >= 0 && ageSec < 90);
    kv("heartbeat", ageSec < 0 ? "never" : ageSec + "s ago", live);
    kv("recording", String.valueOf(recording), Grade.of(true, recording && !muted));
    kv("microphone", muted ? "muted — producing no sample" : "producing sound",
        Grade.of(amplitude >= 0, !muted));
    kv("amplitude", amplitude < 0 ? "unknown" : String.valueOf(amplitude), Grade.of(amplitude >= 0, amplitude > 0));
    kv("rate", s.optInt("sampling_rate", 0) + " Hz", Grade.EVIDENCED);
    kv("chunk", s.optString("current_chunk", "none"), Grade.UNVERIFIED);
    kv("elapsed", s.optInt("current_chunk_elapsed_seconds", 0) + " of "
        + s.optInt("chunk_seconds_target", 0) + " s", Grade.EVIDENCED);
    kv("closed", String.valueOf(s.optInt("chunks_closed", 0)), Grade.EVIDENCED);
    int failures = s.optInt("failures", 0);
    kv("failures", String.valueOf(failures), Grade.of(true, failures == 0));
    kv("battery", s.optInt("battery_percent", -1) + "%", Grade.EVIDENCED);
  }

  private void kv(String key, String value, Grade grade) {
    LinearLayout r = row();
    TextView k = mono(key, 12, TEXT_GHOST);
    k.setLayoutParams(new LinearLayout.LayoutParams(dp(84), ViewGroup.LayoutParams.WRAP_CONTENT));
    TextView v = mono(grade.glyph + " " + value, 12, grade.color);
    r.addView(k);
    r.addView(v);
    r.setPadding(0, dp(3), 0, dp(3));
    statusCard.addView(r);
  }

  private void buildChunks() {
    List<JSONObject> closed = new ArrayList<>();
    for (JSONObject e : Events.recent(this, 2)) {
      if ("chunk_closed".equals(e.optString("kind"))) {
        closed.add(e);
      }
    }
    if (closed.isEmpty()) {
      chunkCard.addView(mono("no chunk has closed yet", 11, TEXT_FAINT));
      return;
    }
    Collections.reverse(closed);
    int shown = 0;
    for (JSONObject e : closed) {
      if (shown++ >= CHUNKS_SHOWN) {
        break;
      }
      boolean nothing = e.optBoolean("captured_nothing", false);
      Grade g = Grade.of(true, !nothing);
      LinearLayout c = column();
      c.setBackground(gradeBackground(g));
      c.setPadding(dp(10), dp(8), dp(10), dp(8));

      c.addView(mono(g.glyph + " " + e.optString("chunk"), 11, g.color));
      // The evidence line is the point of the row: a name and a size prove
      // nothing, and this is the sentence that separates a real recording
      // from a perfectly-shaped empty one.
      String evidence =
          e.optLong("seconds") + "s · " + (e.optLong("bytes") / 1024) + " KiB · peak "
              + e.optInt("peak_amplitude");
      c.addView(mono(nothing ? evidence + " — captured nothing" : evidence, 11, TEXT_FAINT));

      chunkCard.addView(c);
      chunkCard.addView(spacer(dp(6)));
    }
  }

  private void buildHoles() {
    Coverage coverage = Coverage.of(this, System.currentTimeMillis());
    if (coverage.holes.isEmpty()) {
      holeCard.addView(mono("none in the last 7 days", 11, TEXT_FAINT));
      return;
    }
    for (Coverage.Hole h : coverage.holes) {
      LinearLayout c = column();
      c.setBackground(gradeBackground(Grade.BROKEN));
      c.setPadding(dp(10), dp(8), dp(10), dp(8));
      c.addView(mono(h.hours() + " h from " + Status.isoStamp(h.startMs), 11, Grade.BROKEN.color));
      // A hole with a cause is a fact; a hole without one is a mystery
      // somebody has to reconstruct later, which is how sinnix-hcjq happened.
      c.addView(mono(h.cause, 11, TEXT_FAINT));
      holeCard.addView(c);
      holeCard.addView(spacer(dp(6)));
    }
  }

  private LinearLayout lakeCard() {
    LinearLayout c = card();
    c.addView(mono("LAKE", 10, TEXT_GHOST));
    c.addView(spacer(dp(6)));
    // Visually distinct because it is not the phone's fact: whether the lake
    // holds a chunk is prime's business, and the phone can only report what a
    // drain receipt tells it -- of which there are none yet.
    TextView t = mono(Grade.UNVERIFIED.glyph + " the drain leaves no receipt on the phone", 11, LAKE);
    c.addView(t);
    c.addView(mono("chunks are removed here only after prime holds an identical copy", 11, TEXT_FAINT));
    return c;
  }

  private TextView stopRow() {
    TextView t = text("stop capture", 14, Grade.BROKEN.color);
    t.setBackground(gradeBackground(Grade.BROKEN));
    t.setPadding(dp(12), dp(16), dp(12), dp(16));
    // Deliberately not double-confirmed. A confirmation dialog trains the
    // reflex that dismisses it, and stopping is both visible and reversible
    // from this same screen.
    t.setOnClickListener(
        v -> {
          Intent i = new Intent(this, AmbientService.class);
          i.setAction(AmbientService.ACTION_STOP);
          startService(i);
          Events.record(this, "capture_toggle", "to", "stopped", "by", "capture_screen");
          t.setText("stopped — reopen the app to start again");
        });
    return t;
  }
}
