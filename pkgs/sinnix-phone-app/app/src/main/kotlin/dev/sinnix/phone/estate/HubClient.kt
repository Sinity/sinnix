package dev.sinnix.phone.estate

import android.content.Context
import android.util.Log
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Storage
import java.io.IOException
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject

/**
 * The one network client.
 *
 * Its entire job is to make the file plane feel immediate when the tailnet
 * happens to be up. It is not the app's authority for anything: every verb it
 * carries also has an outbox path, the payloads are the same JSON objects, and
 * prime treats a live POST and a drained file identically. If this class were
 * deleted the app would keep working at drain cadence.
 *
 * Timeouts are short and deliberate. A phone that has left the house should
 * discover that in a few seconds and fall back, not spin on a socket for thirty
 * while a screen shows nothing.
 */
class HubClient(context: Context) {

    private val ctx = context.applicationContext

    private val http =
        OkHttpClient.Builder()
            // 4s, not 2: the first call after the screen wakes pays a DNS
            // resolve through the VPN, and a phone that is genuinely at home
            // should not be told it is away because the resolver was cold.
            .connectTimeout(4, TimeUnit.SECONDS)
            .readTimeout(6, TimeUnit.SECONDS)
            .writeTimeout(6, TimeUnit.SECONDS)
            .callTimeout(10, TimeUnit.SECONDS)
            // No retries. A retry here delays the fallback that would have
            // worked, and the fallback is never wrong.
            .retryOnConnectionFailure(false)
            .build()

    /**
     * Every request takes a PATH and is tried against each candidate base in
     * turn, so a MagicDNS miss costs one failed connect rather than the whole
     * control plane. The first base that answers wins; nothing is cached,
     * because the phone that could not resolve the name a minute ago is
     * routinely the same phone that can now.
     */
    private val bases: List<String> get() = Prefs.hubCandidates(ctx)

    /**
     * Reachability, measured rather than assumed.
     *
     * Returns the round-trip in milliseconds, or null. Callers render the
     * number, not the boolean: "live · 34 ms" is evidence and "connected" is a
     * claim.
     */
    fun ping(): Long? {
        val started = System.nanoTime()
        val body = get("$PHONE/ping") ?: return null
        return if (body.optBoolean("ok", true)) (System.nanoTime() - started) / 1_000_000 else null
    }

    fun glance(): JSONObject? = get("$PHONE/glance")

    fun steering(): JSONObject? = get("$PHONE/steering")

    fun jobs(): JSONArray? = get("$PHONE/jobs")?.optJSONArray("jobs")

    /** Post an intent. The same object the outbox would have written. */
    fun postIntent(intent: JSONObject): JSONObject? = post("$PHONE/intent", intent)

    /** Answer an agent's question. */
    fun answerJob(jobId: String, answer: String): JSONObject? =
        post(
            "$PHONE/job-answer",
            JSONObject().put("job_id", jobId).put("answer", answer),
        )

    /**
     * The estate's runtime inventory, as the ops reducer sees it.
     *
     * Read straight from the hub's existing snapshot route rather than through
     * a phone-specific mirror, so the app cannot show a unit the action API
     * would refuse for a reason the phone does not know about.
     */
    fun snapshot(): JSONObject? = get("/ops/v1/snapshot")

    /**
     * Run one bounded action.
     *
     * This is the hub's own action API, unchanged and un-wrapped: admission,
     * optimistic concurrency and receipts are its business, and the phone
     * inherits all three by not reimplementing any of them. Where the API has
     * no verb for a target, the app says so instead of finding another way.
     */
    fun action(target: String, verb: String, expectedRevision: String?): JSONObject? =
        post(
            "/ops/v1/actions",
            JSONObject().apply {
                put("target", target)
                put("action", verb)
                if (expectedRevision != null) put("expected_revision", expectedRevision)
                put("idempotency_key", "phone-${System.currentTimeMillis()}-${target.hashCode()}")
            },
        )

    private fun get(path: String): JSONObject? =
        bases.firstNotNullOfOrNull { getFrom(it + path) }

    /**
     * Trying the second base after the first failed can deliver an intent
     * twice -- a 5xx from a prime that already executed it looks exactly like
     * one that did not. That is safe here and only here: every verb this
     * carries is keyed by send_token on the dispatcher, which records executed
     * tokens and re-emits the receipt for a repeat instead of acting again.
     */
    private fun post(path: String, body: JSONObject): JSONObject? =
        bases.firstNotNullOfOrNull { postTo(it + path, body) }

    private fun getFrom(url: String): JSONObject? =
        try {
            http.newCall(Request.Builder().url(url).get().build()).execute().use { r ->
                if (!r.isSuccessful) null else r.body?.string()?.let { JSONObject(it) }
            }
        } catch (e: IOException) {
            // Logged rather than swallowed. "unreachable" is an honest thing
            // for the UI to say and a useless thing to debug from: a phone off
            // the tailnet, a DNS miss and a cleartext-policy refusal all look
            // identical on screen and are three different fixes.
            Log.i(Storage.TAG, "hub unreachable at $url: ${e.javaClass.simpleName}: ${e.message}")
            null
        } catch (e: Exception) {
            Log.w(Storage.TAG, "hub GET $url failed oddly", e)
            null
        }

    private fun postTo(url: String, body: JSONObject): JSONObject? =
        try {
            val req =
                Request.Builder()
                    .url(url)
                    .post(body.toString().toRequestBody(JSON))
                    .build()
            http.newCall(req).execute().use { r ->
                val text = r.body?.string()
                if (!r.isSuccessful) {
                    Log.w(Storage.TAG, "hub POST $url -> ${r.code}: $text")
                    null
                } else {
                    text?.let { JSONObject(it) } ?: JSONObject().put("ok", true)
                }
            }
        } catch (e: IOException) {
            null
        } catch (e: Exception) {
            Log.w(Storage.TAG, "hub POST $url failed oddly", e)
            null
        }

    companion object {
        private const val PHONE = "/phone/v1"
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }
}
