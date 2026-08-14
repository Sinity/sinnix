package dev.sinnix.phone.sync

import android.app.NotificationManager
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import dev.sinnix.phone.capture.AmbientSensors
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Notifications

/**
 * Verbs that never open the app.
 *
 * The EMA prompt is the reason this exists. A check-in that requires unlocking
 * the phone, finding the app and navigating to a screen is a check-in that
 * gets answered when it is convenient, which is exactly the sampling bias
 * ecological momentary assessment is a method to avoid. Answered from the
 * shade with [RemoteInput], it costs one tap and one word.
 */
class NotificationActionReceiver : BroadcastReceiver() {

    override fun onReceive(ctx: Context, intent: Intent) {
        when (intent.action) {
            ACTION_EMA_REPLY -> {
                val reply =
                    RemoteInput.getResultsFromIntent(intent)?.getCharSequence(KEY_REPLY)?.toString()
                val scale = intent.getIntExtra(EXTRA_SCALE, -1)
                val sensors = AmbientSensors.latest
                Events.record(
                    ctx,
                    "ema_answer",
                    "prompt", intent.getStringExtra(EXTRA_PROMPT),
                    "answer", reply,
                    "scale", if (scale >= 0) scale else null,
                    // Auto-tagged context is what turns self-report from noise
                    // into something joinable: the same answer at 200 lux while
                    // still and at 3 lux while moving are different data points.
                    "lux_mean", sensors?.luxMean,
                    "motion_rms", sensors?.motionRms,
                )
                ctx.getSystemService(NotificationManager::class.java)
                    ?.cancel(Notifications.ID_EMA)
            }
            ACTION_MARK -> {
                val mark = intent.getStringExtra(EXTRA_MARK) ?: return
                dev.sinnix.phone.ui.mark.MarkActivity.record(ctx, mark, null)
            }
        }
    }

    companion object {
        const val ACTION_EMA_REPLY = "dev.sinnix.phone.EMA_REPLY"
        const val ACTION_MARK = "dev.sinnix.phone.MARK"
        const val KEY_REPLY = "ema_reply"
        const val EXTRA_PROMPT = "prompt"
        const val EXTRA_SCALE = "scale"
        const val EXTRA_MARK = "mark"

        /** A shade-answerable prompt: free text plus a coarse scale, both optional. */
        fun postEma(ctx: Context, prompt: String) {
            Notifications.ensureChannels(ctx)
            val nm = ctx.getSystemService(NotificationManager::class.java) ?: return
            val remoteInput =
                RemoteInput.Builder(KEY_REPLY).setLabel("a word or two").build()
            val replyIntent =
                PendingIntent.getBroadcast(
                    ctx,
                    1,
                    Intent(ctx, NotificationActionReceiver::class.java)
                        .setAction(ACTION_EMA_REPLY)
                        .putExtra(EXTRA_PROMPT, prompt),
                    PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
                )
            val reply =
                android.app.Notification.Action.Builder(
                        android.graphics.drawable.Icon.createWithResource(
                            ctx,
                            android.R.drawable.ic_menu_edit,
                        ),
                        "answer",
                        replyIntent,
                    )
                    .addRemoteInput(remoteInput)
                    .build()

            val n =
                android.app.Notification.Builder(ctx, Notifications.CHANNEL_EMA)
                    .setContentTitle(prompt)
                    .setSmallIcon(android.R.drawable.ic_menu_edit)
                    .addAction(reply)
                    .setAutoCancel(true)
                    .build()
            nm.notify(Notifications.ID_EMA, n)
        }
    }
}
