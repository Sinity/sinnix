package dev.sinnix.phone.estate

import android.content.Context
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Storage
import java.io.RandomAccessFile
import java.net.InetSocketAddress
import java.net.Socket
import org.json.JSONObject

/**
 * Live mirror of the events plane: new event lines reach prime within a
 * heartbeat instead of a drain cycle.
 *
 * The day files stay the record and the drain stays the reconciliation --
 * this lane is deliberately a MIRROR, wrapped under its own kind
 * (`estate_event`) so the receiver files it into one `phone-estate_event`
 * capture lane and nothing downstream can mistake the low-latency copy for
 * the canonical history. Measured before this existed: ten minutes from a
 * reading to the events plane, up to thirty more to the lake -- and one
 * evening where a silently broken transport held EVERYTHING back for hours.
 * A mirror that pushes on every heartbeat turns that class of failure into
 * a visible gap in a secondary lane instead of a hole in freshness.
 *
 * Mirror semantics make two hard problems cheap. The cursor starts at the
 * END of the current file, because the first run lands on a day file that
 * may hold a gigabyte of backfill the drain already owns. And a flood tick
 * ships only the newest slice, with an explicit gap record naming the bytes
 * it skipped -- a quarter-million-record sweep must not be re-serialized
 * through a phone socket when the file it lives in is already on its way.
 *
 * Same transport doctrine as the speech lane: one connection per flush, no
 * held socket, because this phone sleeps, roams and changes networks, and a
 * connection kept open across that is usually stale in a way neither end
 * has noticed. Delivery is fire-and-forget TCP; the cursor advances only
 * after a successful write, so an unreachable receiver means retry next
 * heartbeat, not loss.
 */
class EventStreamLane(context: Context) {

    private val ctx: Context = context.applicationContext

    private val worker = java.util.concurrent.Executors.newSingleThreadExecutor { r ->
        Thread(r, "event-stream").apply { isDaemon = true }
    }
    private val busy = java.util.concurrent.atomic.AtomicBoolean(false)

    fun tick() {
        if (!busy.compareAndSet(false, true)) return
        worker.execute {
            try {
                flushNew()
            } catch (e: Exception) {
                Log.w(Storage.TAG, "event-stream: flush failed", e)
            } finally {
                busy.set(false)
            }
        }
    }

    private fun prefs() = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun flushNew() {
        if (!Prefs.streamEvents(ctx)) return
        val file = Events.fileFor(ctx, System.currentTimeMillis()) ?: return
        if (!file.isFile) return

        val name = file.name
        var offset =
            if (prefs().getString(KEY_FILE, null) == name) {
                prefs().getLong(KEY_OFFSET, 0L)
            } else {
                // New day (or first run): the mirror starts NOW. Yesterday's
                // remainder and any pre-existing bulk belong to the drain.
                file.length()
            }
        val size = file.length()
        if (size < offset) offset = 0 // truncated/replaced file: start over
        if (size == offset) {
            persist(name, offset)
            return
        }

        var skipped = 0L
        if (size - offset > MAX_FLUSH_BYTES) {
            skipped = size - offset - MAX_FLUSH_BYTES
            offset = size - MAX_FLUSH_BYTES
        }

        val lines = ArrayList<String>()
        RandomAccessFile(file, "r").use { input ->
            input.seek(offset)
            if (skipped > 0) input.readLine() // certain mid-line landing
            while (true) {
                val before = input.filePointer
                val line = input.readLine() ?: break
                // A line without a newline yet is still being appended;
                // leave it for the next tick rather than shipping half.
                if (input.filePointer >= size && !endsWithNewline(input, size)) {
                    input.seek(before)
                    break
                }
                if (line.isNotEmpty()) lines.add(line)
            }
            offset = input.filePointer
        }
        if (skipped > 0) {
            lines.add(
                JSONObject().put("kind", "estate_event_gap")
                    .put("skipped_bytes", skipped).toString())
        }
        if (lines.isEmpty()) {
            persist(name, offset)
            return
        }

        if (send(lines)) persist(name, offset)
    }

    private fun endsWithNewline(input: RandomAccessFile, size: Long): Boolean {
        val at = input.filePointer
        return try {
            input.seek(size - 1)
            val last = input.read()
            input.seek(at)
            last == '\n'.code
        } catch (e: Exception) {
            true
        }
    }

    private fun persist(name: String, offset: Long) =
        prefs().edit().putString(KEY_FILE, name).putLong(KEY_OFFSET, offset).apply()

    /** One connection, all pending lines, each wrapped under the mirror kind. */
    private fun send(lines: List<String>): Boolean =
        Prefs.receiverCandidates(ctx).any { sendTo(it, lines) }

    private fun sendTo(target: String, lines: List<String>): Boolean {
        val host = target.substringBeforeLast(':', target)
        val port = target.substringAfterLast(':', "8940").toIntOrNull() ?: 8940
        return try {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(host, port), CONNECT_TIMEOUT_MS)
                socket.soTimeout = CONNECT_TIMEOUT_MS
                val out = socket.getOutputStream()
                for (raw in lines) {
                    val wrapped =
                        try {
                            JSONObject().put("kind", "estate_event")
                                .put("event", JSONObject(raw))
                        } catch (e: Exception) {
                            // A corrupt line is still an observation.
                            JSONObject().put("kind", "estate_event")
                                .put("unparsed", raw.take(4096))
                        }
                    out.write((wrapped.toString() + "\n").toByteArray())
                }
                out.flush()
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    companion object {
        private const val PREFS = "sinnix-phone-eventstream"
        private const val KEY_FILE = "file"
        private const val KEY_OFFSET = "offset"
        private const val CONNECT_TIMEOUT_MS = 4000
        private const val MAX_FLUSH_BYTES = 512L shl 10
    }
}
