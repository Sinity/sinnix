package dev.sinnix.phone.core

import android.content.Context
import android.os.Build
import android.os.Environment
import android.util.Log
import java.io.File

/**
 * Where things go on the device, and why those two directories are separate.
 *
 * The chunk directory is a contract with the desktop: `scripts/sinnix-phone`
 * drains `/sdcard/sinnix-ambient` and the lake already holds chunks under that
 * name. Keeping it requires all-files access, because scoped storage makes
 * every other writable location invisible to a different app's uid.
 *
 * The estate directory is the app's own record — events, epoch, outbox, inbox.
 * It is deliberately NOT the chunk directory, because that one has exactly one
 * meaning to the drain (audio, rotated and deleted once the lake holds it) and
 * `--remove-source-files` pointed at an event log is a data-loss bug waiting
 * for its first drain.
 *
 * If all-files access is missing, both degrade to app-private external
 * storage: a permission slip becomes "captured but not yet drainable" rather
 * than "captured nothing". That location is unreadable by Termux on Android
 * 11+, so the fallback is reported loudly rather than treated as equivalent.
 */
object Storage {

    const val TAG = "sinnix-ambient"

    const val SHARED_DIR = "/sdcard/sinnix-ambient"
    const val ESTATE_DIR = "/sdcard/sinnix-phone"

    /** Estate subdirectories. Named here so no caller spells one differently. */
    const val EVENTS = "events"
    const val OUTBOX = "outbox"
    const val INBOX = "inbox"
    const val BLOBS = "blobs"

    fun haveAllFilesAccess(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            true
        }

    /** The directory chunks are currently written to, or null if none is writable. */
    fun chunkDir(ctx: Context): File? {
        val shared = File(SHARED_DIR)
        if (haveAllFilesAccess()) {
            if ((shared.isDirectory || shared.mkdirs()) && shared.canWrite()) return shared
            Log.w(TAG, "all-files access held but $SHARED_DIR is not writable")
        }
        val fallback = File(ctx.getExternalFilesDir(null), "ambient")
        return if (fallback.isDirectory || fallback.mkdirs()) fallback else null
    }

    fun usingFallback(ctx: Context): Boolean {
        val dir = chunkDir(ctx)
        return dir != null && dir.absolutePath != SHARED_DIR
    }

    /** `<estate>/<name>`, created on demand, or null if nothing is writable. */
    fun estateDir(ctx: Context, name: String?): File? {
        var base = File(ESTATE_DIR)
        if (!haveAllFilesAccess() || !(base.isDirectory || base.mkdirs()) || !base.canWrite()) {
            base = File(ctx.getExternalFilesDir(null), "estate")
        }
        val dir = if (name == null) base else File(base, name)
        if (dir.isDirectory || dir.mkdirs()) return dir
        Log.w(TAG, "no writable estate directory at $dir")
        return null
    }

    /**
     * Write a file the way every durable record here is written: into a
     * sibling `.tmp`, fsynced, then renamed over the destination.
     *
     * The drain and the desktop both poll these paths. A torn read of a
     * half-written document is indistinguishable from a crashed writer, and
     * that misreading is the exact failure this whole program keeps hitting in
     * other forms.
     */
    fun writeAtomically(dest: File, bytes: ByteArray): Boolean {
        val tmp = File(dest.parentFile, dest.name + ".tmp")
        return try {
            java.io.FileOutputStream(tmp).use { out ->
                out.write(bytes)
                out.fd.sync()
            }
            if (tmp.renameTo(dest)) {
                true
            } else {
                Log.w(TAG, "could not replace ${dest.name}")
                tmp.delete()
                false
            }
        } catch (e: Exception) {
            Log.w(TAG, "could not write ${dest.name}", e)
            tmp.delete()
            false
        }
    }

    /** Whole-file read, tolerating absence. Files here are kilobytes, not megabytes. */
    fun readText(file: File?): String? {
        if (file == null || !file.isFile) return null
        return try {
            file.readText()
        } catch (e: Exception) {
            Log.w(TAG, "could not read ${file.name}", e)
            null
        }
    }
}
