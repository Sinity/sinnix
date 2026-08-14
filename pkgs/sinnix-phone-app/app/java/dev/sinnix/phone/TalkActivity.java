package dev.sinnix.phone;

import android.graphics.Typeface;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Hold to say something into the lake.
 *
 * <p>Press-and-hold rather than tap-to-start/tap-to-stop: a note that ends
 * when the thumb lifts cannot be left running by accident, and there is no
 * state to reason about while speaking.
 *
 * <p>This records while ambient capture keeps running, which is only sound
 * because concurrent capture was measured on this device: two AudioRecord
 * clients held the microphone simultaneously on separate input ports with no
 * loss on either. If that ever stops being true, the ambient lane's amplitude
 * heartbeat is what will notice.
 *
 * <p>Voice notes land in the outbox, not the ambient lane. They are a
 * different kind of thing -- addressed, deliberate, and meant to be acted on
 * -- and mixing them into the continuous archive would bury them.
 */
public final class TalkActivity extends Screen {

  private static final long TICK_MILLIS = 100L;

  private final Handler handler = new Handler(Looper.getMainLooper());

  private TextView button;
  private TextView hint;
  private MediaRecorder recorder;
  private File current;
  private long startedAtMs;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

    LinearLayout root = mount();
    root.addView(backRow());

    button = text("hold to talk", 22, TEXT_BRIGHT);
    button.setTypeface(Typeface.DEFAULT_BOLD);
    button.setGravity(Gravity.CENTER);
    button.setBackground(cardBackground());
    button.setLayoutParams(
        new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(220)));
    button.setOnTouchListener(
        (v, event) -> {
          switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
              start();
              return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
              stop(true);
              return true;
            default:
              return false;
          }
        });
    root.addView(button);
    root.addView(spacer(dp(12)));

    hint = mono("goes to the outbox · prime collects it on the next drain", 11, TEXT_FAINT);
    root.addView(hint);
  }

  @Override
  protected void onPause() {
    super.onPause();
    // A note interrupted by the screen going away is still a note; keep what
    // was said rather than discarding it because the gesture ended oddly.
    stop(false);
  }

  private void start() {
    if (recorder != null) {
      return;
    }
    File dir = Storage.estateDir(this, "outbox");
    if (dir == null) {
      hint.setText("no writable outbox — check all-files access in grants");
      return;
    }
    current = new File(dir, "voice-" + Status.utcStamp(System.currentTimeMillis()) + ".m4a");
    MediaRecorder r = new MediaRecorder(this);
    r.setAudioSource(MediaRecorder.AudioSource.MIC);
    r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
    r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
    r.setAudioChannels(1);
    // Speech, and the archive lane is already recording the room at full
    // fidelity a metre away -- this one only has to stay intelligible.
    r.setAudioSamplingRate(44100);
    r.setAudioEncodingBitRate(64000);
    r.setOutputFile(current.getAbsolutePath());
    try {
      r.prepare();
      r.start();
    } catch (IOException | IllegalStateException e) {
      // The likeliest cause is the platform refusing a second microphone
      // client. Say so plainly rather than leaving a button that does nothing.
      hint.setText("could not start: " + e.getClass().getSimpleName());
      r.release();
      current = null;
      return;
    }
    recorder = r;
    startedAtMs = System.currentTimeMillis();
    button.setBackground(gradeBackground(Grade.BROKEN));
    tick();
  }

  private void tick() {
    if (recorder == null) {
      return;
    }
    long seconds = (System.currentTimeMillis() - startedAtMs) / 1000L;
    button.setText("● " + seconds + "s — release to send");
    handler.postDelayed(this::tick, TICK_MILLIS);
  }

  private void stop(boolean fromGesture) {
    if (recorder == null) {
      return;
    }
    handler.removeCallbacksAndMessages(null);
    long seconds = Math.max(0L, (System.currentTimeMillis() - startedAtMs) / 1000L);
    try {
      recorder.stop();
    } catch (RuntimeException e) {
      // stop() throws when the recorder got no data at all -- a tap rather
      // than a hold. The file is then unusable and is removed.
      if (current != null) {
        current.delete();
      }
      current = null;
    } finally {
      recorder.release();
      recorder = null;
    }
    button.setBackground(cardBackground());

    if (current == null || !current.isFile() || current.length() == 0) {
      button.setText("hold to talk");
      hint.setText("too short — hold while speaking");
      return;
    }
    writeSidecar(seconds);
    button.setText("hold to talk");
    // The honest label: nothing was sent. The app has no network, and the
    // drain runs on prime's schedule.
    hint.setText("queued · " + seconds + "s · prime collects it on the next drain");
    Events.record(
        this,
        "voice_note",
        "file", current.getName(),
        "seconds", seconds,
        "ended_by", fromGesture ? "release" : "interrupted");
    current = null;
  }

  /**
   * A sidecar next to the audio, so the note is interpretable without the
   * event log: the outbox is drained on its own and a consumer should not need
   * to correlate two lanes to know what a file is.
   */
  private void writeSidecar(long seconds) {
    JSONObject o = new JSONObject();
    try {
      o.put("kind", "voice_note");
      o.put("file", current.getName());
      o.put("seconds", seconds);
      o.put("recorded_at", Status.isoStamp(startedAtMs));
      o.put("epoch", Epoch.current(this).id);
    } catch (JSONException e) {
      return;
    }
    File sidecar = new File(current.getParentFile(), current.getName() + ".json");
    try (FileOutputStream out = new FileOutputStream(sidecar)) {
      out.write(o.toString(2).getBytes(StandardCharsets.UTF_8));
    } catch (IOException | JSONException e) {
      // The audio is the irreplaceable half; a missing sidecar is recoverable
      // from the event log.
    }
  }
}
