package dev.sinnix.phone.sync

import android.content.Context
import android.os.FileObserver
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Notifications
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.io.File
import org.json.JSONObject

/**
 * The phone's inbound half: what prime pushes down.
 *
 * Four kinds of file, all JSON, all written by the drain into
 * `/sdcard/sinnix-phone/inbox/`:
 *
 * - `steering.json` — the standing menu, open commitments, the ready queue.
 * - `glance.json` — the estate's verdict, as data rather than as a page.
 * - `receipts` — one file per thing prime answered that the phone asked for.
 * - `notify` — one file per estate interruption.
 * - `decks` — drill decks, which parameterize the instrument engines.
 *
 * Receipts and notifications are consumed: rendered as a notification and then
 * deleted, because a receipt that stays is a receipt that reappears. Steering,
 * glance and decks are state, and are read where they lie.
 */
object Inbox {

    fun dir(ctx: Context): File? = Storage.estateDir(ctx, Storage.INBOX)

    fun sub(ctx: Context, name: String): File? =
        dir(ctx)?.let { File(it, name).apply { if (!isDirectory) mkdirs() } }

    fun readObject(ctx: Context, name: String): JSONObject? {
        val d = dir(ctx) ?: return null
        val text = Storage.readText(File(d, name)) ?: return null
        return try {
            JSONObject(text)
        } catch (e: Exception) {
            Log.w(Storage.TAG, "inbox/$name is not readable JSON", e)
            null
        }
    }

    /**
     * How stale the pushed state is.
     *
     * Always rendered next to anything read from the inbox, never hidden: a
     * ready queue from this morning and a ready queue from four days ago look
     * identical on screen unless the screen says which one it is holding.
     */
    fun ageSeconds(ctx: Context, name: String): Long {
        val d = dir(ctx) ?: return -1
        val f = File(d, name)
        if (!f.isFile) return -1
        return (System.currentTimeMillis() - f.lastModified()) / 1000L
    }

    /**
     * Render every pending receipt and notification, then delete it.
     *
     * Deletion is the acknowledgement. There is no ack channel back to prime
     * for these, and there does not need to be: the file existing means "the
     * phone has not shown this yet", which is the only state worth tracking.
     */
    fun drainNotifications(ctx: Context): Int {
        var shown = 0
        shown += consume(ctx, "receipts") { o, id ->
            Notifications.postReceipt(
                ctx,
                id,
                o.optString("title", "Receipt"),
                o.optString("body", o.optString("text", "")),
                o.optString("route").ifEmpty { null },
            )
            Events.record(
                ctx,
                "receipt_shown",
                "receipt_kind", o.optString("kind"),
                "send_token", o.optString("send_token"),
            )
        }
        shown += consume(ctx, "notify") { o, id ->
            Notifications.postNeedsYou(
                ctx,
                id,
                o.optString("title", "Estate"),
                o.optString("body", o.optString("text", "")),
                o.optString("route").ifEmpty { null },
            )
            Events.record(ctx, "estate_notification", "title", o.optString("title"))
        }
        return shown
    }

    private inline fun consume(
        ctx: Context,
        subdir: String,
        render: (JSONObject, Int) -> Unit,
    ): Int {
        val d = sub(ctx, subdir) ?: return 0
        val files = d.listFiles { _, name -> name.endsWith(".json") } ?: return 0
        var n = 0
        for ((i, f) in files.sortedBy { it.name }.withIndex()) {
            val text = Storage.readText(f) ?: continue
            val o =
                try {
                    JSONObject(text)
                } catch (e: Exception) {
                    Log.w(Storage.TAG, "unparseable ${f.name}; leaving it in place", e)
                    continue
                }
            render(o, i)
            f.delete()
            n++
        }
        return n
    }

    /** Decks pushed from prime, newest first, with their staleness. */
    fun decks(ctx: Context): List<Pair<JSONObject, Long>> {
        val d = sub(ctx, "decks") ?: return emptyList()
        val files = d.listFiles { _, name -> name.endsWith(".json") } ?: return emptyList()
        return files.mapNotNull { f ->
            val text = Storage.readText(f) ?: return@mapNotNull null
            try {
                JSONObject(text) to (System.currentTimeMillis() - f.lastModified()) / 1000L
            } catch (e: Exception) {
                null
            }
        }
            .sortedBy { it.second }
    }

    /** Asset next to a deck manifest, or null when the push was incomplete. */
    fun deckAsset(ctx: Context, name: String): File? {
        val d = sub(ctx, "decks") ?: return null
        val f = File(d, name)
        return if (f.isFile) f else null
    }

    const val STEERING = "steering.json"
    const val GLANCE = "glance.json"
}

/**
 * Watches the inbox while the capture service is alive, so a receipt shows up
 * within seconds of landing rather than at the next app open.
 *
 * [FileObserver] rather than a poll: the arrival is an event the kernel already
 * knows about, and a phone that is asleep should not be woken to discover
 * nothing changed. The watchdog alarm sweeps as a backstop for the case where
 * capture is off and nothing is watching.
 */
class InboxWatcher(context: Context) {

    private val ctx = context.applicationContext
    private var observer: FileObserver? = null

    fun start() {
        val receipts = Inbox.sub(ctx, "receipts") ?: return
        val notify = Inbox.sub(ctx, "notify")
        observer =
            object : FileObserver(receipts, CLOSE_WRITE or MOVED_TO) {
                    override fun onEvent(event: Int, path: String?) {
                        Inbox.drainNotifications(ctx)
                    }
                }
                .also { it.startWatching() }
        // One observer, and a sweep for the sibling directory: two observers
        // would double every notification when the drain writes both in one
        // pass, and the sweep is cheap enough to run on either signal.
        if (notify != null) Inbox.drainNotifications(ctx)
    }

    fun stop() {
        observer?.stopWatching()
        observer = null
    }

    companion object {
        /** The backstop: called from the watchdog alarm and on app resume. */
        fun sweepOnce(ctx: Context) {
            // The estate line on the widget comes from inbox/glance.json, so a
            // drain is the other event that changes what it says.
            dev.sinnix.phone.ui.widget.SinnixWidget.refresh(ctx)
            val shown = Inbox.drainNotifications(ctx)
            if (shown > 0) {
                Events.record(
                    ctx,
                    "inbox_swept",
                    "shown", shown,
                    "at", Stamps.iso(System.currentTimeMillis()),
                )
            }
        }
    }
}
