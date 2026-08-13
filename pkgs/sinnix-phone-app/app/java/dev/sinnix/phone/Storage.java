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
}
