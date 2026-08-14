package dev.sinnix.phone.estate

import android.content.Context
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.sync.Outbox
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * Which path a thing took, and the honesty rule around it.
 *
 * Every action the operator triggers reports the path it actually took. Not as
 * decoration — as the difference between "that is done" and "that will be done
 * within half an hour", which are different promises and the operator is
 * entitled to know which one they just got.
 */
enum class Path(val label: String) {
    LIVE("sent · live"),
    QUEUED("queued · next drain"),
    FAILED("not sent"),
}

data class Reachability(val liveMs: Long?, val checkedAtMs: Long) {
    val live: Boolean get() = liveMs != null

    /** Evidence, not a claim: the number is shown, and its age with it. */
    fun describe(nowMs: Long = System.currentTimeMillis()): String {
        val age = (nowMs - checkedAtMs) / 1000L
        return when {
            liveMs != null && age < 60 -> "live · ${liveMs} ms"
            liveMs != null -> "live · ${liveMs} ms, ${age}s ago"
            else -> "unreachable · file plane"
        }
    }
}

/**
 * The dual-transport sender.
 *
 * One rule, applied everywhere: try live, fall back to the outbox, and never
 * report a path that did not happen. The live attempt and the queued write
 * carry the *same* object, including the same `send_token`, so a request that
 * goes out live and then gets re-queued by a retry is still one request as far
 * as prime's dispatcher is concerned.
 */
class Transport(context: Context) {

    private val ctx = context.applicationContext
    private val hub = HubClient(ctx)

    @Volatile private var lastReachability: Reachability? = null

    fun cachedReachability(): Reachability? = lastReachability

    suspend fun probe(): Reachability =
        withContext(Dispatchers.IO) {
            val ms = hub.ping()
            Reachability(ms, System.currentTimeMillis()).also { lastReachability = it }
        }

    /**
     * Send an intent by whichever path is available.
     *
     * The queued path is not a failure mode; it is the design. The live path
     * only removes the wait.
     */
    suspend fun send(kind: String, vararg keyValues: Any?): Path =
        withContext(Dispatchers.IO) {
            val intent = buildIntent(kind, *keyValues)
            val token = intent.getString("send_token")

            val live = hub.postIntent(intent)
            if (live != null) {
                lastReachability = Reachability(0L, System.currentTimeMillis())
                Events.append(
                    ctx,
                    JSONObject(intent.toString()).put("kind", "intent_sent").put("path", "live")
                        .put("intent_kind", kind),
                )
                return@withContext Path.LIVE
            }

            lastReachability = Reachability(null, System.currentTimeMillis())
            val queued = Outbox.writeIntentObject(ctx, intent)
            Events.append(
                ctx,
                JSONObject(intent.toString())
                    .put("kind", "intent_sent")
                    .put("path", if (queued) "queued" else "failed")
                    .put("intent_kind", kind),
            )
            if (queued) Path.QUEUED else Path.FAILED
        }

    /** Read the estate glance: live if reachable, otherwise whatever the drain last pushed. */
    suspend fun glance(): Pair<JSONObject?, Boolean> =
        withContext(Dispatchers.IO) {
            val live = hub.glance()
            if (live != null) {
                lastReachability = Reachability(0L, System.currentTimeMillis())
                live to true
            } else {
                dev.sinnix.phone.sync.Inbox.readObject(ctx, dev.sinnix.phone.sync.Inbox.GLANCE) to
                    false
            }
        }

    suspend fun steering(): Pair<JSONObject?, Boolean> =
        withContext(Dispatchers.IO) {
            val live = hub.steering()
            if (live != null) {
                live to true
            } else {
                dev.sinnix.phone.sync.Inbox.readObject(ctx, dev.sinnix.phone.sync.Inbox.STEERING) to
                    false
            }
        }

    suspend fun jobs(): org.json.JSONArray? = withContext(Dispatchers.IO) { hub.jobs() }

    suspend fun snapshot(): JSONObject? = withContext(Dispatchers.IO) { hub.snapshot() }

    /**
     * Answer an agent's question.
     *
     * Live-preferred like everything else, but the queued form matters more
     * here than anywhere: an agent blocked on a question at 3am should get its
     * answer at the next drain rather than never.
     */
    suspend fun answerJob(jobId: String, answer: String): Path =
        withContext(Dispatchers.IO) {
            if (hub.answerJob(jobId, answer) != null) {
                Events.record(ctx, "job_answered", "job_id", jobId, "path", "live")
                Path.LIVE
            } else {
                send("job_answer", "job_id", jobId, "answer", answer)
            }
        }

    /** Run a bounded action through the hub's action API. Live only, and honest about it. */
    suspend fun action(target: String, verb: String, expectedRevision: String?): Pair<Path, String> =
        withContext(Dispatchers.IO) {
            val r = hub.action(target, verb, expectedRevision)
            if (r != null) {
                Events.record(ctx, "estate_action", "target", target, "verb", verb, "ok", true)
                Path.LIVE to (r.optString("status").ifEmpty { "accepted" })
            } else {
                // Deliberately NOT queued. start/stop/restart on a live unit is
                // a decision about right now; executing it half an hour later,
                // against a machine in a state nobody looked at, is a different
                // and worse action than the one the operator asked for.
                Events.record(ctx, "estate_action", "target", target, "verb", verb, "ok", false)
                Path.FAILED to "needs the tailnet — actions are not queued"
            }
        }

    private fun buildIntent(kind: String, vararg keyValues: Any?): JSONObject {
        val o = JSONObject()
        o.put("schema", "sinnix.phone.intent/1")
        o.put("kind", kind)
        o.put("send_token", UUID.randomUUID().toString())
        o.put("ts", Stamps.iso(System.currentTimeMillis()))
        var i = 0
        while (i + 1 < keyValues.size) {
            o.put(keyValues[i].toString(), keyValues[i + 1] ?: JSONObject.NULL)
            i += 2
        }
        return o
    }
}
