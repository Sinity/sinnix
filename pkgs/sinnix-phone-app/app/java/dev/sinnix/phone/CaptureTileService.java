package dev.sinnix.phone;

import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

import org.json.JSONObject;

import java.io.File;
import java.io.RandomAccessFile;

/**
 * Capture state in the quick-settings shade.
 *
 * <p>The shade is where a phone is actually looked at, so this is the cheapest
 * possible answer to "is it still recording" — no unlock, no app launch.
 *
 * <p>It deliberately does <b>not</b> toggle capture. A control that can end a
 * multi-hour recording with one mis-swipe, from a surface people swipe through
 * without looking, is a hazard rather than a convenience; stopping is a
 * deliberate act and lives on the capture screen. Tapping here opens the app.
 */
public final class CaptureTileService extends TileService {

  /** A heartbeat older than this means the writer is gone, whatever the file claims. */
  private static final long STALE_MILLIS = 90_000L;

  @Override
  public void onStartListening() {
    super.onStartListening();
    render();
  }

  @Override
  public void onClick() {
    super.onClick();
    Intent intent = new Intent(this, HomeActivity.class);
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    // The Intent overload, not the PendingIntent one: this compiles against
    // platform 33, matching the device, and the replacement only exists from
    // 34. Raising the target is not free here -- see the manifest comment on
    // why it stays at 33.
    startActivityAndCollapse(intent);
  }

  private void render() {
    Tile tile = getQsTile();
    if (tile == null) {
      return;
    }
    JSONObject status = readStatus();
    long age = status == null ? -1 : ageSeconds(status);
    boolean recording = status != null && status.optBoolean("recording", false);
    boolean muted = status != null && status.optBoolean("muted", false);
    boolean live = age >= 0 && age * 1000L < STALE_MILLIS;

    // ACTIVE only for capture that is provably producing. A stale status.json
    // still says recording=true, and that claim is exactly what a dead
    // recorder leaves behind -- so liveness is judged from the heartbeat's age
    // and the microphone's own amplitude, never from the flag alone.
    if (live && recording && !muted) {
      tile.setState(Tile.STATE_ACTIVE);
      setSubtitleCompat(tile, status.optInt("chunks_closed", 0) + " chunks");
    } else if (live && muted) {
      tile.setState(Tile.STATE_INACTIVE);
      setSubtitleCompat(tile, "no sound");
    } else if (status == null) {
      tile.setState(Tile.STATE_INACTIVE);
      setSubtitleCompat(tile, "never started");
    } else {
      tile.setState(Tile.STATE_INACTIVE);
      setSubtitleCompat(tile, age < 0 ? "unknown" : age + "s stale");
    }
    tile.setLabel("Sinnix capture");
    tile.setIcon(Icon.createWithResource(this, android.R.drawable.ic_btn_speak_now));
    tile.updateTile();
  }

  private void setSubtitleCompat(Tile tile, String s) {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
      tile.setSubtitle(s);
    }
  }

  private long ageSeconds(JSONObject status) {
    long updated = Coverage.parseStamp(status.optString("updated_at"));
    return updated == 0 ? -1 : (System.currentTimeMillis() - updated) / 1000L;
  }

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
}
