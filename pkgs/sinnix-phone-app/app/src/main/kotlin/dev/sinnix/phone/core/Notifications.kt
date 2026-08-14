package dev.sinnix.phone.core

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import dev.sinnix.phone.R

/**
 * Four channels, because they answer to four different rules — and separate
 * channels rather than one so that silencing the furniture does not also
 * silence the alarm, which is exactly the outcome a single channel forces and
 * the reason a broken recorder can go unnoticed for a day.
 *
 * The interruption taxonomy, stated once: interrupt for capture broken, for a
 * grant revoked, for a commitment coming due, and for an agent that asked a
 * question. Do not interrupt for capture merely behind on upload, for an
 * instrument being due, or for a job that finished successfully. Those wait
 * for the next glance.
 */
object Notifications {

    /** The forced foreground-service notification. Furniture, and silent. */
    const val CHANNEL_STATUS = "sinnix-ambient"

    /** Capture has stopped producing. Interrupts. */
    const val CHANNEL_CAPTURE_BROKEN = "sinnix-capture-alert"

    /** Something is waiting on the operator: an agent question, a due commitment. */
    const val CHANNEL_NEEDS_YOU = "sinnix-needs-you"

    /** Prime answered: a transcript, a score, a send confirmation. Silent. */
    const val CHANNEL_RECEIPTS = "sinnix-receipts"

    /** EMA prompts, answerable from the shade without unlocking. */
    const val CHANNEL_EMA = "sinnix-ema"

    const val ID_ONGOING = 4711
    const val ID_ALERT = 4712
    const val ID_EMA = 4713
    const val ID_NEEDS_YOU_BASE = 4800
    const val ID_RECEIPT_BASE = 4900

    fun ensureChannels(ctx: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return

        channel(nm, CHANNEL_STATUS, "Ambient capture", NotificationManager.IMPORTANCE_LOW) {
            it.setShowBadge(false)
            it.setSound(null, null)
        }
        channel(nm, CHANNEL_CAPTURE_BROKEN, "Capture problems", NotificationManager.IMPORTANCE_DEFAULT) {
            it.setShowBadge(true)
        }
        channel(nm, CHANNEL_NEEDS_YOU, "Needs you", NotificationManager.IMPORTANCE_DEFAULT) {
            it.setShowBadge(true)
        }
        channel(nm, CHANNEL_RECEIPTS, "Receipts", NotificationManager.IMPORTANCE_LOW) {
            it.setShowBadge(false)
            it.setSound(null, null)
        }
        channel(nm, CHANNEL_EMA, "Check-ins", NotificationManager.IMPORTANCE_DEFAULT) {
            it.setShowBadge(false)
        }
    }

    private inline fun channel(
        nm: NotificationManager,
        id: String,
        name: String,
        importance: Int,
        configure: (NotificationChannel) -> Unit,
    ) {
        if (nm.getNotificationChannel(id) != null) return
        val c = NotificationChannel(id, name, importance)
        configure(c)
        nm.createNotificationChannel(c)
    }

    /** An Intent that opens the app, used by every channel. */
    fun openApp(ctx: Context, route: String? = null): PendingIntent {
        val intent =
            Intent(ctx, dev.sinnix.phone.ui.MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                if (route != null) putExtra("route", route)
            }
        return PendingIntent.getActivity(
            ctx,
            route?.hashCode() ?: 0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
    }

    /**
     * Say that capture has stopped producing.
     *
     * Interrupts deliberately: this is the class of failure that otherwise
     * announces itself days later as a hole in the archive. Withdrawn again
     * only when a chunk closes with sound in it — "the service is running
     * again" is exactly the claim that was wrong when this failure mode was
     * discovered.
     */
    fun alertCaptureBroken(ctx: Context, reason: String) {
        ensureChannels(ctx)
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        val n =
            Notification.Builder(ctx, CHANNEL_CAPTURE_BROKEN)
                .setContentTitle("Capture stopped producing")
                .setContentText(reason)
                .setStyle(Notification.BigTextStyle().bigText(reason))
                .setSmallIcon(android.R.drawable.stat_notify_error)
                .setContentIntent(openApp(ctx, "capture"))
                .setAutoCancel(true)
                .setOnlyAlertOnce(true)
                .build()
        nm.notify(ID_ALERT, n)
    }

    fun clearAlert(ctx: Context) {
        ctx.getSystemService(NotificationManager::class.java)?.cancel(ID_ALERT)
    }

    /** A receipt from prime: silent, informative, dismissible. */
    fun postReceipt(ctx: Context, id: Int, title: String, body: String, route: String?) {
        ensureChannels(ctx)
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        val n =
            Notification.Builder(ctx, CHANNEL_RECEIPTS)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(Notification.BigTextStyle().bigText(body))
                .setSmallIcon(R.drawable.ic_mark)
                .setContentIntent(openApp(ctx, route))
                .setAutoCancel(true)
                .build()
        nm.notify(ID_RECEIPT_BASE + (id and 0x3F), n)
    }

    /** Something is waiting on the operator. Interrupts. */
    fun postNeedsYou(
        ctx: Context,
        id: Int,
        title: String,
        body: String,
        route: String?,
        actions: List<Notification.Action> = emptyList(),
    ) {
        ensureChannels(ctx)
        val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
        val b =
            Notification.Builder(ctx, CHANNEL_NEEDS_YOU)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(Notification.BigTextStyle().bigText(body))
                .setSmallIcon(android.R.drawable.stat_notify_more)
                .setContentIntent(openApp(ctx, route))
                .setAutoCancel(true)
        actions.forEach { b.addAction(it) }
        nm.notify(ID_NEEDS_YOU_BASE + (id and 0x3F), b.build())
    }
}
