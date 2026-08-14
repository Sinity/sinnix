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
 * discover that in two seconds and fall back, not spin on a socket for thirty
 * while a screen shows nothing.
 */
class HubClient(context: Context) {

    private val ctx = context.applicationContext

    private val http =
        OkHttpClient.Builder()
            .connectTimeout(2, TimeUnit.SECONDS)
            .readTimeout(6, TimeUnit.SECONDS)
            .writeTimeout(6, TimeUnit.SECONDS)
            .callTimeout(10, TimeUnit.SECONDS)
            // No retries. A retry here delays the fallback that would have
            // worked, and the fallback is never wrong.
            .retryOnConnectionFailure(false)
            .build()

    private val base: String get() = Prefs.hubBaseUrl(ctx).trimEnd('/')

    /**
     * Reachability, measured rather than assumed.
     *
     * Returns the round-trip in milliseconds, or null. Callers render the
     * number, not the boolean: "live · 34 ms" is evidence and "connected" is a
     * claim.
     */
    fun ping(): Long? {
        val started = System.nanoTime()
        val body = get("$base$PHONE/ping") ?: return null
        return if (body.optBoolean("ok", true)) (System.nanoTime() - started) / 1_000_000 else null
    }

    fun glance(): JSONObject? = get("$base$PHONE/glance")

    fun steering(): JSONObject? = get("$base$PHONE/steering")

    fun jobs(): JSONArray? = get("$base$PHONE/jobs")?.optJSONArray("jobs")

    /** Post an intent. The same object the outbox would have written. */
    fun postIntent(intent: JSONObject): JSONObject? = post("$base$PHONE/intent", intent)

    /** Answer an agent's question. */
    fun answerJob(jobId: String, answer: String): JSONObject? =
        post(
            "$base$PHONE/job-answer",
            JSONObject().put("job_id", jobId).put("answer", answer),
        )

    /**
     * The estate's runtime inventory, as the ops reducer sees it.
     *
     * Read straight from the hub's existing snapshot route rather than through
     * a phone-specific mirror, so the app cannot show a unit the action API
     * would refuse for a reason the phone does not know about.
     */
    fun snapshot(): JSONObject? = get("$base/ops/v1/snapshot")

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
            "$base/ops/v1/actions",
            JSONObject().apply {
                put("target", target)
                put("action", verb)
                if (expectedRevision != null) put("expected_revision", expectedRevision)
                put("idempotency_key", "phone-${System.currentTimeMillis()}-${target.hashCode()}")
            },
        )

    private fun get(url: String): JSONObject? =
        try {
            http.newCall(Request.Builder().url(url).get().build()).execute().use { r ->
                if (!r.isSuccessful) null else r.body?.string()?.let { JSONObject(it) }
            }
        } catch (e: IOException) {
            null
        } catch (e: Exception) {
            Log.w(Storage.TAG, "hub GET $url failed oddly", e)
            null
        }

    private fun post(url: String, body: JSONObject): JSONObject? =
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
