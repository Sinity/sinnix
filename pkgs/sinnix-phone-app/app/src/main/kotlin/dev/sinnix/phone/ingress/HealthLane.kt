package dev.sinnix.phone.ingress

import android.content.Context
import android.util.Log
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ActiveCaloriesBurnedRecord
import androidx.health.connect.client.records.BasalMetabolicRateRecord
import androidx.health.connect.client.records.BloodGlucoseRecord
import androidx.health.connect.client.records.BloodPressureRecord
import androidx.health.connect.client.records.BodyFatRecord
import androidx.health.connect.client.records.BodyTemperatureRecord
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.FloorsClimbedRecord
import androidx.health.connect.client.records.HeightRecord
import androidx.health.connect.client.records.HydrationRecord
import androidx.health.connect.client.records.SkinTemperatureRecord
import androidx.health.connect.client.records.ElevationGainedRecord
import androidx.health.connect.client.records.ExerciseRouteResult
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
import androidx.health.connect.client.records.metadata.Device
import androidx.health.connect.client.records.metadata.Metadata
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
            FloorsClimbedRecord::class,
            SkinTemperatureRecord::class,
            BloodGlucoseRecord::class,
            BodyFatRecord::class,
            BasalMetabolicRateRecord::class,
            HeightRecord::class,
            HydrationRecord::class,
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
            HealthPermission.PERMISSION_READ_HEALTH_DATA_IN_BACKGROUND +
            ROUTES_PERMISSION

    /**
     * The grants that getGrantedPermissions can actually report.
     *
     * Exercise-route access is a tri-state Health Connect keeps to itself
     * ("Additional access" -> Always allow / Ask every time / Don't allow):
     * with Always allow set and working, the permission still never appears
     * in the granted set, so counting it made the lane report "1 of 20
     * missing" forever. It stays in PERMISSIONS so the request dialog OFFERS
     * it; the truth about route access is carried per record by the `route`
     * field, which is the only place Health Connect states it.
     */
    val QUERYABLE_PERMISSIONS: Set<String> = PERMISSIONS - ROUTES_PERMISSION

    fun availability(ctx: Context): String =
        when (HealthConnectClient.getSdkStatus(ctx)) {
            HealthConnectClient.SDK_AVAILABLE -> "available"
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> "needs update"
            else -> "not installed"
        }


    private const val ROUTES_PERMISSION = "android.permission.health.READ_EXERCISE_ROUTES"
    private const val PREFS = "sinnix-phone-health"
    private const val KEY_LEGACY_TOKEN = "changes_token"

    /**
     * Bump this to re-sweep everything Health Connect holds.
     *
     * Generation 1 swept 30 days, because that is all a client without
     * READ_HEALTH_DATA_HISTORY is permitted to see. Generation 2 removed the
     * lower bound -- and then read exactly one page per type, because
     * readRecords defaults to 1,000 records and nothing followed pageToken.
     * The lake shows the fingerprint: 1,390 Samsung heart-rate records is the
     * ~390 already held plus one full page, with the span in between silently
     * absent while the min/max timestamps made coverage look continuous.
     * Generation 3 exists to re-run that sweep with pagination actually
     * followed to the end.
     *
     * A re-sweep deliberately RE-EMITS records already captured. That is the
     * point: every event carries the record's Health Connect id, modification
     * time and the emit time, so a re-read is separable downstream and never
     * destructive.
     */
    private const val BACKFILL_GENERATION = 3

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
    /**
     * One sync at a time, ever. The scheduler launches sync on every
     * watchdog tick, and a quota-bound backfill sweep runs far longer than
     * one tick -- so without this gate a second sync starts while the first
     * is mid-sweep, both interleave through the shared page cursor, and the
     * pagination re-walks the same pages endlessly. Measured on 2026-08-16:
     * one heart-rate record emitted 188 times, a 1.4 GB day file that was
     * mostly duplicates, and every re-walked page paid for out of the same
     * rate quota the real sweep was starving on.
     */
    private val syncRunning = java.util.concurrent.atomic.AtomicBoolean(false)

    suspend fun sync(ctx: Context): Int {
        if (!syncRunning.compareAndSet(false, true)) return 0
        try {
            return syncInner(ctx)
        } finally {
            syncRunning.set(false)
        }
    }

    private suspend fun syncInner(ctx: Context): Int {
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
        val missing = QUERYABLE_PERMISSIONS - granted
        if (missing.isNotEmpty()) {
            Events.record(
                ctx,
                "lane_blocked",
                "lane", "health",
                "reason", "${missing.size} of ${QUERYABLE_PERMISSIONS.size} read grants missing",
                // Named, not counted. "3 of 17 missing" sends someone to the
                // Health Connect UI to work out WHICH three; the names make a
                // partial grant actionable from the log alone.
                "missing", JSONArray(missing.map { it.substringAfterLast('.') }),
            )
            if (granted.isEmpty()) return 0
        }

        // One retirement of the old single-token, whole-lane state. From here
        // every type carries its own token and its own sweep-complete flag, so
        // one failing or permission-revoked type stalls itself and nothing
        // else -- and a DeletionChange arrives on a feed that knows its type,
        // which the combined feed deliberately withholds for privacy.
        prefs(ctx).edit().remove(KEY_LEGACY_TOKEN).commit()

        rateLimited = false
        var written = 0
        // A type whose read permission is not granted can never be swept, and
        // asking anyway cost 72 identical `lane_blocked` events per type per
        // day -- six ungranted types, 432 events, all restating a fact that
        // does not change until someone taps a toggle. Skipped here and named
        // once in the state record below.
        val ungranted = TYPES.filter { HealthPermission.getReadPermission(it) in missing }.toSet()
        // Fresh data first, history second. A tick that starts with the
        // sweeps spends its quota on history before reading last night's
        // sleep; incrementals are a handful of calls for the swept types, so
        // they run first and the day's readings land every tick no matter
        // how far a backfill still has to crawl. (The provider's retained
        // history is actually small -- a few thousand heart-rate records, one
        // page of steps; the "254,720 StepsRecord records" this comment once
        // cited were the empty-pageToken loop re-reading one page 1,592
        // times.)
        val queryable = TYPES.filterNot { it in ungranted }
        val (swept, unswept) = queryable.partition { prefs(ctx).getBoolean(sweptKey(it), false) }
        for (type in swept) {
            written += incremental(ctx, client, type)
            if (rateLimited) break
        }
        // Steps sweeps LAST. It is the largest history by an order of
        // magnitude and the least dense signal per record; every other type
        // that finishes its sweep graduates to cheap incrementals, so the
        // sooner sleep and heart rate get their turn at the quota, the sooner
        // each new night lands within a tick of Mi Fitness writing it.
        for (type in unswept.sortedBy { it == StepsRecord::class }) {
            // Health Connect enforces a rolling API quota. Once one call is
            // rejected for quota, every later call this tick will be too --
            // the first run proved it with sixteen identical token failures
            // in two seconds. Stop the tick and let the next one continue
            // from the persisted page cursor.
            if (rateLimited) break
            written += sweep(ctx, client, type)
        }
        if (rateLimited) {
            Events.record(ctx, "lane_blocked", "lane", "health",
                "reason", "rate limited; resuming next tick")
        }

        // The lane's own state, every tick, because completion was previously
        // knowable ONLY from the one-shot `health_backfill` record a type
        // emits the instant it finishes. Miss that line -- an uninstall, a
        // day-file nobody kept, a receipt that never fired for a reason still
        // unexplained -- and "has this type's history been read to the end?"
        // becomes unanswerable forever, which is exactly the state the lake
        // was found in on 2026-08-17: ten types reading incrementally, and no
        // receipt anywhere proving any of them ever swept.
        //
        // A state record cannot be missed that way. It restates what is true
        // now, so the newest one always answers the question, and it costs one
        // line per tick against the 432 it replaces.
        val p = prefs(ctx)
        Events.record(
            ctx,
            "health_lane_state",
            "generation", BACKFILL_GENERATION,
            "swept", JSONArray(queryable.filter { p.getBoolean(sweptKey(it), false) }.map { it.simpleName }),
            "unswept", JSONArray(queryable.filterNot { p.getBoolean(sweptKey(it), false) }.map { it.simpleName }),
            "ungranted", JSONArray(ungranted.map { it.simpleName }),
            "rate_limited", rateLimited,
            "records", written,
        )
        return written
    }

    /** Set when Health Connect rejects a call for quota; cleared each sync(). */
    private var rateLimited = false

    private fun isRateLimit(e: Exception) =
        e.message?.contains("quota", ignoreCase = true) == true ||
            e.message?.contains("rate limit", ignoreCase = true) == true

    private fun sweptKey(type: KClass<out Record>) = "swept:$BACKFILL_GENERATION:${type.simpleName}"
    private fun tokenKey(type: KClass<out Record>) = "token:${type.simpleName}"
    private fun resumePageKey(type: KClass<out Record>) = "sweep_page:$BACKFILL_GENERATION:${type.simpleName}"
    private fun resumeTokenKey(type: KClass<out Record>) = "sweep_token:$BACKFILL_GENERATION:${type.simpleName}"
    private fun resumeCountKey(type: KClass<out Record>) = "sweep_count:$BACKFILL_GENERATION:${type.simpleName}"
    private fun resumePagesKey(type: KClass<out Record>) = "sweep_pages:$BACKFILL_GENERATION:${type.simpleName}"

    /**
     * Full-history sweep of one type: every page until pageToken runs out,
     * resumable across ticks.
     *
     * The changes token is taken at the START of the whole sweep -- before
     * the first page, persisted so a resumed sweep reuses it. Anything
     * inserted while the sweep crawls is then delivered again by the changes
     * feed rather than falling between the two -- a duplicate is a nuisance,
     * a hole is not recoverable.
     *
     * The page cursor is persisted after EVERY page, so a sweep the rolling
     * API quota interrupts resumes where it stopped instead of restarting
     * from page one. (Historical note: the numbers that once justified this
     * -- "StepsRecord ran 1,592 pages and 254,720 records" -- were the
     * empty-pageToken loop below re-reading a single ~162-record page 1,592
     * times. The real retained history fits in a handful of pages per type;
     * the cursor is still correct, it is just no longer load-bearing for
     * quarter-million-record histories that never existed.)
     *
     * "Swept" is still only written after the LAST page: a paused sweep is
     * unfinished and stays visibly unfinished. The generation-2 importer
     * marked itself complete after one unpaged read per type, which is how
     * five months of apparent coverage turned out to be two disconnected
     * blocks.
     */
    private suspend fun sweep(ctx: Context, client: HealthConnectClient, type: KClass<out Record>): Int {
        val p = prefs(ctx)
        var token = p.getString(resumeTokenKey(type), null)
        if (token == null) {
            token =
                try {
                    client.getChangesToken(ChangesTokenRequest(recordTypes = setOf(type)))
                } catch (e: Exception) {
                    rateLimited = rateLimited || isRateLimit(e)
                    Events.record(ctx, "lane_blocked", "lane", "health",
                        "reason", "token ${type.simpleName}: ${e.message}")
                    return 0
                }
            p.edit().putString(resumeTokenKey(type), token).commit()
        }
        // No lower bound. `before` asks for everything up to now, so the window
        // is whatever Health Connect still retains rather than a number we
        // guessed -- and guessing is how the previous 30 hid the Samsung era.
        val range = TimeRangeFilter.before(Instant.now())
        var written = p.getInt(resumeCountKey(type), 0)
        var pages = p.getInt(resumePagesKey(type), 0)
        var pageToken: String? = p.getString(resumePageKey(type), null)
        try {
            do {
                val page = client.readRecords(ReadRecordsRequest(type, range, pageToken = pageToken))
                pages++
                written += page.records.count { emit(ctx, it) }
                // The client's pageToken is nullable but, on the Android 13
                // APK-provider path, never null: it is copied straight off a
                // proto3 string field (ProtoToReadRecordsResponse.kt), whose
                // absent-value is "". Passing "" back in reads page one again,
                // so a null-only loop condition re-walks the whole history
                // forever -- measured 2026-08-17 as one heart-rate record
                // emitted 473 times, an 18-second full-history cycle sustained
                // for hours, and a 3.3 GB day file.
                pageToken = page.pageToken?.takeUnless { it.isEmpty() }
                p.edit().putString(resumePageKey(type), pageToken)
                    .putInt(resumeCountKey(type), written)
                    .putInt(resumePagesKey(type), pages).commit()
            } while (pageToken != null)
        } catch (e: Exception) {
            rateLimited = rateLimited || isRateLimit(e)
            Log.w(Storage.TAG, "health: ${type.simpleName} sweep paused on page ${pages + 1}", e)
            Events.record(ctx, "health_sweep_failed", "type", type.simpleName,
                "pages_read", pages, "records_emitted", written,
                "resumable", true, "reason", e.message)
            return written
        }
        p.edit().putString(tokenKey(type), token).putBoolean(sweptKey(type), true)
            .remove(resumePageKey(type)).remove(resumeTokenKey(type))
            .remove(resumeCountKey(type)).remove(resumePagesKey(type)).commit()
        Events.record(ctx, "health_backfill", "type", type.simpleName, "records", written,
            "pages", pages, "generation", BACKFILL_GENERATION, "window", "all")
        return written
    }

    /** Everything inserted for one type since its stored token, following `hasMore` to the end. */
    private suspend fun incremental(ctx: Context, client: HealthConnectClient, type: KClass<out Record>): Int {
        var token = prefs(ctx).getString(tokenKey(type), null)
            ?: return sweep(ctx, client, type)
        var written = 0
        while (true) {
            val response =
                try {
                    client.getChanges(token)
                } catch (e: Exception) {
                    rateLimited = rateLimited || isRateLimit(e)
                    Log.w(Storage.TAG, "health: ${type.simpleName} changes unreadable", e)
                    return written
                }
            if (response.changesTokenExpired) {
                // Health Connect drops tokens after ~30 days of not being
                // asked. Falling back to a window sweep is the documented
                // recovery and re-establishes a token in the same pass.
                Events.record(ctx, "health_token_expired", "type", type.simpleName, "action", "sweep")
                prefs(ctx).edit().remove(tokenKey(type)).remove(sweptKey(type)).commit()
                return written + sweep(ctx, client, type)
            }
            response.changes.forEach { change ->
                when (change) {
                    is UpsertionChange -> if (emit(ctx, change.record)) written++
                    // The id is the entire value of a deletion: it is what
                    // lets a downstream store tombstone the right record
                    // instead of holding a count of unidentifiable losses.
                    is DeletionChange ->
                        Events.record(ctx, "health_deletion",
                            "type", type.simpleName, "record_id", change.recordId)
                    else -> Unit
                }
            }
            token = response.nextChangesToken
            if (!response.hasMore) break
        }
        // Only now, and only because every page above was read without
        // throwing. A token advanced past unread changes is data loss with no
        // symptom.
        prefs(ctx).edit().putString(tokenKey(type), token).commit()
        return written
    }

    /**
     * One record to one event, dispatched on its own type.
     *
     * Returns false for a type nobody has written an emitter for, so an
     * unhandled type is counted as unhandled rather than counted as captured.
     */
    /**
     * The identity block every event carries, straight off the record's
     * Health Connect metadata.
     *
     * `record_id` is what makes two reads of one record recognizable as one
     * record: the band's overnight session is UPDATED as Mi Fitness refines
     * it, and the changes feed re-delivers each revision. Without the id the
     * lake shows three sleeps where there was one night growing -- which is
     * exactly what the 2026-08-16 rows show. `modified` orders the revisions,
     * `recording_method` separates a sensor reading from a manual entry, and
     * the device fields distinguish a Galaxy Watch record from one Samsung
     * Health synthesized itself.
     */
    private fun meta(r: Record): Array<Any?> {
        val m = r.metadata
        return arrayOf(
            "source", m.dataOrigin.packageName,
            "record_id", m.id,
            "modified", Stamps.iso(m.lastModifiedTime.toEpochMilli()),
            "client_record_id", m.clientRecordId,
            "client_record_version", m.clientRecordVersion,
            "recording_method", recordingMethodName(m.recordingMethod),
            "device_manufacturer", m.device?.manufacturer,
            "device_model", m.device?.model,
            "device_type", m.device?.let { deviceTypeName(it.type) },
        )
    }

    private fun recordingMethodName(method: Int): String =
        when (method) {
            Metadata.RECORDING_METHOD_ACTIVELY_RECORDED -> "actively_recorded"
            Metadata.RECORDING_METHOD_AUTOMATICALLY_RECORDED -> "automatically_recorded"
            Metadata.RECORDING_METHOD_MANUAL_ENTRY -> "manual_entry"
            else -> "unknown"
        }

    private fun deviceTypeName(type: Int): String =
        when (type) {
            Device.TYPE_WATCH -> "watch"
            Device.TYPE_PHONE -> "phone"
            Device.TYPE_SCALE -> "scale"
            Device.TYPE_RING -> "ring"
            Device.TYPE_HEAD_MOUNTED -> "head_mounted"
            Device.TYPE_FITNESS_BAND -> "fitness_band"
            Device.TYPE_CHEST_STRAP -> "chest_strap"
            Device.TYPE_SMART_DISPLAY -> "smart_display"
            else -> "unknown"
        }

    private fun emit(ctx: Context, r: Record): Boolean {
        when (r) {
            is StepsRecord ->
                Events.record(ctx, "health_steps",
                    "count", r.count,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

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
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))
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
                    "title", r.title, *meta(r))
            }

            is OxygenSaturationRecord ->
                Events.record(ctx, "health_spo2", "percentage", r.percentage.value,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is HeartRateVariabilityRmssdRecord ->
                Events.record(ctx, "health_hrv", "rmssd_ms", r.heartRateVariabilityMillis,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is RespiratoryRateRecord ->
                Events.record(ctx, "health_respiratory_rate", "breaths_per_minute", r.rate,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is RestingHeartRateRecord ->
                Events.record(ctx, "health_resting_heart_rate", "bpm", r.beatsPerMinute,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is ActiveCaloriesBurnedRecord ->
                Events.record(ctx, "health_active_calories", "kcal", r.energy.inKilocalories,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

            is TotalCaloriesBurnedRecord ->
                Events.record(ctx, "health_total_calories", "kcal", r.energy.inKilocalories,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

            is DistanceRecord ->
                Events.record(ctx, "health_distance", "meters", r.distance.inMeters,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

            is SpeedRecord ->
                Events.record(ctx, "health_speed",
                    "samples", r.samples.size,
                    "mps", JSONArray(r.samples.map { it.speed.inMetersPerSecond }),
                    "sample_times", JSONArray(r.samples.map { Stamps.iso(it.time.toEpochMilli()) }),
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

            is ElevationGainedRecord ->
                Events.record(ctx, "health_elevation", "meters", r.elevation.inMeters,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

            is ExerciseSessionRecord ->
                Events.record(ctx, "health_exercise",
                    "type", r.exerciseType, "title", r.title, "notes", r.notes,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()),
                    "minutes", (r.endTime.toEpochMilli() - r.startTime.toEpochMilli()) / 60_000L,
                    "segments", r.segments.size, "laps", r.laps.size,
                    // A route written by another app returns ConsentRequired
                    // from a background read no matter what is granted; the
                    // per-route consent is a foreground UI act. So this field
                    // is a pending-work marker, not a route: "consent_required"
                    // means GPS points exist and are one deliberate tap away
                    // from being lost with the session's retention.
                    "route",
                    when (r.exerciseRouteResult) {
                        is ExerciseRouteResult.Data -> "data"
                        is ExerciseRouteResult.ConsentRequired -> "consent_required"
                        else -> "none"
                    },
                    *meta(r))

            is Vo2MaxRecord ->
                Events.record(ctx, "health_vo2max",
                    "ml_per_min_per_kg", r.vo2MillilitersPerMinuteKilogram,
                    "measurement_method", r.measurementMethod,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is BodyTemperatureRecord ->
                Events.record(ctx, "health_body_temperature", "celsius", r.temperature.inCelsius,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is BloodPressureRecord ->
                Events.record(ctx, "health_blood_pressure",
                    "systolic_mmhg", r.systolic.inMillimetersOfMercury,
                    "diastolic_mmhg", r.diastolic.inMillimetersOfMercury,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is WeightRecord ->
                Events.record(ctx, "health_weight", "kg", r.weight.inKilograms,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is FloorsClimbedRecord ->
                Events.record(ctx, "health_floors_climbed", "floors", r.floors,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

            // Baseline plus per-delta series, mirroring how HR keeps its
            // samples: the deltas are the measurement, the baseline is the
            // reference they are relative to.
            is SkinTemperatureRecord -> {
                val deltas = JSONArray()
                r.deltas.forEach { d ->
                    deltas.put(
                        org.json.JSONObject()
                            .put("time", Stamps.iso(d.time.toEpochMilli()))
                            .put("delta_celsius", d.delta.inCelsius))
                }
                Events.record(ctx, "health_skin_temperature",
                    "baseline_celsius", r.baseline?.inCelsius,
                    "deltas", deltas,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))
            }

            is BloodGlucoseRecord ->
                Events.record(ctx, "health_blood_glucose",
                    "mmol_per_l", r.level.inMillimolesPerLiter,
                    "specimen_source", r.specimenSource,
                    "relation_to_meal", r.relationToMeal,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is BodyFatRecord ->
                Events.record(ctx, "health_body_fat", "percent", r.percentage.value,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is BasalMetabolicRateRecord ->
                Events.record(ctx, "health_basal_metabolic_rate",
                    "kcal_per_day", r.basalMetabolicRate.inKilocaloriesPerDay,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is HeightRecord ->
                Events.record(ctx, "health_height", "meters", r.height.inMeters,
                    "time", Stamps.iso(r.time.toEpochMilli()), *meta(r))

            is HydrationRecord ->
                Events.record(ctx, "health_hydration", "liters", r.volume.inLiters,
                    "start", Stamps.iso(r.startTime.toEpochMilli()),
                    "end", Stamps.iso(r.endTime.toEpochMilli()), *meta(r))

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
