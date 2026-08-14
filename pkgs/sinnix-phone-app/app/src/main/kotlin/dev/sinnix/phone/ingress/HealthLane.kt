package dev.sinnix.phone.ingress

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ActiveCaloriesBurnedRecord
import androidx.health.connect.client.records.BloodPressureRecord
import androidx.health.connect.client.records.BodyTemperatureRecord
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.ElevationGainedRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.HeartRateVariabilityRmssdRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.Record
import androidx.health.connect.client.records.RespiratoryRateRecord
import androidx.health.connect.client.records.RestingHeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.SpeedRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.records.TotalCaloriesBurnedRecord
import androidx.health.connect.client.records.Vo2MaxRecord
import androidx.health.connect.client.records.WeightRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.time.Instant
import java.time.temporal.ChronoUnit
import kotlin.reflect.KClass
import org.json.JSONArray

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
 * band becomes events on the phone's own plane, drained by the transport that
 * already works.
 *
 * **Everything the band writes, at the resolution it writes it.** This lane
 * used to read three record types and then throw away most of what they
 * carried: heart rate collapsed to a mean/min/max per record, and a sleep
 * session recorded the NUMBER of its stages rather than the stages. Those two
 * are the band's most valuable outputs -- a per-minute HR series and a
 * light/deep/REM breakdown -- and both were being discarded at the point of
 * capture, where the loss is permanent. The aggregate is cheap to recompute
 * later; the samples cannot be recovered once not written. So the samples are
 * written, and the aggregate comes along as a convenience.
 *
 * Health Connect may not be installed at all (it is a separate APK on Android
 * 13), and its permissions are granted per record type. Both are ordinary
 * outcomes here rather than errors: the lane records why it produced nothing
 * so an empty week is explicable, which is exactly what the export lane never
 * did. A type the band does not produce simply reads back empty, which costs
 * one query and keeps the lane correct if a future device does produce it.
 */
object HealthLane {

    /**
     * Every record type worth asking for, not the three that were needed on
     * the day this was written.
     *
     * Mi Fitness declares writes for active calories, workout summary,
     * distance, elevation, exercise route, heart rate, blood oxygen, sleep and
     * speed; asking for only steps/HR/sleep left blood oxygen -- a signal the
     * band measures continuously and nothing else in the estate has -- on the
     * floor. The rest are here because the marginal cost of a granted-but-
     * empty record type is one query per hour, and the cost of noticing a
     * missing type months later is the months.
     */
    private val TYPES: List<KClass<out Record>> =
        listOf(
            StepsRecord::class,
            HeartRateRecord::class,
            SleepSessionRecord::class,
            OxygenSaturationRecord::class,
            HeartRateVariabilityRmssdRecord::class,
            RespiratoryRateRecord::class,
            RestingHeartRateRecord::class,
            ActiveCaloriesBurnedRecord::class,
            TotalCaloriesBurnedRecord::class,
            DistanceRecord::class,
            SpeedRecord::class,
            ElevationGainedRecord::class,
            ExerciseSessionRecord::class,
            Vo2MaxRecord::class,
            BodyTemperatureRecord::class,
            BloodPressureRecord::class,
            WeightRecord::class,
        )

    val PERMISSIONS: Set<String> = TYPES.map { HealthPermission.getReadPermission(it) }.toSet()

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
                // Named, not counted. "3 of 17 missing" sends someone to the
                // Health Connect UI to work out WHICH three; the names make a
                // partial grant actionable from the log alone.
                "missing", JSONArray(missing.map { it.substringAfterLast('.') }),
            )
            if (granted.isEmpty()) return 0
        }

        val start = Instant.ofEpochMilli(sinceMs).coerceAtLeast(Instant.now().minus(30, ChronoUnit.DAYS))
        val range = TimeRangeFilter.between(start, Instant.now())
        var written = 0

        written += read(ctx, client, range, StepsRecord::class, "health_steps") { r ->
            arrayOf(
                "count", r.count,
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        // The full sample series, not a summary of it. One row per RECORD
        // (Health Connect already batches samples into records), carrying every
        // sample's time and value as parallel arrays. Mean/min/max ride along
        // because they are free and most queries want them, but they are no
        // longer the only thing that survives.
        written += read(ctx, client, range, HeartRateRecord::class, "health_heart_rate") { r ->
            val bpms = r.samples.map { it.beatsPerMinute }
            arrayOf(
                "samples", bpms.size,
                "bpm", JSONArray(bpms),
                "sample_times", JSONArray(r.samples.map { Stamps.iso(it.time.toEpochMilli()) }),
                "mean_bpm", if (bpms.isEmpty()) null else bpms.average(),
                "min_bpm", bpms.minOrNull(),
                "max_bpm", bpms.maxOrNull(),
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        // Stages by name and boundary, which is the entire point of wearing the
        // band overnight. The previous version wrote `stages: 42` -- a count of
        // things it had just decided not to record.
        written += read(ctx, client, range, SleepSessionRecord::class, "health_sleep") { r ->
            val stages = JSONArray()
            r.stages.forEach { s ->
                stages.put(
                    org.json.JSONObject()
                        .put("stage", stageName(s.stage))
                        .put("start", Stamps.iso(s.startTime.toEpochMilli()))
                        .put("end", Stamps.iso(s.endTime.toEpochMilli()))
                        .put("minutes", (s.endTime.toEpochMilli() - s.startTime.toEpochMilli()) / 60_000L)
                )
            }
            arrayOf(
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "minutes", (r.endTime.toEpochMilli() - r.startTime.toEpochMilli()) / 60_000L,
                "stage_count", r.stages.size,
                "stages", stages,
                "title", r.title,
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, OxygenSaturationRecord::class, "health_spo2") { r ->
            arrayOf(
                "percentage", r.percentage.value,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, HeartRateVariabilityRmssdRecord::class, "health_hrv") { r ->
            arrayOf(
                "rmssd_ms", r.heartRateVariabilityMillis,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, RespiratoryRateRecord::class, "health_respiratory_rate") { r ->
            arrayOf(
                "breaths_per_minute", r.rate,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, RestingHeartRateRecord::class, "health_resting_heart_rate") { r ->
            arrayOf(
                "bpm", r.beatsPerMinute,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, ActiveCaloriesBurnedRecord::class, "health_active_calories") { r ->
            arrayOf(
                "kcal", r.energy.inKilocalories,
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, TotalCaloriesBurnedRecord::class, "health_total_calories") { r ->
            arrayOf(
                "kcal", r.energy.inKilocalories,
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, DistanceRecord::class, "health_distance") { r ->
            arrayOf(
                "meters", r.distance.inMeters,
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, SpeedRecord::class, "health_speed") { r ->
            arrayOf(
                "samples", r.samples.size,
                "mps", JSONArray(r.samples.map { it.speed.inMetersPerSecond }),
                "sample_times", JSONArray(r.samples.map { Stamps.iso(it.time.toEpochMilli()) }),
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, ElevationGainedRecord::class, "health_elevation") { r ->
            arrayOf(
                "meters", r.elevation.inMeters,
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, ExerciseSessionRecord::class, "health_exercise") { r ->
            arrayOf(
                "type", r.exerciseType,
                "title", r.title,
                "notes", r.notes,
                "start", Stamps.iso(r.startTime.toEpochMilli()),
                "end", Stamps.iso(r.endTime.toEpochMilli()),
                "minutes", (r.endTime.toEpochMilli() - r.startTime.toEpochMilli()) / 60_000L,
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, Vo2MaxRecord::class, "health_vo2max") { r ->
            arrayOf(
                "ml_per_min_per_kg", r.vo2MillilitersPerMinuteKilogram,
                "measurement_method", r.measurementMethod,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, BodyTemperatureRecord::class, "health_body_temperature") { r ->
            arrayOf(
                "celsius", r.temperature.inCelsius,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, BloodPressureRecord::class, "health_blood_pressure") { r ->
            arrayOf(
                "systolic_mmhg", r.systolic.inMillimetersOfMercury,
                "diastolic_mmhg", r.diastolic.inMillimetersOfMercury,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        written += read(ctx, client, range, WeightRecord::class, "health_weight") { r ->
            arrayOf(
                "kg", r.weight.inKilograms,
                "time", Stamps.iso(r.time.toEpochMilli()),
                "source", r.metadata.dataOrigin.packageName,
            )
        }

        return written
    }

    /**
     * One reader for every type.
     *
     * A type the device never writes reads back empty rather than throwing, and
     * a type whose permission was refused throws and is logged as unreadable --
     * neither takes the other sixteen down with it, which is why each call is
     * wrapped rather than the whole sync.
     */
    private suspend fun <T : Record> read(
        ctx: Context,
        client: HealthConnectClient,
        range: TimeRangeFilter,
        type: KClass<T>,
        kind: String,
        fields: (T) -> Array<Any?>,
    ): Int =
        try {
            val page = client.readRecords(ReadRecordsRequest(type, range))
            page.records.forEach { r -> Events.record(ctx, kind, *fields(r)) }
            page.records.size
        } catch (e: Exception) {
            Log.w(Storage.TAG, "health: $kind unreadable", e)
            0
        }

    private fun stageName(stage: Int): String =
        when (stage) {
            SleepSessionRecord.STAGE_TYPE_AWAKE -> "awake"
            SleepSessionRecord.STAGE_TYPE_AWAKE_IN_BED -> "awake_in_bed"
            SleepSessionRecord.STAGE_TYPE_OUT_OF_BED -> "out_of_bed"
            SleepSessionRecord.STAGE_TYPE_SLEEPING -> "sleeping"
            SleepSessionRecord.STAGE_TYPE_LIGHT -> "light"
            SleepSessionRecord.STAGE_TYPE_DEEP -> "deep"
            SleepSessionRecord.STAGE_TYPE_REM -> "rem"
            else -> "unknown"
        }
}
