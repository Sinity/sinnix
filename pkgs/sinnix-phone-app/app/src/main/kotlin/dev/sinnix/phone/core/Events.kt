package dev.sinnix.phone.core

import android.content.Context
import android.util.Log
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.util.Calendar
import java.util.TimeZone
import org.json.JSONObject

/**
 * The app's own record: append-only JSONL, one file per UTC day.
 *
 * Everything historical any screen shows is a reduction of this — the
 * continuity ribbon, holes, grant transitions, instrument runs, marks, EMA
 * answers, steering replies. Append-only because a reducer can always re-read
 * a log while a file the app rewrites is a file the app can corrupt; and
 * because the drain takes whole files, so a record that is only ever extended
 * is never half-written when it is collected.
 *
 * Each line carries at least `kind` and `ts`. Unknown kinds are preserved on
 * read rather than dropped: a consumer written before a kind existed should
 * skip it, not lose it.
 */
object Events {

    private const val PREFIX = "events-"
    private const val SUFFIX = ".jsonl"

    /** A single line longer than this is treated as corruption, not a record. */
    private const val MAX_LINE_BYTES = 1 shl 20

    fun fileFor(ctx: Context, atMs: Long): File? {
        val dir = Storage.estateDir(ctx, Storage.EVENTS) ?: return null
        return File(dir, PREFIX + Stamps.day(atMs) + SUFFIX)
    }

    /**
     * Append one record, stamping `ts` when the caller has not.
     *
     * Opened in append mode per call rather than held open: the recorder can be
     * killed at any moment, and a descriptor kept across that boundary buys
     * nothing a hundred-byte write needs.
     */
    fun append(ctx: Context, record: JSONObject?) {
        if (record == null) return
        val now = System.currentTimeMillis()
        if (!record.has("ts")) record.put("ts", Stamps.iso(now))
        val file = fileFor(ctx, now) ?: return
        val line = (record.toString() + "\n").toByteArray(Charsets.UTF_8)
        try {
            FileOutputStream(file, true).use { it.write(line) }
            // Not fsynced: an event lost to a crash is a missing observation,
            // while an fsync per event on a phone's flash is a durable cost
            // paid forever. The chunks themselves are what get fsynced.
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not append event to $file", e)
        }
    }

    /** The common shape: a kind plus flat key/value pairs. */
    fun record(ctx: Context, kind: String, vararg keyValues: Any?) {
        val o = JSONObject()
        o.put("kind", kind)
        var i = 0
        while (i + 1 < keyValues.size) {
            val key = keyValues[i].toString()
            val value = keyValues[i + 1]
            o.put(key, value ?: JSONObject.NULL)
            i += 2
        }
        append(ctx, o)
    }

    /**
     * Records from the last [days] UTC day-files, oldest first.
     *
     * Reads by day-file rather than by scanning everything: the ribbon only
     * ever asks for a week, and a log that grows for months should not be
     * walked to answer that.
     */
    fun recent(ctx: Context, days: Int): List<JSONObject> {
        val out = ArrayList<JSONObject>()
        val dir = Storage.estateDir(ctx, Storage.EVENTS) ?: return out
        val cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        cal.add(Calendar.DAY_OF_YEAR, -(days - 1))
        repeat(days) {
            readInto(File(dir, PREFIX + Stamps.day(cal.timeInMillis) + SUFFIX), out)
            cal.add(Calendar.DAY_OF_YEAR, 1)
        }
        return out
    }

    /** The most recent [limit] records of the given kinds, newest last. */
    fun recentOfKind(ctx: Context, days: Int, vararg kinds: String): List<JSONObject> {
        val wanted = kinds.toSet()
        return recent(ctx, days).filter { it.optString("kind") in wanted }
    }

    /**
     * Reading a whole day file into parsed objects was an OOM once the
     * Health Connect backfill wrote a quarter-million records into one day:
     * a 101 MB file became several hundred MB of JSONObjects inside a 256 MB
     * art heap, and the process crash-looped from whichever allocation
     * happened next (observed from both the home screen's offer policy and
     * the speech lane's 24-byte tensor alloc). Every caller of recent() wants
     * the newest slice, so each file contributes at most its final TAIL_BYTES
     * -- an ordinary day is far smaller than the cap and unaffected.
     */
    private const val TAIL_BYTES = 4L shl 20

    private fun readInto(file: File, out: MutableList<JSONObject>) {
        if (!file.isFile) return
        try {
            RandomAccessFile(file, "r").use { input ->
                if (input.length() > TAIL_BYTES) {
                    input.seek(input.length() - TAIL_BYTES)
                    // Mid-line landing is certain; drop the partial line.
                    input.readLine()
                }
                while (true) {
                    val line = input.readLine() ?: break
                    if (line.isEmpty() || line.length > MAX_LINE_BYTES) continue
                    // A truncated final line is the normal shape of a log whose
                    // writer was killed mid-append. Skip it and keep the rest
                    // rather than discarding the file.
                    try {
                        out.add(JSONObject(line))
                    } catch (ignored: Exception) {
                        // not a record; the next line still might be
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not read events from $file", e)
        }
    }
}
