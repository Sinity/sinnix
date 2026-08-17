package dev.sinnix.phone.capture

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Storage
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/**
 * The archive ships itself.
 *
 * Ambient chunks used to leave this phone only when prime came and took them:
 * a half-hourly drain that ssh'd into Termux and rsynced `/sdcard/sinnix-
 * ambient`. That made the estate's largest data path depend on the estate's
 * least reliable component -- Termux does not survive a reboot, its sshd only
 * runs while it does, and a storage-blind sshd answers rsync with an empty
 * listing and exit 0. Every one of those failures is silent on the phone and
 * looks like "no audio yet" on prime.
 *
 * A finalized chunk is a complete, immutable file that already knows it is
 * done (the recorder renames `.part` away only after a successful stop), so
 * there is nothing to coordinate: this uploads it, prime verifies the hash it
 * was given, and only an ok deletes the local copy. That last clause is the
 * whole safety argument -- a lost response, an unreachable prime, a truncated
 * body, a full disk on the other side all leave the audio exactly where it
 * was, to be retried on the next heartbeat.
 *
 * HTTP through the hub rather than the receiver's socket, deliberately. The
 * receiver speaks line-delimited JSON sized for VAD utterances; a 3.6 MB
 * archive file base64'd through it would be a second bulk-transfer mechanism
 * built on a protocol that was not designed for one. The hub already carries
 * this phone's control plane, already has a route, and answers with a status
 * code -- which is exactly the acknowledgement a delete-after-send needs.
 *
 * Unmetered-only by default, and that is the honest replacement for the
 * drain's `termux-wifi-connectioninfo` gate: continuous ambient audio is
 * ~43 MB/hour, which is archive traffic, not the live signals the speech and
 * event lanes push regardless of network. The chunks wait; they do not
 * expire.
 */
class ChunkUploader(context: Context) {

    private val ctx: Context = context.applicationContext

    private val worker = java.util.concurrent.Executors.newSingleThreadExecutor { r ->
        Thread(r, "chunk-upload").apply { isDaemon = true }
    }
    private val busy = java.util.concurrent.atomic.AtomicBoolean(false)

    /** Reported once per transition, so a week offline is one event, not thousands. */
    private var lastFailure: String? = null

    private val http =
        OkHttpClient.Builder()
            .connectTimeout(6, TimeUnit.SECONDS)
            // Minutes, not seconds: this is a multi-megabyte body over a
            // tailnet that may be routing through a relay. The control plane's
            // short timeouts exist so a screen fails fast; nothing is waiting
            // on this one.
            .writeTimeout(2, TimeUnit.MINUTES)
            .readTimeout(1, TimeUnit.MINUTES)
            .callTimeout(3, TimeUnit.MINUTES)
            .retryOnConnectionFailure(false)
            .build()

    fun tick() {
        if (!busy.compareAndSet(false, true)) return
        worker.execute {
            try {
                uploadPending()
            } catch (e: Exception) {
                Log.w(Storage.TAG, "chunk-upload: pass failed", e)
            } finally {
                busy.set(false)
            }
        }
    }

    private fun uploadPending() {
        if (!Prefs.uploadChunks(ctx)) return
        if (!unmetered()) return note("metered")
        val dir = Storage.chunkDir(ctx) ?: return note("no chunk directory")

        val pending =
            dir.listFiles { f -> f.isFile && shippable(f.name) }
                ?.sortedBy { it.name }
                ?.take(MAX_PER_TICK)
                ?: return note("chunk directory unreadable")
        if (pending.isEmpty()) return note(null)

        for (chunk in pending) {
            val length = chunk.length()
            if (length <= 0L || length > MAX_BYTES) {
                // Neither is retryable by waiting, and both are worth seeing
                // in the events plane rather than silently skipping forever.
                Events.record(ctx, "chunk_upload_skipped", "chunk", chunk.name, "bytes", length)
                continue
            }
            val body = try {
                chunk.readBytes()
            } catch (e: Exception) {
                note("read failed: ${e.javaClass.simpleName}")
                return
            }
            if (!upload(chunk.name, body)) return
            // Verified landed. The file has served its purpose here.
            if (chunk.delete()) {
                Events.record(ctx, "chunk_uploaded", "chunk", chunk.name, "bytes", length)
            } else {
                // Prime has it; a chunk that will not delete would be uploaded
                // again forever, so say so loudly and stop this pass.
                Events.record(ctx, "chunk_upload_undeletable", "chunk", chunk.name)
                return
            }
        }
        note(null)
    }

    /**
     * True only for a body prime confirmed it wrote.
     *
     * A 2xx alone is not that confirmation: the route answers `ok:false` for a
     * hash mismatch, an unknown lane, and a name it will not accept, and each
     * of those must leave the local copy in place.
     */
    private fun upload(name: String, body: ByteArray): Boolean {
        val digest = sha256(body)
        // Each candidate base in turn: the MagicDNS name resolves on this
        // phone about as reliably as it did for the receiver, which is to say
        // it stopped one day and nothing said so. Re-uploading to the second
        // base after the first failed is free, because prime answers a chunk
        // it already holds with ok rather than a conflict.
        //
        // Only the LAST candidate's reason is reported, and only if every one
        // failed. A first attempt that fails and a second that works is a
        // successful upload, not a blocked lane; saying otherwise would file
        // a `chunk_upload_blocked` event beside every single chunk this phone
        // ships, which is how a signal stops being read.
        var reason: String? = null
        for (base in Prefs.hubCandidates(ctx)) {
            when (val outcome = uploadTo("$base$ROUTE?lane=ambient&name=$name", digest, body)) {
                null -> return true
                else -> reason = outcome
            }
        }
        note(reason)
        return false
    }

    /** Null on success; otherwise the reason this base did not take it. */
    private fun uploadTo(url: String, digest: String, body: ByteArray): String? {
        val request =
            Request.Builder()
                .url(url)
                .header("X-Sinnix-Sha256", digest)
                .post(body.toRequestBody(OCTETS))
                .build()
        return try {
            http.newCall(request).execute().use { response ->
                val text = response.body?.string().orEmpty()
                if (response.isSuccessful && JSONObject(text).optBoolean("ok", false)) null
                else "prime refused ${response.code}: ${text.take(200)}"
            }
        } catch (e: Exception) {
            "unreachable: ${e.javaClass.simpleName}"
        }
    }

    /** Records a state change in the upload path, and only a change. */
    private fun note(reason: String?) {
        if (reason == lastFailure) return
        lastFailure = reason
        if (reason != null) {
            Log.i(Storage.TAG, "chunk-upload: paused ($reason)")
            Events.record(ctx, "chunk_upload_blocked", "reason", reason)
        } else {
            Events.record(ctx, "chunk_upload_ready")
        }
    }

    /**
     * A chunk is shippable exactly when the recorder is finished with it.
     *
     * `.part` is a file still being written and is the one thing that must
     * never leave. `.orphan` is a recording a crash cut short -- the recorder
     * keeps it rather than deleting it, and so does this: truncated audio is
     * still audio.
     */
    private fun shippable(name: String): Boolean =
        !name.endsWith(".part") &&
            !name.startsWith("status.json") &&
            (name.endsWith(".m4a") || name.endsWith(".m4a.orphan"))

    private fun unmetered(): Boolean {
        if (Prefs.uploadOnMetered(ctx)) return true
        val cm = ctx.getSystemService(ConnectivityManager::class.java) ?: return false
        val caps = cm.getNetworkCapabilities(cm.activeNetwork ?: return false) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_METERED) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    private fun sha256(body: ByteArray): String =
        MessageDigest.getInstance("SHA-256").digest(body).joinToString("") { "%02x".format(it) }

    companion object {
        private const val ROUTE = "/phone/v1/chunk"
        private val OCTETS = "application/octet-stream".toMediaType()

        /**
         * Four per heartbeat (20s) drains a backlog at roughly 12 chunks a
         * minute -- an hour of accumulated audio clears in about a minute --
         * while leaving the recorder's own thread untouched, since this runs
         * on its own worker and one pass never holds more than one chunk in
         * memory.
         */
        private const val MAX_PER_TICK = 4

        /** A 5-minute chunk is ~3.6 MB; anything past this is not one. */
        private const val MAX_BYTES = 64L shl 20
    }
}
