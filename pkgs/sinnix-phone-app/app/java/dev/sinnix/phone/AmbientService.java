package dev.sinnix.phone;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import android.util.Log;

import java.io.File;

/**
 * Continuous ambient audio capture.
 *
 * <p>Runs as a microphone-typed foreground service, which is what lets the
 * recorder keep receiving real samples with the screen off. The service owns a
 * single {@link MediaRecorder} at a time and rotates it on a fixed wall-clock
 * cadence, producing one chunk file per period.
 *
 * <p>Files are written as {@code ambient-<UTC>.m4a.part} and renamed to
 * {@code .m4a} only once the muxer has closed them. The desktop drain
 * (scripts/sinnix-phone) rsyncs this directory with --remove-source-files, so
 * an in-progress file under its final name would eventually be deleted out
 * from under the open descriptor and lose the trailing moov atom. The suffix,
 * plus an rsync exclude on the desktop side, makes "closed" an explicit state
 * rather than an inference from mtime ordering.
 */
public class AmbientService extends Service {

  static final String TAG = "sinnix-ambient";
  static final String CHANNEL_ID = "sinnix-ambient";
  static final int NOTIFICATION_ID = 4711;

  static final String ACTION_START = "dev.sinnix.phone.START";
  static final String ACTION_STOP = "dev.sinnix.phone.STOP";

  /** Chunk length. Matches the 300s convention the lake already holds. */
  static final long CHUNK_MILLIS = 300_000L;

  /** Cadence for refreshing the on-device liveness file. */
  static final long HEARTBEAT_MILLIS = 20_000L;

  /** Backoff after a recorder failure (mic stolen by a call, etc.). */
  static final long RETRY_MILLIS = 15_000L;

  /** Set by the service itself so the watchdog and UI can ask cheaply. */
  static volatile boolean running = false;

  private HandlerThread thread;
  private Handler handler;
  private PowerManager.WakeLock wakeLock;

  private MediaRecorder recorder;
  private File currentPart;
  private long chunkStartedAtMs;
  /**
   * Capture rates in preference order. This is an archive lane, not an ASR feed:
   * 16 kHz caps audio bandwidth at 8 kHz, discarding the room -- music,
   * environment, the timbre diarization and speaker identification need --
   * before it is ever written, and nothing downstream can recover a band that
   * was never captured. Lower entries are degraded fallbacks, not alternatives.
   *
   * <p>Verified in the file rather than in the API's own account of itself:
   * 48 kHz yields mean -37.4 dB / max -7.0 dB over a full 300s chunk. That
   * check is the point. A chunk recorded while a second recorder held the
   * microphone came back at mean = max = -91.0 dB -- digital silence at full
   * bitrate and exact duration, with {@code prepare()} and {@code start()}
   * both reporting success. Nothing structural separates those two files;
   * only their samples do. The silence was contention, not the rate, and the
   * amplitude heartbeat did catch it -- which is the argument for that
   * detector, not for distrusting a rate the hardware honours.
   */
  private static final int[] SAMPLING_RATE_LADDER = {48000, 44100, 16000};

  private int samplingRate = SAMPLING_RATE_LADDER[0];

  private final Status status = new Status();

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }

  @Override
  public void onCreate() {
    super.onCreate();
    thread = new HandlerThread("ambient-rotate");
    thread.start();
    handler = new Handler(thread.getLooper());

    PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
    // The foreground service keeps mic access; it does not by itself keep the
    // CPU scheduled tightly enough for the rotation handler to fire on time in
    // Doze. The partial wakelock is what keeps chunk boundaries near 300s
    // instead of drifting to whatever maintenance window happens next.
    wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "sinnix:ambient");
    wakeLock.setReferenceCounted(false);
    wakeLock.acquire();

    status.attach(this);
    sweepOrphans();
  }

  /**
   * Retire {@code .part} files left behind by a previous process.
   *
   * <p>Nothing else writes that suffix, so any one present at startup belongs
   * to a recorder that died without closing its muxer. The drain skips
   * {@code .part} to avoid deleting a live chunk, which means an orphan would
   * otherwise sit on the phone forever, invisible and never collected.
   *
   * <p>Renamed rather than deleted. An MP4 missing its trailing moov atom is
   * not playable, but it is not nothing either -- the samples are there and
   * recoverable -- and discarding captured audio on the device's own say-so
   * is not this service's call to make. Under {@code .orphan} it drains to
   * the lake like anything else.
   */
  private void sweepOrphans() {
    File dir = Storage.chunkDir(this);
    if (dir == null) {
      return;
    }
    File[] parts = dir.listFiles((d, name) -> name.endsWith(".m4a.part"));
    if (parts == null) {
      return;
    }
    for (File part : parts) {
      File dest = new File(dir, stripPart(part.getName()) + ".orphan");
      if (!part.renameTo(dest)) {
        Log.w(TAG, "could not retire orphan " + part.getName());
      } else {
        Log.i(TAG, "retired orphan chunk " + dest.getName());
      }
    }
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int startId) {
    String action = intent == null ? null : intent.getAction();
    if (ACTION_STOP.equals(action)) {
      stopSelf();
      return START_NOT_STICKY;
    }

    // startForeground must happen before any mic access, and within a few
    // seconds of startForegroundService, or the platform kills us with an
    // ANR-shaped crash.
    startForeground(NOTIFICATION_ID, buildNotification("starting"));
    running = true;
    status.serviceStarted();

    handler.removeCallbacksAndMessages(null);
    handler.post(this::rotate);
    handler.postDelayed(this::heartbeat, HEARTBEAT_MILLIS);

    Watchdog.schedule(this);

    // START_STICKY so a low-memory kill is followed by a restart with a null
    // intent, which the branch above treats as "start capturing".
    return START_STICKY;
  }

  @Override
  public void onDestroy() {
    running = false;
    if (handler != null) {
      handler.removeCallbacksAndMessages(null);
      handler.post(
          () -> {
            closeChunk();
            status.serviceStopped();
          });
    }
    if (thread != null) {
      thread.quitSafely();
    }
    if (wakeLock != null && wakeLock.isHeld()) {
      wakeLock.release();
    }
    super.onDestroy();
  }

  // --- recording ---------------------------------------------------------

  /** Close the open chunk (if any), open the next one, and schedule the next rotation. */
  private void rotate() {
    closeChunk();
    boolean ok = openChunk();
    handler.postDelayed(this::rotate, ok ? CHUNK_MILLIS : RETRY_MILLIS);
    updateNotification();
  }

  private boolean openChunk() {
    File dir = Storage.chunkDir(this);
    if (dir == null) {
      status.recordFailure("no writable chunk directory (all-files access not granted?)");
      return false;
    }
    String stamp = Status.utcStamp(System.currentTimeMillis());
    File part = new File(dir, "ambient-" + stamp + ".m4a.part");

    // Start every chunk back at the preferred rate. A codec refusal is often
    // transient (another app holding the encoder), and without this reset one
    // such moment would degrade every remaining chunk until the service
    // restarts. The cost when the refusal is permanent is one failed prepare()
    // per rotation.
    samplingRate = SAMPLING_RATE_LADDER[0];
    MediaRecorder r = newRecorder();
    r.setOutputFile(part.getAbsolutePath());
    r.setOnErrorListener((mr, what, extra) -> onRecorderError("error " + what + "/" + extra));
    try {
      r.prepare();
      r.start();
    } catch (Exception first) {
      // Not every codec path accepts every rate. Walk down the ladder rather
      // than dropping capture entirely -- a degraded chunk beats a hole.
      release(r);
      Exception last = first;
      for (int rate : SAMPLING_RATE_LADDER) {
        if (rate >= samplingRate) {
          continue;
        }
        Log.w(TAG, samplingRate + " Hz recorder failed, falling back to " + rate + " Hz", last);
        samplingRate = rate;
        MediaRecorder retry = newRecorder();
        retry.setOutputFile(part.getAbsolutePath());
        retry.setOnErrorListener((mr, what, extra) -> onRecorderError("error " + what + "/" + extra));
        try {
          retry.prepare();
          retry.start();
          recorder = retry;
          currentPart = part;
          chunkStartedAtMs = System.currentTimeMillis();
          status.chunkOpened(part, chunkStartedAtMs, samplingRate);
          return true;
        } catch (Exception next) {
          release(retry);
          last = next;
        }
      }
      status.recordFailure("recorder start failed: " + last);
      part.delete();
      return false;
    }

    recorder = r;
    currentPart = part;
    chunkStartedAtMs = System.currentTimeMillis();
    status.chunkOpened(part, chunkStartedAtMs, samplingRate);
    return true;
  }

  private MediaRecorder newRecorder() {
    MediaRecorder r =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ? new MediaRecorder(this) : new MediaRecorder();
    r.setAudioSource(MediaRecorder.AudioSource.MIC);
    r.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
    r.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
    r.setAudioChannels(1);
    r.setAudioSamplingRate(samplingRate);
    // 96 kbps mono AAC, the same archive bitrate the desktop lane encodes at,
    // so a phone chunk and a desktop chunk are the same grade of evidence.
    // ~3.6 MB per 5 min chunk.
    r.setAudioEncodingBitRate(96000);
    return r;
  }

  private void closeChunk() {
    MediaRecorder r = recorder;
    File part = currentPart;
    recorder = null;
    currentPart = null;
    if (r == null) {
      return;
    }
    boolean stopped = false;
    try {
      r.stop();
      stopped = true;
    } catch (Exception e) {
      // stop() throws when the muxer never got a frame. The file is garbage
      // in that case; keeping it would put a zero-length chunk in the lake.
      Log.w(TAG, "recorder stop failed", e);
      status.recordFailure("recorder stop failed: " + e);
    } finally {
      release(r);
    }

    if (part == null) {
      return;
    }
    if (!stopped || !part.isFile() || part.length() == 0) {
      part.delete();
      return;
    }
    File finalFile = new File(part.getParentFile(), stripPart(part.getName()));
    if (!part.renameTo(finalFile)) {
      Log.w(TAG, "could not rename " + part + " -> " + finalFile);
      status.recordFailure("rename failed for " + part.getName());
      return;
    }
    long closedAt = System.currentTimeMillis();
    int peak = status.chunkPeak();
    status.chunkClosed(finalFile, chunkStartedAtMs, closedAt);
    // The chunk itself leaves the phone on the next drain, so the coverage
    // record has to outlive it: the ribbon and the hole list are reductions of
    // these lines, not of the directory listing. Peak amplitude travels with
    // it because a chunk that captured nothing is otherwise indistinguishable
    // from one that captured a quiet room.
    Events.record(
        this,
        "chunk_closed",
        "chunk", finalFile.getName(),
        "started_at", Status.utcStamp(chunkStartedAtMs),
        "seconds", Math.max(0L, (closedAt - chunkStartedAtMs) / 1000L),
        "bytes", finalFile.length(),
        "peak_amplitude", peak,
        "captured_nothing", peak == 0,
        "sampling_rate", samplingRate);
  }

  private static String stripPart(String name) {
    return name.endsWith(".part") ? name.substring(0, name.length() - ".part".length()) : name;
  }

  private static void release(MediaRecorder r) {
    try {
      r.reset();
    } catch (Exception ignored) {
      // reset on a dead recorder is not actionable
    }
    try {
      r.release();
    } catch (Exception ignored) {
      // ditto
    }
  }

  private void onRecorderError(String detail) {
    Log.w(TAG, "recorder error: " + detail);
    status.recordFailure(detail);
    handler.post(
        () -> {
          handler.removeCallbacksAndMessages(null);
          closeChunk();
          handler.postDelayed(this::rotate, RETRY_MILLIS);
          handler.postDelayed(this::heartbeat, HEARTBEAT_MILLIS);
        });
  }

  // --- liveness ----------------------------------------------------------

  private void heartbeat() {
    long size = currentPart == null ? 0 : currentPart.length();
    status.heartbeat(size, elapsedChunkSeconds(), sampleAmplitude());

    // A chunk whose file has stopped growing means the recorder has stopped
    // producing frames while still believing it is running.
    if (status.stalled()) {
      Log.w(TAG, "chunk file stopped growing; cycling recorder");
      onRecorderError("chunk file stopped growing");
      return;
    }
    // The more dangerous case, and the one file growth cannot see: Android's
    // concurrent-capture arbitration hands the microphone to a foreground app
    // and feeds this one digital silence instead. The encoder keeps running at
    // the same bitrate, so the file grows exactly as it should while the audio
    // is nothing. Amplitude is the only signal that separates them -- a live
    // microphone in a silent room still reports its noise floor, so a
    // sustained run of exact zeroes means muted, not quiet.
    if (status.muted()) {
      Log.w(TAG, "microphone reporting digital silence; cycling recorder");
      onRecorderError("microphone muted (lost capture arbitration?)");
      return;
    }
    updateNotification();
    handler.postDelayed(this::heartbeat, HEARTBEAT_MILLIS);
  }

  /**
   * Peak amplitude since the previous call, or -1 when unavailable.
   *
   * <p>Deliberately read once per heartbeat and nowhere else: the reading is
   * destructive (it resets the running peak), so a second caller would blind
   * the silence check.
   */
  private int sampleAmplitude() {
    MediaRecorder r = recorder;
    if (r == null) {
      return -1;
    }
    try {
      return r.getMaxAmplitude();
    } catch (Exception e) {
      return -1;
    }
  }

  private long elapsedChunkSeconds() {
    return chunkStartedAtMs == 0 ? 0 : (System.currentTimeMillis() - chunkStartedAtMs) / 1000L;
  }

  // --- notification ------------------------------------------------------

  private void updateNotification() {
    NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
    String detail =
        recorder == null
            ? "not recording — " + status.lastErrorShort()
            : "recording " + elapsedChunkSeconds() + "s / " + (CHUNK_MILLIS / 1000) + "s"
                + " · " + status.chunksClosed() + " chunks";
    nm.notify(NOTIFICATION_ID, buildNotification(detail));
  }

  private Notification buildNotification(String detail) {
    NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && nm.getNotificationChannel(CHANNEL_ID) == null) {
      NotificationChannel channel =
          new NotificationChannel(CHANNEL_ID, "Ambient capture", NotificationManager.IMPORTANCE_LOW);
      channel.setShowBadge(false);
      channel.setSound(null, null);
      nm.createNotificationChannel(channel);
    }
    PendingIntent open =
        PendingIntent.getActivity(
            this,
            0,
            new Intent(this, HomeActivity.class),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

    Notification.Builder b =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(this, CHANNEL_ID)
            : new Notification.Builder(this);
    return b.setContentTitle("Sinnix ambient capture")
        .setContentText(detail)
        .setSmallIcon(android.R.drawable.ic_btn_speak_now)
        .setOngoing(true)
        .setContentIntent(open)
        .build();
  }

  // --- entry points ------------------------------------------------------

  static void start(Context ctx) {
    Intent i = new Intent(ctx, AmbientService.class).setAction(ACTION_START);
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
      ctx.startForegroundService(i);
    } else {
      ctx.startService(i);
    }
  }

  static void stop(Context ctx) {
    ctx.startService(new Intent(ctx, AmbientService.class).setAction(ACTION_STOP));
  }
}
