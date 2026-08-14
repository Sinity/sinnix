package dev.sinnix.phone;

import android.content.Context;
import android.os.Build;
import android.os.Environment;
import android.util.Log;

import java.io.File;

/**
 * Where chunks go.
 *
 * <p>The shared path is the contract with the desktop: scripts/sinnix-phone
 * drains {@code /sdcard/sinnix-ambient} over Termux's sshd, and the lake
 * already holds chunks under that name. Keeping it requires all-files access,
 * because scoped storage makes every other writable location invisible to a
 * different app's uid.
 *
 * <p>If that grant is missing the service still records, into the app-private
 * external directory, so a permission slip degrades to "captured but not yet
 * drainable" instead of "captured nothing". That directory is unreadable by
 * Termux on Android 11+, so the fallback is reported loudly rather than
 * treated as equivalent.
 */
final class Storage {

  static final String SHARED_DIR = "/sdcard/sinnix-ambient";

  private Storage() {}

  static boolean haveAllFilesAccess() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
      return Environment.isExternalStorageManager();
    }
    return true;
  }

  /** The directory chunks are currently being written to, or null if none is writable. */
  static File chunkDir(Context ctx) {
    File shared = new File(SHARED_DIR);
    if (haveAllFilesAccess()) {
      if (shared.isDirectory() || shared.mkdirs()) {
        if (shared.canWrite()) {
          return shared;
        }
      }
      Log.w(AmbientService.TAG, "all-files access held but " + SHARED_DIR + " is not writable");
    }
    File fallback = new File(ctx.getExternalFilesDir(null), "ambient");
    if (fallback.isDirectory() || fallback.mkdirs()) {
      return fallback;
    }
    return null;
  }

  static boolean usingFallback(Context ctx) {
    File dir = chunkDir(ctx);
    return dir != null && !SHARED_DIR.equals(dir.getAbsolutePath());
  }

  /**
   * The app's own estate, separate from the recorder's lane.
   *
   * <p>Kept apart from {@link #SHARED_DIR} because that directory has one
   * meaning to the drain -- audio chunks, rotated and deleted once the lake
   * holds them -- and the app's records are neither. Mixing them would make
   * the drain's `--remove-source-files` a hazard to the event log.
   */
  static final String ESTATE_DIR = "/sdcard/sinnix-phone";

  /** {@code <estate>/<name>}, created on demand, or null if nothing is writable. */
  static File estateDir(Context ctx, String name) {
    File base = new File(ESTATE_DIR);
    if (!haveAllFilesAccess() || !(base.isDirectory() || base.mkdirs()) || !base.canWrite()) {
      // Same degradation as the chunk path: an app-private location keeps the
      // record intact even though the drain cannot reach it.
      base = new File(ctx.getExternalFilesDir(null), "estate");
    }
    File dir = name == null ? base : new File(base, name);
    if (dir.isDirectory() || dir.mkdirs()) {
      return dir;
    }
    Log.w(AmbientService.TAG, "no writable estate directory at " + dir);
    return null;
  }
}
