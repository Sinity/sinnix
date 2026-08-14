package dev.sinnix.phone.ingress

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import dev.sinnix.phone.core.Events

/**
 * The inbound comms timeline.
 *
 * Notifications are the one record of what actually reached the operator's
 * attention through a phone, and nothing else in the estate produces it —
 * ActivityWatch mobile captures which app was open, not what it said or when
 * it interrupted.
 *
 * MIUI may revoke this binding silently, which is the same failure shape as
 * every other grant here. So the connect and disconnect callbacks are written
 * as events: a gap in the lane then explains itself in the log instead of
 * being guessed at months later.
 *
 * The app's own notifications are skipped. Logging the capture heartbeat into
 * the capture log would be a feedback loop with nothing at the end of it.
 */
class PhoneNotificationListener : NotificationListenerService() {

    override fun onListenerConnected() {
        super.onListenerConnected()
        Events.record(this, "grant_transition", "grant", "notification_listener", "granted", true)
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        Events.record(this, "grant_transition", "grant", "notification_listener", "granted", false)
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        record(sbn, posted = true)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        record(sbn, posted = false)
    }

    private fun record(sbn: StatusBarNotification?, posted: Boolean) {
        val n = sbn ?: return
        if (n.packageName == packageName) return
        val extras = n.notification?.extras
        Events.record(
            this,
            if (posted) "notification_posted" else "notification_removed",
            "app", n.packageName,
            "title", extras?.getCharSequence("android.title")?.toString(),
            "text", extras?.getCharSequence("android.text")?.toString(),
            "posted_at", n.postTime,
            "ongoing", n.isOngoing,
            "clearable", n.isClearable,
            "key", n.key,
        )
    }
}
