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
}
