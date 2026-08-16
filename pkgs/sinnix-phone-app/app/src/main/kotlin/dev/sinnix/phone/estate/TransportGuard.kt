package dev.sinnix.phone.estate

import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import dev.sinnix.phone.core.Events
import java.net.InetSocketAddress
import java.net.Socket

/**
 * Keeps prime's way in open.
 *
 * Prime cannot reach this phone on its own initiative: the app is a client, and
 * every inbound path belongs to something less durable than the app itself.
 * Termux's sshd is supervised by runit, which MIUI stops at boot when it
 * declines to honour Termux:Boot; adbd's TCP listener does not survive a
 * reboot at all and cannot be made to, because `persist.adb.tcp.port` is
 * refused to the shell uid. Tailscale is a VPN service the platform is free to
 * kill.
 *
 * When those fall over together the phone is perfectly healthy and perfectly
 * unreachable, which is what happened over 2026-08-15/16: capture kept
 * recording the whole time (health, battery, location all still being written)
 * and none of it could be drained, because prime had no way to ask.
 *
 * The app is the right place to fix that. It is a foreground service with a
 * watchdog alarm and it is the one component on this device MIUI reliably lets
 * live, so it can watch the things that cannot watch themselves. It repairs
 * what it can reach — sshd, via Termux's RUN_COMMAND — and reports what it
 * cannot, so an unreachable phone at least explains itself the moment contact
 * resumes.
 */
object TransportGuard {

    private const val TAG = "TransportGuard"
    private const val SSHD_PORT = 8022
    private const val PROBE_TIMEOUT_MILLIS = 1500

    private const val TERMUX_PACKAGE = "com.termux"
    private const val TERMUX_RUN_COMMAND_SERVICE = "com.termux.app.RunCommandService"
    private const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"
    private const val EXTRA_COMMAND_PATH = "com.termux.RUN_COMMAND_PATH"
    private const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
    private const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"

    private const val TERMUX_PREFIX = "/data/data/com.termux/files/usr"

    /** Called from Scheduler.tick, on the watchdog's ~10 minute wakeup. */
    fun tick(ctx: Context) {
        val sshdUp = probeLocal(SSHD_PORT)
        val vpnUp = vpnActive(ctx)

        if (!sshdUp) {
            val attempted = startSshd(ctx)
            Events.record(
                ctx, "transport_repair",
                "transport", "sshd",
                "attempted", attempted.toString(),
            )
        }

        // Recorded every sweep, not only on failure. A gap in the drain is
        // read backwards later, and "was the way in open at the time" is only
        // answerable if the answer was written down while it was true.
        Events.record(
            ctx, "transport_health",
            "sshd", sshdUp.toString(),
            "vpn", vpnUp.toString(),
        )
    }

    /**
     * Is something listening on loopback?
     *
     * Loopback rather than the tailnet address: this asks whether the service
     * is alive, and answering that must not depend on the VPN, which is one of
     * the things being diagnosed.
     */
    private fun probeLocal(port: Int): Boolean =
        try {
            Socket().use {
                it.connect(InetSocketAddress("127.0.0.1", port), PROBE_TIMEOUT_MILLIS)
                true
            }
        } catch (e: Exception) {
            false
        }

    /**
     * Ask Termux to bring its supervisor and sshd back up.
     *
     * `sv up` alone is not enough after MIUI has stopped Termux: runsvdir, the
     * supervisor itself, is gone, so the service directory has nobody reading
     * it. Start the supervisor first and then raise sshd specifically —
     * `ambient` deliberately stays down, having been retired in favour of this
     * app's own recorder, and a blanket start would resurrect it into competing
     * for the microphone.
     */
    private fun startSshd(ctx: Context): Boolean =
        try {
            val script =
                "export PATH=$TERMUX_PREFIX/bin:\$PATH; " +
                    "pgrep -f runsvdir >/dev/null 2>&1 || " +
                    "nohup $TERMUX_PREFIX/bin/runsvdir -P $TERMUX_PREFIX/var/service >/dev/null 2>&1 & " +
                    "sleep 2; $TERMUX_PREFIX/bin/sv up $TERMUX_PREFIX/var/service/sshd"
            val intent = Intent(ACTION_RUN_COMMAND).apply {
                setClassName(TERMUX_PACKAGE, TERMUX_RUN_COMMAND_SERVICE)
                putExtra(EXTRA_COMMAND_PATH, "$TERMUX_PREFIX/bin/sh")
                putExtra(EXTRA_ARGUMENTS, arrayOf("-c", script))
                putExtra(EXTRA_BACKGROUND, true)
            }
            ctx.startService(intent)
            true
        } catch (e: Exception) {
            // Termux absent, RUN_COMMAND not permitted, or allow-external-apps
            // unset in termux.properties. Reported rather than thrown: a phone
            // that cannot repair its own sshd should still say so.
            Log.w(TAG, "sshd repair failed: ${e.message}")
            false
        }

    /** Is a VPN transport up? Proxy for "tailscale is carrying traffic". */
    private fun vpnActive(ctx: Context): Boolean =
        try {
            val cm = ctx.getSystemService(ConnectivityManager::class.java)
            val caps = cm?.getNetworkCapabilities(cm.activeNetwork)
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true
        } catch (e: Exception) {
            false
        }
}
