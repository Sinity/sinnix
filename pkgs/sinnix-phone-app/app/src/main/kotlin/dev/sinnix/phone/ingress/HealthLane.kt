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
import androidx.health.connect.client.changes.DeletionChange
import androidx.health.connect.client.changes.UpsertionChange
import androidx.health.connect.client.request.ChangesTokenRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.time.Instant
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

    /**
     * Every read permission, plus the two that are not record types.
     *
     * HISTORY is what lifts Health Connect's silent 30-day truncation, and
     * BACKGROUND is what keeps the lane readable from the watchdog receiver it
     * actually runs in. Both are in the set rather than treated as optional so
     * a missing one is NAMED in lane_blocked instead of quietly halving what
     * the lane can see.
     */
    val PERMISSIONS: Set<String> =
        TYPES.map { HealthPermission.getReadPermission(it) }.toSet() +
            HealthPermission.PERMISSION_READ_HEALTH_DATA_HISTORY +
            HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND

    fun availability(ctx: Context): String =
        when (HealthConnectClient.getSdkStatus(ctx)) {
            HealthConnectClient.SDK_AVAILABLE -> "available"
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> "needs update"
            else -> "not installed"
        }


    private const val PREFS = "sinnix-phone-health"
    private const val KEY_TOKEN = "changes_token"
    private const val KEY_BACKFILL_GEN = "backfill_generation"

    /**
     * Bump this to re-sweep everything Health Connect holds.
     *
     * Generation 1 swept 30 days, because that is all a client without
     * READ_HEALTH_DATA_HISTORY is permitted to see. Generation 2 sweeps with no
     * lower bound at all, which with that permission granted reaches the whole
     * retained history -- on this device that includes Samsung Health records
     * from the Galaxy Watch 5 era, predating the band entirely.
     *
     * A re-sweep deliberately RE-EMITS records already captured. That is the
     * point: the operator asked for the old data alongside what we hold so the
     * two can be compared, and a lane that refuses to repeat itself cannot
     * answer "did this change?". Every event carries both the record's own
     * timestamps and the emit time, so duplicates are separable downstream and
     * a re-read is never destructive.
     */
    private const val BACKFILL_GENERATION = 2

    private fun prefs(ctx: Context) = ctx.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /**
     * Pull everything Health Connect has gained since the last successful read.
     *
     * Driven by a CHANGES TOKEN rather than a timestamp cursor, and the
     * difference is not cosmetic. Health Connect indexes a record by when the
     * measurement happened, but Mi Fitness only writes when the band syncs --
     * so a sync at 21:44 inserts a whole day of readings stamped 08:00, 08:01,
     * 08:02. A cursor over measurement time asks "anything since 20:44?" and
     * gets nothing, then advances past the window, and that day is lost
     * permanently. The changes feed is ordered by INSERTION, so late-arriving
     * backfill is exactly what it is designed to deliver.
     *
     * The token only advances on a successful read. A sync that fails, or one
     * that runs before permissions exist, leaves the token where it was and
     * retries the same changes next tick -- the previous version stamped its
     * cursor BEFORE attempting, so every failure silently dropped an hour.
     *
     * Returns how many records landed, so a caller can tell "nothing new" from
     * "nothing readable" — two states an empty return would conflate.
     */
    suspend fun sync(ctx: Context): Int {
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

        val stored = prefs(ctx).getString(KEY_TOKEN, null)
        val gen = prefs(ctx).getInt(KEY_BACKFILL_GEN, 0)
        // A widened window is indistinguishable from a first run as far as the
        // sweep is concerned, so the generation drives both. This is what makes
        // "pull more history" a constant change rather than a manual re-install.
        return if (stored == null || gen < BACKFILL_GENERATION) {
            backfill(ctx, client)
        } else {
            incremental(ctx, client, stored)
        }
    }

    /**
     * First run, or recovery after an expired token: sweep a wide window by
     * measurement time, then take a token so every later run is incremental.
     *
     * The token is taken BEFORE the sweep on purpose. Anything inserted during
     * the sweep is then delivered again by the changes feed rather than falling
     * between the two -- a duplicate is a nuisance, a hole is not recoverable.
     */
    private suspend fun backfill(ctx: Context, client: HealthConnectClient): Int {
        val token =
            try {
                client.getChangesToken(ChangesTokenRequest(recordTypes = TYPES.toSet()))
            } catch (e: Exception) {
                Events.record(ctx, "lane_blocked", "lane", "health", "reason", "token: ${e.message}")
                return 0
            }
        // No lower bound. `before` asks for everything up to now, so the window
        // is whatever Health Connect still retains rather than a number we
        // guessed -- and guessing is how the previous 30 hid the Samsung era.
        val range = TimeRangeFilter.before(Instant.now())
        var written = 0
        TYPES.forEach { type ->
            written +=
                try {
                    val page = client.readRecords(ReadRecordsRequest(type, range))
                    page.records.count { emit(ctx, it) }
                } catch (e: Exception) {
                    Log.w(Storage.TAG, "health: ${type.simpleName} unreadable", e)
                    0
                }
        }
        prefs(ctx).edit().putString(KEY_TOKEN, token).putInt(KEY_BACKFILL_GEN, BACKFILL_GENERATION).apply()
        Events.record(ctx, "health_backfill", "records", written, "generation", BACKFILL_GENERATION, "window", "all")
        return written
    }

    /** Everything inserted since the stored token, following `hasMore` to the end. */
    private suspend fun incremental(ctx: Context, client: HealthConnectClient, startToken: String): Int {
        var token = startToken
        var written = 0
        var deleted = 0
        while (true) {
            val response =
                try {
                    client.getChanges(token)
                } catch (e: Exception) {
                    Log.w(Storage.TAG, "health: changes unreadable", e)
                    return written
                }
            if (response.changesTokenExpired) {
                // Health Connect drops tokens after ~30 days of not being
                // asked. Falling back to a window sweep is the documented
                // recovery and re-establishes a token in the same pass.
                Events.record(ctx, "health_token_expired", "action", "backfill")
                prefs(ctx).edit().remove(KEY_TOKEN).apply()
                return written + backfill(ctx, client)
            }
            response.changes.forEach { change ->
                when (change) {
                    is UpsertionChange -> if (emit(ctx, change.record)) written++
                    is DeletionChange -> deleted++
                    else -> Unit
                }
            }
            token = response.nextChangesToken
            if (!response.hasMore) break
        }
        // Only now, and only because every page above was read without
        // throwing. A token advanced past unread changes is data loss with no
        // symptom.
        prefs(ctx).edit().putString(KEY_TOKEN, token).apply()
        if (deleted > 0) Events.record(ctx, "health_deletions", "count", deleted)
        return written
    }

    /**
     * One record to one event, dispatched on its own type.
     *
     * Returns false for a type nobody has written an emitter for, so an
     * unhandled type is counted as unhandled rather than counted as captured.
     */
    private fun emit(ctx: Context, r: Record): Boolean {
        val src = r.metadata.dataOrigin.packageName
        when (r) {
            is StepsRecord ->
                Events.record(ctx, "health_steps",
                    "count", r.count,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)

            // The full sample series, not a summary of it. Mean/min/max ride
            // along because they are free and most queries want them, but they
            // are no longer the only thing that survives.
            is HeartRateRecord -> {
                val bpms = r.samples.map { it.beatsPerMinute }
                Events.record(ctx, "health_heart_rate",
                    "samples", bpms.size,
                    "bpm", JSONArray(bpms),
                    "sample_times", JSONArray(r.samples.map { Stamps.iso(it.time.toEpochMilli()) }),
                    "mean_bpm", if (bpms.isEmpty()) null else bpms.average(),
                    "min_bpm", bpms.minOrNull(),
                    "max_bpm", bpms.maxOrNull(),
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)
            }

            // Stages by name and boundary, which is the entire point of wearing
            // the band overnight. The previous version wrote `stages: 42` -- a
            // count of things it had just decided not to record.
            is SleepSessionRecord -> {
                val stages = JSONArray()
                r.stages.forEach { st ->
                    stages.put(
                        org.json.JSONObject()
                            .put("stage", stageName(st.stage))
                            .put("start", Stamps.iso(st.startTime.toEpochMilli()))
                            .put("end", Stamps.iso(st.endTime.toEpochMilli()))
                            .put("minutes", (st.endTime.toEpochMilli() - st.startTime.toEpochMilli()) / 60_000L))
                }
                Events.record(ctx, "health_sleep",
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()),
                    "minutes", (r.endTime.toEpochMilli() - r.startTime.toEpochMilli()) / 60_000L,
                    "stage_count", r.stages.size, "stages", stages,
                    "title", r.title, "source", src)
            }

            is OxygenSaturationRecord ->
                Events.record(ctx, "health_spo2", "percentage", r.percentage.value,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is HeartRateVariabilityRmssdRecord ->
                Events.record(ctx, "health_hrv", "rmssd_ms", r.heartRateVariabilityMillis,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is RespiratoryRateRecord ->
                Events.record(ctx, "health_respiratory_rate", "breaths_per_minute", r.rate,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is RestingHeartRateRecord ->
                Events.record(ctx, "health_resting_heart_rate", "bpm", r.beatsPerMinute,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is ActiveCaloriesBurnedRecord ->
                Events.record(ctx, "health_active_calories", "kcal", r.energy.inKilocalories,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)

            is TotalCaloriesBurnedRecord ->
                Events.record(ctx, "health_total_calories", "kcal", r.energy.inKilocalories,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)

            is DistanceRecord ->
                Events.record(ctx, "health_distance", "meters", r.distance.inMeters,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)

            is SpeedRecord ->
                Events.record(ctx, "health_speed",
                    "samples", r.samples.size,
                    "mps", JSONArray(r.samples.map { it.speed.inMetersPerSecond }),
                    "sample_times", JSONArray(r.samples.map { Stamps.iso(it.time.toEpochMilli()) }),
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)

            is ElevationGainedRecord ->
                Events.record(ctx, "health_elevation", "meters", r.elevation.inMeters,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), "source", src)

            is ExerciseSessionRecord ->
                Events.record(ctx, "health_exercise",
                    "type", r.exerciseType, "title", r.title, "notes", r.notes,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()),
                    "minutes", (r.endTime.toEpochMilli() - r.startTime.toEpochMilli()) / 60_000L,
                    "source", src)

            is Vo2MaxRecord ->
                Events.record(ctx, "health_vo2max",
                    "ml_per_min_per_kg", r.vo2MillilitersPerMinuteKilogram,
                    "measurement_method", r.measurementMethod,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is BodyTemperatureRecord ->
                Events.record(ctx, "health_body_temperature", "celsius", r.temperature.inCelsius,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is BloodPressureRecord ->
                Events.record(ctx, "health_blood_pressure",
                    "systolic_mmhg", r.systolic.inMillimetersOfMercury,
                    "diastolic_mmhg", r.diastolic.inMillimetersOfMercury,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            is WeightRecord ->
                Events.record(ctx, "health_weight", "kg", r.weight.inKilograms,
                    "time", Stamps.iso(r.time.toEpochMilli()), "source", src)

            else -> return false
        }
        return true
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
