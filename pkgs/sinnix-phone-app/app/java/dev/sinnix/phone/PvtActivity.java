package dev.sinnix.phone;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Choreographer;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * Psychomotor vigilance task.
 *
 * <p>First instrument because it is the one that earns its place hardest: a
 * validated measure, robust to the apparatus, directly sensitive to sleep, and
 * the carrier for the touch-latency calibration every later timing instrument
 * depends on.
 *
 * <p>The whole screen is the response surface. There are no buttons, because a
 * button is a target to aim at and aiming is not what is being measured.
 */
public final class PvtActivity extends Activity {

  /** Classic PVT interstimulus range. Uniform, so the wait is never predictable. */
  private static final int ISI_MIN_MS = 2_000;
  private static final int ISI_MAX_MS = 10_000;

  /** A phone check is minutes, not the clinical ten. */
  private static final int TRIALS = 25;

  /** Above this, the trial is a lapse -- the conventional PVT threshold. */
  private static final int LAPSE_MS = 500;

  /**
   * A stimulus nobody answers is recorded at this ceiling and the run moves
   * on. Without it a missed trial waits forever: the counter climbs, the run
   * never ends, and the operator's only exit is to kill the app -- which
   * throws away every trial already completed.
   */
  private static final int NO_RESPONSE_MS = 10_000;

  private enum Phase {
    /** Waiting out the interstimulus interval; a tap here is a false start. */
    ARMED,
    /** Counter running; a tap here is the response. */
    STIMULUS,
    /** Showing the last result before re-arming. */
    FEEDBACK,
    DONE
  }

  private TrialView view;
  private final Handler handler = new Handler(Looper.getMainLooper());
  private final Random random = new Random();

  private Phase phase = Phase.ARMED;
  private int trial = 0;
  private final List<Integer> reactions = new ArrayList<>();
  private int falseStarts = 0;
  private int interruptions = 0;
  private int discarded = 0;

  /**
   * The frame time at which the stimulus actually became visible.
   *
   * <p>Not the moment the code decided to show it: between those two lies an
   * unknown slice of layout, draw and compositing, and on a 60 Hz panel that
   * is up to a frame of pure bias in every single trial.
   */
  private long stimulusFrameNanos = 0;

  private Epoch epoch;
  private long startedAtMs;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    epoch = Epoch.current(this);
    startedAtMs = System.currentTimeMillis();
    view = new TrialView(this);
    setContentView(view);
    arm();
  }

  @Override
  protected void onPause() {
    super.onPause();
    // An interrupted trial is not a slow trial. A notification shade, a call,
    // or the operator glancing away produces a reaction time that is really a
    // measure of the interruption, and averaging it in would quietly poison
    // the median. The trial is discarded and re-presented at the same index.
    if (phase == Phase.ARMED || phase == Phase.STIMULUS) {
      interruptions++;
      handler.removeCallbacksAndMessages(null);
      phase = Phase.FEEDBACK;
    }
  }

  @Override
  protected void onResume() {
    super.onResume();
    if (phase == Phase.FEEDBACK && trial < TRIALS) {
      arm();
    }
  }

  private void arm() {
    phase = Phase.ARMED;
    stimulusFrameNanos = 0;
    view.invalidate();
    int isi = ISI_MIN_MS + random.nextInt(ISI_MAX_MS - ISI_MIN_MS);
    handler.postDelayed(this::showStimulus, isi);
  }

  private void showStimulus() {
    phase = Phase.STIMULUS;
    view.invalidate();
    // Ask the compositor when this frame is presented, rather than assuming
    // the invalidate() above was instantaneous.
    Choreographer.getInstance()
        .postFrameCallback(
            frameTimeNanos -> {
              if (phase == Phase.STIMULUS && stimulusFrameNanos == 0) {
                stimulusFrameNanos = frameTimeNanos;
                view.startCounter();
                handler.postDelayed(this::onNoResponse, NO_RESPONSE_MS);
              }
            });
  }

  private void onResponse(MotionEvent event) {
    switch (phase) {
      case ARMED:
        // Never punished, only recorded. A PVT that scolds trains the operator
        // to hesitate, which changes the very thing being measured.
        falseStarts++;
        handler.removeCallbacksAndMessages(null);
        view.setMessage("too early");
        phase = Phase.FEEDBACK;
        handler.postDelayed(this::nextOrFinish, 700);
        return;
      case STIMULUS:
        if (stimulusFrameNanos == 0) {
          return;
        }
        // getEventTime() is the digitizer's own timestamp for the touch, not
        // the moment this callback ran; the difference is the input queue,
        // which has nothing to do with the operator.
        long eventNanos = event.getEventTime() * 1_000_000L;
        int raw = (int) ((eventNanos - stimulusFrameNanos) / 1_000_000L);
        int corrected = epoch.isCalibrated() ? raw - epoch.touchOffsetMs : raw;
        if (corrected < 0) {
          corrected = 0;
        }
        reactions.add(corrected);
        trial++;
        view.setMessage(corrected + " ms" + (corrected >= LAPSE_MS ? "  · lapse" : ""));
        phase = Phase.FEEDBACK;
        handler.postDelayed(this::nextOrFinish, 700);
        return;
      default:
        // ignore taps during feedback
    }
  }

  /** Ceiling-scored: a missed trial is data about vigilance, not a gap. */
  private void onNoResponse() {
    if (phase != Phase.STIMULUS) {
      return;
    }
    reactions.add(NO_RESPONSE_MS);
    trial++;
    view.setMessage("no response");
    phase = Phase.FEEDBACK;
    handler.postDelayed(this::nextOrFinish, 700);
  }

  /** A two-finger tap means "that one did not count" and costs nothing. */
  private void onMisfire() {
    if (phase == Phase.STIMULUS || phase == Phase.ARMED) {
      discarded++;
      handler.removeCallbacksAndMessages(null);
      view.setMessage("dropped");
      phase = Phase.FEEDBACK;
      handler.postDelayed(this::arm, 500);
    }
  }

  private void nextOrFinish() {
    if (trial >= TRIALS) {
      finishRun();
    } else {
      arm();
    }
  }

  private void finishRun() {
    phase = Phase.DONE;
    handler.removeCallbacksAndMessages(null);
    int median = median(reactions);
    int lapses = 0;
    for (int rt : reactions) {
      if (rt >= LAPSE_MS) {
        lapses++;
      }
    }
    JSONObject o = new JSONObject();
    try {
      o.put("kind", "instrument_run");
      o.put("instrument", "pvt");
      o.put("engine", "reaction");
      o.put("epoch", epoch.id);
      // Printed, never hidden: a number corrected by an unmeasured offset is
      // a number with an unstated assumption in it.
      o.put("touch_offset_applied_ms", epoch.isCalibrated() ? epoch.touchOffsetMs : JSONObject.NULL);
      o.put("median_ms", median);
      o.put("trials", reactions.size());
      o.put("lapses", lapses);
      o.put("false_starts", falseStarts);
      o.put("interruptions", interruptions);
      o.put("discarded", discarded);
      o.put("started_at", Status.isoStamp(startedAtMs));
      JSONArray rts = new JSONArray();
      for (int rt : reactions) {
        rts.put(rt);
      }
      // The whole series, not just the summary: prime scores, and a median
      // thrown away here cannot be recomputed differently later.
      o.put("rt_ms", rts);
    } catch (JSONException e) {
      // fall through; a partial record still beats none
    }
    Events.append(this, o);
    view.setSummary(median, lapses, reactions.size());
  }

  private static int median(List<Integer> values) {
    if (values.isEmpty()) {
      return 0;
    }
    List<Integer> sorted = new ArrayList<>(values);
    java.util.Collections.sort(sorted);
    int n = sorted.size();
    return n % 2 == 1 ? sorted.get(n / 2) : (sorted.get(n / 2 - 1) + sorted.get(n / 2)) / 2;
  }

  /** The task itself: one View, drawn by hand, with no widgets to aim at. */
  private final class TrialView extends View {

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private String message = "";
    private boolean counting = false;
    private int summaryMedian = -1;
    private int summaryLapses = 0;
    private int summaryTrials = 0;

    TrialView(Activity a) {
      super(a);
      setBackgroundColor(Screen.BG);
      setKeepScreenOn(true);
    }

    void setMessage(String s) {
      message = s;
      counting = false;
      invalidate();
    }

    void startCounter() {
      message = "";
      counting = true;
      invalidate();
    }

    void setSummary(int median, int lapses, int trials) {
      summaryMedian = median;
      summaryLapses = lapses;
      summaryTrials = trials;
      counting = false;
      invalidate();
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
      if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
        if (event.getPointerCount() >= 2) {
          onMisfire();
        } else {
          onResponse(event);
        }
        return true;
      }
      if (event.getActionMasked() == MotionEvent.ACTION_POINTER_DOWN) {
        onMisfire();
        return true;
      }
      return super.onTouchEvent(event);
    }

    @Override
    protected void onDraw(Canvas canvas) {
      super.onDraw(canvas);
      int w = getWidth();
      int h = getHeight();
      paint.setTypeface(Typeface.MONOSPACE);

      paint.setColor(Screen.TEXT_GHOST);
      paint.setTextSize(spToPx(11));
      paint.setTextAlign(Paint.Align.LEFT);
      String header =
          summaryMedian >= 0
              ? "pvt · " + epoch.id
              : "pvt · " + Math.min(trial + 1, TRIALS) + "/" + TRIALS + " · " + epoch.id;
      canvas.drawText(header, spToPx(14), spToPx(28), paint);

      paint.setTextAlign(Paint.Align.CENTER);
      if (summaryMedian >= 0) {
        drawSummary(canvas, w, h);
        return;
      }

      if (counting) {
        // A number that visibly runs is the stimulus AND the feedback: the
        // operator sees the cost of a slow response without being told off.
        long elapsed = (System.nanoTime() - stimulusFrameNanos) / 1_000_000L;
        paint.setColor(Screen.ACCENT);
        paint.setTextSize(spToPx(64));
        canvas.drawText(String.valueOf(Math.max(0, elapsed)), w / 2f, h / 2f, paint);
        postInvalidateOnAnimation();
      } else if (!message.isEmpty()) {
        paint.setColor(message.contains("lapse") || message.equals("too early")
            ? Grade.UNVERIFIED.color
            : Screen.TEXT_BRIGHT);
        paint.setTextSize(spToPx(48));
        canvas.drawText(message, w / 2f, h / 2f, paint);
      } else {
        paint.setColor(Screen.TEXT_GHOST);
        paint.setTextSize(spToPx(16));
        canvas.drawText("wait for the number", w / 2f, h / 2f, paint);
      }

      paint.setColor(Screen.TEXT_GHOST);
      paint.setTextSize(spToPx(12));
      canvas.drawText("tap when it appears · two fingers to drop a trial", w / 2f, h - spToPx(28), paint);
    }

    private void drawSummary(Canvas canvas, int w, int h) {
      paint.setColor(Screen.TEXT_BRIGHT);
      paint.setTextSize(spToPx(56));
      canvas.drawText(summaryMedian + " ms", w / 2f, h / 2f - spToPx(20), paint);

      paint.setColor(Screen.TEXT_FAINT);
      paint.setTextSize(spToPx(13));
      canvas.drawText(
          "median of " + summaryTrials + " · " + summaryLapses + " lapses · "
              + falseStarts + " false starts",
          w / 2f,
          h / 2f + spToPx(24),
          paint);

      // The provenance line. A number without its apparatus is not comparable
      // to anything, and an uncalibrated offset is stated rather than assumed
      // away.
      String provenance =
          epoch.isCalibrated()
              ? "epoch " + epoch.id + " · touch offset " + epoch.touchOffsetMs + " ms applied"
              : "epoch " + epoch.id + " · touch offset not measured — raw times";
      canvas.drawText(provenance, w / 2f, h / 2f + spToPx(48), paint);
      canvas.drawText("comparable only to runs from " + epoch.id, w / 2f, h / 2f + spToPx(70), paint);

      paint.setColor(Screen.ACCENT);
      paint.setTextSize(spToPx(14));
      canvas.drawText("tap to close", w / 2f, h - spToPx(40), paint);
      setOnClickListener(v -> finish());
    }

    private float spToPx(float sp) {
      return sp * getResources().getDisplayMetrics().scaledDensity;
    }
  }
}
