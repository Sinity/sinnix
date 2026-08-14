package dev.sinnix.phone.ingress

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Health, read from the API rather than waited on.
 *
 * The motivation is a measurement, not a preference: `captures/phone/health`
 * in the lake is **empty**. The drain has a lane for it and pulls from
 * `/sdcard/HealthConnectExport/`, and that scheduled export has never once
 * landed a file. A lane that depends on the operator remembering to configure
 * an export in another app, on a schedule that other app controls, is a lane
 * that reports nothing and looks configured.
 *
 * Reading Health Connect directly removes the middle step. What arrives in the
 * band — steps, heart rate, sleep sessions — becomes events on the phone's own
 * plane, drained by the transport that already works.
 *
 * Health Connect may not be installed at all (it is a separate APK on Android
 * 13), and its permissions are granted per record type. Both are ordinary
 * outcomes here rather than errors: the lane records why it produced nothing
 * so an empty week is explicable, which is exactly what the export lane never
 * did.
 */
object HealthLane {

    val PERMISSIONS =
        setOf(
            HealthPermission.getReadPermission(StepsRecord::class),
            HealthPermission.getReadPermission(HeartRateRecord::class),
            HealthPermission.getReadPermission(SleepSessionRecord::class),
        )

    fun availability(ctx: Context): String =
        when (HealthConnectClient.getSdkStatus(ctx)) {
            HealthConnectClient.SDK_AVAILABLE -> "available"
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> "needs update"
            else -> "not installed"
        }

    /**
     * Pull whatever is new since [sinceMs] and write it to the events plane.
     *
     * Returns how many records landed, so a caller can tell "nothing new" from
     * "nothing readable" — two states an empty return would conflate.
     */
    suspend fun sync(ctx: Context, sinceMs: Long): Int {
        if (!Prefs.healthLane(ctx)) return 0
        if (HealthConnectClient.getSdkStatus(ctx) != HealthConnectClient.SDK_AVAILABLE) {
            Events.record(ctx, "lane_blocked", "lane", "health", "reason", availability(ctx))
            return 0
        }
        val client =
            try {
                HealthConnectClient.getOrCreate(ctx)
            } catch (e: Exception) {
                Events.record(ctx, "lane_blocked", "lane", "health", "reason", "client: ${e.message}")
                return 0
            }

        val granted =
            try {
                client.permissionController.getGrantedPermissions()
            } catch (e: Exception) {
                emptySet<String>()
            }
        val missing = PERMISSIONS - granted
        if (missing.isNotEmpty()) {
            Events.record(
                ctx,
                "lane_blocked",
                "lane", "health",
                "reason", "${missing.size} of ${PERMISSIONS.size} read grants missing",
            )
            if (granted.isEmpty()) return 0
        }

        val start = Instant.ofEpochMilli(sinceMs).coerceAtLeast(Instant.now().minus(30, ChronoUnit.DAYS))
        val range = TimeRangeFilter.between(start, Instant.now())
        var written = 0

        written += readSteps(ctx, client, range)
        written += readHeartRate(ctx, client, range)
        written += readSleep(ctx, client, range)
        return written
    }

    private suspend fun readSteps(ctx: Context, client: HealthConnectClient, range: TimeRangeFilter): Int =
        try {
            val page = client.readRecords(ReadRecordsRequest(StepsRecord::class, range))
            page.records.forEach { r ->
                Events.record(
                    ctx,
                    "health_steps",
                    "count", r.count,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()),
                    "source", r.metadata.dataOrigin.packageName,
                )
            }
            page.records.size
        } catch (e: Exception) {
            Log.w(Storage.TAG, "health: steps unreadable", e)
            0
        }

    private suspend fun readHeartRate(ctx: Context, client: HealthConnectClient, range: TimeRangeFilter): Int =
        try {
            val page = client.readRecords(ReadRecordsRequest(HeartRateRecord::class, range))
            var n = 0
            page.records.forEach { r ->
                // One record per sample would be tens of thousands of rows a
                // day for a signal whose daily shape is what matters; the
                // session's own aggregate is what a join wants.
                val bpms = r.samples.map { it.beatsPerMinute }
                if (bpms.isEmpty()) return@forEach
                Events.record(
                    ctx,
                    "health_heart_rate",
                    "samples", bpms.size,
                    "mean_bpm", bpms.average(),
                    "min_bpm", bpms.min(),
                    "max_bpm", bpms.max(),
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()),
                    "source", r.metadata.dataOrigin.packageName,
                )
                n++
            }
            n
        } catch (e: Exception) {
            Log.w(Storage.TAG, "health: heart rate unreadable", e)
            0
        }

    private suspend fun readSleep(ctx: Context, client: HealthConnectClient, range: TimeRangeFilter): Int =
        try {
            val page = client.readRecords(ReadRecordsRequest(SleepSessionRecord::class, range))
            page.records.forEach { r ->
                Events.record(
                    ctx,
                    "health_sleep",
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()),
                    "minutes", (r.endTime.toEpochMilli() - r.startTime.toEpochMilli()) / 60_000L,
                    "stages", r.stages.size,
                    "source", r.metadata.dataOrigin.packageName,
                )
            }
            page.records.size
        } catch (e: Exception) {
            Log.w(Storage.TAG, "health: sleep unreadable", e)
            0
        }
}
