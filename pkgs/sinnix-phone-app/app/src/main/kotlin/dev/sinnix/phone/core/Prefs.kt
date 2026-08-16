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
}
