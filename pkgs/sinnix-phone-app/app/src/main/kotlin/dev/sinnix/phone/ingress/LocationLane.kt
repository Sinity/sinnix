package dev.sinnix.phone.ingress

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Storage
import kotlin.math.roundToInt

/**
 * Where the phone is, at the coarsest cadence that still answers the question.
 *
 * This is the covariate that makes everything else joinable to a place. A
 * reaction time is a number; a reaction time with "at the desk" or "on a
 * train" attached is an observation. Marks, instrument runs and EMA answers
 * all already carry light and motion for the same reason — location is the
 * third leg, and the one nothing else in the estate can produce.
 *
 * **`LocationManager`, not Play Services.** Android 12 promoted the fused
 * provider into the framework itself, so the good provider is available
 * without a Google Play Services dependency — which for a sovereignty estate
 * would have been a large thing to swallow for one lane. On anything older the
 * network provider is the fallback, which is the same accuracy class this lane
 * wants anyway.
 *
 * The cadence is deliberately slow and the accuracy deliberately coarse. The
 * question is "where was this happening", not "which side of the room", and a
 * lane that woke the GPS every minute would be a battery lane wearing a
 * location lane's name. Movement is what triggers a record: a phone that has
 * not moved has nothing to say, and saying it every ten minutes would bury the
 * times it did.
 */
class LocationLane(context: Context) : LocationListener {

    private val ctx: Context = context.applicationContext
    private var manager: LocationManager? = null
    private var last: Location? = null

    fun start(): Boolean {
        if (!Prefs.locationLane(ctx)) return false
        if (!granted()) {
            // Denied is a state, not an error: the lane simply does not run,
            // and the settings screen says why rather than the app retrying
            // into a permission dialog the operator already dismissed.
            Events.record(ctx, "lane_blocked", "lane", "location", "reason", "permission not granted")
            return false
        }
        val lm = ctx.getSystemService(LocationManager::class.java) ?: return false
        val provider = bestProvider(lm) ?: run {
            Events.record(ctx, "lane_blocked", "lane", "location", "reason", "no provider enabled")
            return false
        }
        return try {
            lm.requestLocationUpdates(provider, INTERVAL_MILLIS, MIN_DISTANCE_METRES, this)
            manager = lm
            Log.i(Storage.TAG, "location lane on $provider")
            true
        } catch (e: SecurityException) {
            Events.record(ctx, "lane_blocked", "lane", "location", "reason", "revoked mid-flight")
            false
        }
    }

    fun stop() {
        try {
            manager?.removeUpdates(this)
        } catch (ignored: Exception) {
            // removing updates from a manager that is already gone is fine
        }
        manager = null
    }

    private fun granted(): Boolean =
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED

    private fun bestProvider(lm: LocationManager): String? {
        val candidates =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                listOf(LocationManager.FUSED_PROVIDER, LocationManager.NETWORK_PROVIDER)
            } else {
                listOf(LocationManager.NETWORK_PROVIDER, LocationManager.GPS_PROVIDER)
            }
        return candidates.firstOrNull { p ->
            try {
                lm.isProviderEnabled(p)
            } catch (e: Exception) {
                false
            }
        }
    }

    override fun onLocationChanged(location: Location) {
        val previous = last
        val moved = previous?.distanceTo(location)?.toDouble()
        // Rounded to roughly a hundred metres. The lane's question is which
        // place, and full precision would be a movement trace of a person
        // rather than a covariate on a measurement.
        Events.record(
            ctx,
            "location",
            "lat", round(location.latitude),
            "lon", round(location.longitude),
            "accuracy_m", location.accuracy.roundToInt(),
            "provider", location.provider,
            "moved_m", moved?.roundToInt(),
            "speed_mps", if (location.hasSpeed()) location.speed.toDouble() else null,
        )
        last = location
    }

    @Deprecated("Required by the pre-30 LocationListener contract")
    override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}

    override fun onProviderDisabled(provider: String) {
        Events.record(ctx, "lane_blocked", "lane", "location", "reason", "$provider disabled")
    }

    override fun onProviderEnabled(provider: String) {
        Events.record(ctx, "lane_resumed", "lane", "location", "provider", provider)
    }

    private fun round(v: Double): Double = Math.round(v * 1000.0) / 1000.0

    companion object {
        /** Ten minutes. A place lasts longer than that or it is not a place. */
        private const val INTERVAL_MILLIS = 10 * 60_000L

        /** Under this the phone is still where it was, whatever the fix says. */
        private const val MIN_DISTANCE_METRES = 150f
    }
}
