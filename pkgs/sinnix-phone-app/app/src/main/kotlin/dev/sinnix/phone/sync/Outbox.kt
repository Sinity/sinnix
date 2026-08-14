package dev.sinnix.phone.sync

import android.content.Context
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.io.File
import java.util.UUID
import org.json.JSONObject

/**
 * The phone's outbound half: intents and blobs the drain collects and prime
 * executes.
 *
 * An intent is a *request*, never an action. The app has no authority to send
 * anything on the operator's behalf — it writes what it would like done, prime
 * does it, and a receipt comes back. That asymmetry is why the ready queue can
 * exist on a device that is offline half the time without ever lying about
 * what happened.
 *
 * Every intent carries a `send_token`. The drain may collect the same file
 * twice (a transfer that succeeded after its exit status said otherwise), and
 * the dispatcher on prime uses the token to make the second execution a no-op.
 * Idempotency is the token's whole job; nothing else about it is meaningful.
 */
object Outbox {

    /**
     * Write an intent for prime.
     *
     * Returns the send token, which the caller keeps so it can recognise the
     * receipt when it arrives — and so the live plane can post the *same*
     * object and have prime treat the two as one request rather than two.
     */
    fun writeIntent(ctx: Context, kind: String, vararg keyValues: Any?): String? {
        val token = UUID.randomUUID().toString()
        val o = JSONObject()
        o.put("schema", SCHEMA)
        o.put("kind", kind)
        o.put("send_token", token)
        o.put("ts", Stamps.iso(System.currentTimeMillis()))
        var i = 0
        while (i + 1 < keyValues.size) {
            o.put(keyValues[i].toString(), keyValues[i + 1] ?: JSONObject.NULL)
            i += 2
        }
        return if (write(ctx, "intent-${Stamps.compact(System.currentTimeMillis())}-$token.json", o))
            token
        else null
    }

    /** Post an already-built intent object (the live plane's retry path). */
    fun writeIntentObject(ctx: Context, intent: JSONObject): Boolean {
        val token = intent.optString("send_token", UUID.randomUUID().toString())
        return write(ctx, "intent-${Stamps.compact(System.currentTimeMillis())}-$token.json", intent)
    }

    private fun write(ctx: Context, name: String, o: JSONObject): Boolean {
        val dir = Storage.estateDir(ctx, Storage.OUTBOX)
        if (dir == null) {
            Log.w(Storage.TAG, "no outbox directory; intent ${o.optString("kind")} dropped")
            return false
        }
        // Same .part discipline as the chunks, for the same reason: the drain
        // moves whole files out of this directory, and a half-written intent
        // collected mid-write is an intent prime cannot parse and the phone
        // believes it sent.
        val part = File(dir, "$name.part")
        return try {
            part.writeText(o.toString() + "\n")
            part.renameTo(File(dir, name))
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not write outbox intent", e)
            false
        }
    }

    /**
     * Stage a blob (a voice note, a PPG trace, an IMU window) with its
     * metadata sidecar, both under the same base name so the drain and the
     * lake can pair them without a manifest.
     */
    fun blobFile(ctx: Context, prefix: String, extension: String): File? {
        val dir = Storage.estateDir(ctx, Storage.OUTBOX) ?: return null
        return File(dir, "$prefix-${Stamps.compact(System.currentTimeMillis())}.$extension")
    }

    fun writeSidecar(ctx: Context, blob: File, meta: JSONObject) {
        meta.put("schema", SCHEMA)
        if (!meta.has("send_token")) meta.put("send_token", UUID.randomUUID().toString())
        if (!meta.has("ts")) meta.put("ts", Stamps.iso(System.currentTimeMillis()))
        meta.put("file", blob.name)
        try {
            File(blob.parentFile, blob.name + ".json").writeText(meta.toString() + "\n")
        } catch (e: Exception) {
            Log.w(Storage.TAG, "could not write sidecar for ${blob.name}", e)
        }
        Events.append(ctx, JSONObject(meta.toString()).put("kind", meta.optString("kind", "blob")))
    }

    /** How many intents are still waiting for a drain. Rendered, never guessed at. */
    fun pendingCount(ctx: Context): Int {
        val dir = Storage.estateDir(ctx, Storage.OUTBOX) ?: return 0
        return dir.listFiles { _, name -> name.startsWith("intent-") && name.endsWith(".json") }
            ?.size ?: 0
    }

    private const val SCHEMA = "sinnix.phone.intent/1"
}
