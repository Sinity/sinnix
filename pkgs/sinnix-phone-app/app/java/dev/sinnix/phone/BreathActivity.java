package dev.sinnix.phone;

import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

/**
 * Breath counting: a measure of meta-awareness, not of attention.
 *
 * <p>Count breaths one to nine, marking the first eight with the large zone
 * and the ninth with the small one, then start again. The task is trivial and
 * that is the point: what it measures is not whether the count is kept but
 * whether losing it is <em>noticed</em>.
 *
 * <p>Two failures are recorded and must never be added together. Pressing
 * "nine" at any position other than nine is a mind that wandered and did not
 * know it. A long press -- "I have lost count" -- is a mind that wandered and
 * caught itself. Their ratio is the quantity worth looking at; an accuracy
 * score built from their sum would rank someone who never notices above
 * someone who notices constantly, which is exactly backwards.
 *
 * <p>Phone-native rather than desktop: it wants to be done away from a screen
 * full of other things, and the timing precision the desktop offers is
 * irrelevant here.
 */
public final class BreathActivity extends Screen {

  private static final int CYCLE = 9;

  private int position = 0;
  private int cyclesCorrect = 0;
  private int unawareMiscounts = 0;
  private int selfCaughtResets = 0;
  private long startedAtMs;

  private TextView counter;
  private TextView tally;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    startedAtMs = System.currentTimeMillis();

    LinearLayout root = mount();
    root.addView(backRow());

    counter = text("1", 72, TEXT_BRIGHT);
    counter.setTypeface(Typeface.MONOSPACE);
    counter.setGravity(Gravity.CENTER);
    counter.setPadding(0, dp(8), 0, dp(16));
    root.addView(counter);

    TextView breath = zone("breath", 150);
    breath.setOnClickListener(v -> onBreath());
    // The same long press on either zone: noticing you are lost is not a
    // different action depending on where your thumb happens to be.
    breath.setOnLongClickListener(v -> onLostCount());
    root.addView(breath);
    root.addView(spacer(dp(10)));

    TextView nine = zone("nine", 90);
    nine.setOnClickListener(v -> onNine());
    nine.setOnLongClickListener(v -> onLostCount());
    root.addView(nine);
    root.addView(spacer(dp(12)));

    tally = mono("", 12, TEXT_FAINT);
    root.addView(tally);
    root.addView(spacer(dp(6)));
    root.addView(
        text(
            "Count each breath. Mark the ninth with the small zone. Hold either"
                + " zone when you notice you have lost count.",
            12,
            TEXT_GHOST));

    render();
  }

  private TextView zone(String label, int heightDp) {
    TextView t = text(label, 18, TEXT);
    t.setGravity(Gravity.CENTER);
    t.setBackground(cardBackground());
    t.setLayoutParams(
        new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(heightDp)));
    return t;
  }

  private void onBreath() {
    position++;
    // Past nine without marking it: the count has run on unnoticed. Recorded
    // when the ninth finally arrives, so it stays one event per cycle.
    render();
  }

  private void onNine() {
    if (position == CYCLE - 1) {
      cyclesCorrect++;
    } else {
      unawareMiscounts++;
    }
    position = 0;
    render();
  }

  private boolean onLostCount() {
    selfCaughtResets++;
    position = 0;
    render();
    return true;
  }

  private void render() {
    counter.setText(String.valueOf(Math.min(position + 1, CYCLE)));
    tally.setText(
        "cycles "
            + cyclesCorrect
            + "   ·   unaware "
            + unawareMiscounts
            + "   ·   self-caught "
            + selfCaughtResets);
  }

  @Override
  protected void onPause() {
    super.onPause();
    // Written on leaving rather than at a fixed length: the session ends when
    // the operator stops, and a run cut short is still a real observation.
    if (cyclesCorrect + unawareMiscounts + selfCaughtResets == 0) {
      return;
    }
    JSONObject o = new JSONObject();
    try {
      o.put("kind", "instrument_run");
      o.put("instrument", "breath_counting");
      o.put("engine", "count");
      o.put("epoch", Epoch.current(this).id);
      o.put("started_at", Status.isoStamp(startedAtMs));
      o.put("seconds", (System.currentTimeMillis() - startedAtMs) / 1000L);
      o.put("cycles_correct", cyclesCorrect);
      // Deliberately separate fields, never summed into an accuracy: the two
      // failures mean opposite things about awareness.
      o.put("unaware_miscounts", unawareMiscounts);
      o.put("self_caught_resets", selfCaughtResets);
    } catch (JSONException e) {
      return;
    }
    Events.append(this, o);
    cyclesCorrect = 0;
    unawareMiscounts = 0;
    selfCaughtResets = 0;
  }
}
