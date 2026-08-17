package dev.sinnix.phone.core

import android.content.Context
import android.content.SharedPreferences

/**
 * Persisted intent. Deliberately SharedPreferences rather than DataStore: boot
 * receivers, the watchdog alarm and the tile all read this synchronously on a
 * broadcast thread with no coroutine scope to suspend in, and a suspending
 * read there means either a blocking bridge or a wrong answer.
 */
object Prefs {

    private const val NAME = "sinnix-phone"

    private const val KEY_ENABLED = "capture_enabled"
    private const val KEY_ENERGY = "energy_state"
    private const val KEY_HUB = "hub_base_url"
    private const val KEY_EMA_PER_DAY = "ema_per_day"
    private const val KEY_LISTENER_ACK = "notification_listener_acknowledged"
    private const val KEY_AUTOSTART_ATTESTED_AT = "miui_autostart_attested_at"
    private const val KEY_SPEECH = "speech_lane_enabled"
    private const val KEY_RECEIVER = "receiver_host"
    private const val KEY_LOCATION = "location_lane_enabled"
    private const val KEY_HEALTH = "health_lane_enabled"
    private const val KEY_SLEEP_DETECT = "sleep_detect_enabled"
    private const val KEY_POWER = "power_lane_enabled"
    private const val KEY_HR_LIVE = "hr_live_lane_enabled"
    private const val KEY_USAGE = "usage_lane_enabled"
    private const val KEY_STREAM_EVENTS = "stream_events_enabled"
    private const val KEY_UPLOAD_CHUNKS = "upload_chunks_enabled"
    private const val KEY_UPLOAD_METERED = "upload_chunks_metered"
    private const val KEY_WAKE_HOUR = "wake_hour"
    private const val KEY_WAKE_MINUTE = "wake_minute"
    private const val KEY_WAKE_ARMED = "wake_armed"

    /**
     * The estate's own address. A default rather than a setting the operator
     * must find: this app has exactly one prime, and a hostname that resolves
     * on the tailnet is not a secret worth a config screen.
     */
    const val DEFAULT_HUB = "http://sinnix-prime:8880"

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.applicationContext.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    /**
     * Whether capture should be running.
     *
     * Boot and watchdog restarts consult it, so an operator who stops capture
     * from the UI does not get it resurrected ten minutes later, while an
     * unattended reboot resumes without anyone touching the screen.
     */
    fun enabled(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_ENABLED, true)

    fun setEnabled(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_ENABLED, value).apply()

    /** good / any / low — filters what the instrument offer policy proposes. */
    fun energyState(ctx: Context): String = prefs(ctx).getString(KEY_ENERGY, "any") ?: "any"

    fun setEnergyState(ctx: Context, value: String) =
        prefs(ctx).edit().putString(KEY_ENERGY, value).apply()

    fun hubBaseUrl(ctx: Context): String =
        prefs(ctx).getString(KEY_HUB, DEFAULT_HUB) ?: DEFAULT_HUB

    fun setHubBaseUrl(ctx: Context, value: String) =
        prefs(ctx).edit().putString(KEY_HUB, value).apply()

    /**
     * EMA samples per day. A knob with its cost stated rather than a silent
     * default: multiple samples a day is what makes EMA a method rather than a
     * diary, and one-a-day trades most of that away for compliance. The
     * operator gets to make that trade knowingly.
     */
    fun emaPerDay(ctx: Context): Int = prefs(ctx).getInt(KEY_EMA_PER_DAY, 3)

    fun setEmaPerDay(ctx: Context, value: Int) =
        prefs(ctx).edit().putInt(KEY_EMA_PER_DAY, value.coerceIn(0, 12)).apply()

    fun notificationListenerAcknowledged(ctx: Context): Boolean =
        prefs(ctx).getBoolean(KEY_LISTENER_ACK, false)

    fun setNotificationListenerAcknowledged(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_LISTENER_ACK, value).apply()

    /**
     * When the operator last attested that MIUI autostart is on. There is no
     * API to read it, so an attestation with a date is the honest substitute
     * for a check — and it is rendered as an attestation, never as a green
     * tick.
     */
    fun autostartAttestedAt(ctx: Context): Long =
        prefs(ctx).getLong(KEY_AUTOSTART_ATTESTED_AT, 0L)

    fun setAutostartAttestedAt(ctx: Context, ms: Long) =
        prefs(ctx).edit().putLong(KEY_AUTOSTART_ATTESTED_AT, ms).apply()

    /**
     * The always-on speech lane. On by default, like every other capture here.
     *
     * An earlier version of this shipped off-by-default with a comment about
     * how it "puts what was said on a wire" and so nothing but the operator
     * should switch it on. That was the wrong posture for this estate and the
     * operator said so: capture lanes are meant to be on, and to stay on. The
     * toggle exists because a switch is useful, not because the default should
     * be silence.
     *
     * "On" here means what it means for the recorder: started at boot, revived
     * by the watchdog, restarted when the app is opened. A lane that quietly
     * stops after a reboot is not an always-on lane, it is an intermittent one
     * that nobody has noticed yet.
     */
    fun speechLane(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_SPEECH, true)

    fun setSpeechLane(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_SPEECH, value).apply()

    /**
     * Where the speech receiver listens.
     *
     * Its own setting rather than derived from the hub URL: the hub is HTTP
     * through Caddy and the receiver is a raw TCP socket on a different port,
     * so one address standing for both would break the moment either moved.
     */
    fun receiverHost(ctx: Context): String =
        prefs(ctx).getString(KEY_RECEIVER, DEFAULT_RECEIVER) ?: DEFAULT_RECEIVER

    fun setReceiverHost(ctx: Context, value: String) =
        prefs(ctx).edit().putString(KEY_RECEIVER, value).apply()

    /**
     * Every capture lane in this file defaults ON, including these two.
     *
     * They used to default off, and the cost was not theoretical: the health
     * lane shipped fully written and produced nothing at all, so the Band 10
     * arrived to an empty `captures/phone/health` and the gap looked like a
     * pipeline problem rather than an unflipped boolean. A lane that has to be
     * switched on has a hole in it running back to the day it was written,
     * and nobody discovers that until they go looking for the data.
     *
     * Off is not the safe default here. The estate exists to capture; a lane
     * that is built and wired and then left dark is a bug with a settings
     * screen in front of it. Where a lane genuinely cannot run -- no Health
     * Connect installed, permission not granted -- the lane says so as an
     * event (`lane_blocked`), which is the honest way to be silent. The
     * toggles stay so a lane can be turned OFF deliberately; what changed is
     * which way they point when nobody has touched them.
     */
    fun locationLane(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_LOCATION, true)

    fun setLocationLane(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_LOCATION, value).apply()

    fun healthLane(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_HEALTH, true)

    fun setHealthLane(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_HEALTH, value).apply()

    /** Sleep inferred from the phone's own signals. Cheap, so on by default. */
    fun sleepDetect(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_SLEEP_DETECT, true)

    fun setSleepDetect(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_SLEEP_DETECT, value).apply()

    /** Live mirror of new event lines to prime's receiver. */
    fun streamEvents(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_STREAM_EVENTS, true)

    fun setStreamEvents(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_STREAM_EVENTS, value).apply()

    /**
     * The phone ships its own finalized ambient chunks to prime.
     *
     * On, like every lane here: an archive that only moves when something
     * else remembers to come and take it is an archive with holes in it, and
     * this one had them -- the drain's ssh transport dies with Termux, which
     * does not survive a reboot.
     */
    fun uploadChunks(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_UPLOAD_CHUNKS, true)

    fun setUploadChunks(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_UPLOAD_CHUNKS, value).apply()

    /**
     * Whether that upload may also run on a metered network.
     *
     * The one default-OFF switch in this file, and not for privacy: continuous
     * audio is ~43 MB an hour, and a phone that spends a day on cellular would
     * spend a data plan on files that are in no hurry. Chunks wait on the
     * device until wifi; they do not expire and nothing downstream needs them
     * within the hour. The live lanes (speech, events) push regardless -- they
     * are kilobytes and their value is their latency.
     */
    fun uploadOnMetered(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_UPLOAD_METERED, false)

    fun setUploadOnMetered(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_UPLOAD_METERED, value).apply()

    /** App/screen/keyguard history from the system's usage ledger. */
    fun usageLane(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_USAGE, true)

    fun setUsageLane(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_USAGE, value).apply()

    /** Live heart rate over BLE HRS, straight from the band. */
    fun heartRateLane(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_HR_LIVE, true)

    fun setHeartRateLane(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_HR_LIVE, value).apply()

    /** Battery and thermal as events. Free — the service already reads both. */
    fun powerLane(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_POWER, true)

    fun setPowerLane(ctx: Context, value: Boolean) =
        prefs(ctx).edit().putBoolean(KEY_POWER, value).apply()

    /** The sleep-inertia protocol's wake time, and whether it is armed. */
    fun wakeHour(ctx: Context): Int = prefs(ctx).getInt(KEY_WAKE_HOUR, 7)

    fun wakeMinute(ctx: Context): Int = prefs(ctx).getInt(KEY_WAKE_MINUTE, 0)

    fun wakeArmed(ctx: Context): Boolean = prefs(ctx).getBoolean(KEY_WAKE_ARMED, false)

    fun setWake(ctx: Context, hour: Int, minute: Int, armed: Boolean) =
        prefs(ctx)
            .edit()
            .putInt(KEY_WAKE_HOUR, hour.coerceIn(0, 23))
            .putInt(KEY_WAKE_MINUTE, minute.coerceIn(0, 59))
            .putBoolean(KEY_WAKE_ARMED, armed)
            .apply()

    /**
     * The receiver's address, defaulted to prime's tailnet name.
     *
     * Cleartext and unauthenticated, like the hub, because the tailnet is the
     * boundary — see the network-security config for why that is a considered
     * position rather than a leftover.
     */
    const val DEFAULT_RECEIVER = "sinnix-prime:8940"

    /**
     * The receiver targets to try, in order.
     *
     * The MagicDNS name stopped resolving on this phone on 2026-08-14 --
     * Tailscale was up, the tailnet route worked, and every stream to the
     * name silently failed for two days while a connect to the raw tailnet
     * address succeeded. The name stays first because names survive IP
     * reassignment; the literal address is the fallback that survives DNS.
     */
    fun receiverCandidates(ctx: Context): List<String> {
        val configured = receiverHost(ctx)
        val fallback = "100.114.9.64:8940"
        return if (configured == fallback) listOf(configured)
        else listOf(configured, fallback)
    }

    /**
     * The hub base URLs to try, in order -- the same lesson as
     * [receiverCandidates], which the hub did not get until 2026-08-17.
     *
     * The receiver learned to fall back to the raw tailnet address when
     * MagicDNS stopped resolving; the hub URL kept a single name, so every
     * HTTP call the app made -- glance, steering, jobs, intents, job answers,
     * ops actions -- died on UnknownHostException and fell back to the file
     * plane. Silently, because falling back is what those calls are supposed
     * to do when prime is unreachable, and a DNS miss is indistinguishable
     * from an absent prime unless something looks at the exception. Measured
     * from the phone: `ping sinnix-prime` -> unknown host, GET on
     * http://100.114.9.64:8880/phone/v1/ping -> 200.
     */
    fun hubCandidates(ctx: Context): List<String> {
        val configured = hubBaseUrl(ctx).trimEnd('/')
        val fallback = "http://100.114.9.64:8880"
        return if (configured == fallback) listOf(configured) else listOf(configured, fallback)
    }
}
