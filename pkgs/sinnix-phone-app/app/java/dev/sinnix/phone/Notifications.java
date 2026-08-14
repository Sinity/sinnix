package dev.sinnix.phone;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * Two notification classes, because they answer to different rules.
 *
 * <p>The ongoing one is furniture: it exists because the platform requires a
 * foreground service to show something, and it should never make a sound or
 * carry a badge. The alert one interrupts, and is reserved for capture having
 * actually broken.
 *
 * <p>Separate channels rather than one, so the operator can silence the
 * furniture without also silencing the alarm -- which is the outcome a single
 * channel forces, and the reason a broken recorder can go unnoticed for a day.
 */
final class Notifications {

  static final String CHANNEL_CAPTURE = "sinnix-ambient";
  static final String CHANNEL_ALERT = "sinnix-capture-alert";

  static final int ID_ONGOING = 4711;
  static final int ID_ALERT = 4712;

  private Notifications() {}

  static void ensureChannels(Context ctx) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
      return;
    }
    NotificationManager nm =
        (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
    if (nm == null) {
      return;
    }
    if (nm.getNotificationChannel(CHANNEL_CAPTURE) == null) {
      NotificationChannel c =
          new NotificationChannel(CHANNEL_CAPTURE, "Ambient capture", NotificationManager.IMPORTANCE_LOW);
      c.setShowBadge(false);
      c.setSound(null, null);
      nm.createNotificationChannel(c);
    }
    if (nm.getNotificationChannel(CHANNEL_ALERT) == null) {
      NotificationChannel c =
          new NotificationChannel(
              CHANNEL_ALERT, "Capture problems", NotificationManager.IMPORTANCE_DEFAULT);
      c.setShowBadge(true);
      nm.createNotificationChannel(c);
    }
  }

  /** An Intent that opens Home, used by both classes. */
  static PendingIntent openApp(Context ctx) {
    return PendingIntent.getActivity(
        ctx,
        0,
        new Intent(ctx, HomeActivity.class),
        PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
  }

  /**
   * Say that capture has stopped producing, once per distinct reason.
   *
   * <p>Interrupts deliberately: this is the class of failure that otherwise
   * announces itself days later as a hole in the archive. It is not posted for
   * ordinary rotation or for a recorder cycling and recovering -- only when
   * the service has given up on the current attempt.
   */
  static void alertCaptureBroken(Context ctx, String reason) {
    ensureChannels(ctx);
    NotificationManager nm =
        (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
    if (nm == null) {
      return;
    }
    Notification n =
        new Notification.Builder(ctx, CHANNEL_ALERT)
            .setContentTitle("Capture stopped producing")
            .setContentText(reason)
            .setStyle(new Notification.BigTextStyle().bigText(reason))
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentIntent(openApp(ctx))
            .setAutoCancel(true)
            .setOnlyAlertOnce(true)
            .build();
    nm.notify(ID_ALERT, n);
  }

  /** Withdraw the alert once chunks are landing again. */
  static void clearAlert(Context ctx) {
    NotificationManager nm =
        (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
    if (nm != null) {
      nm.cancel(ID_ALERT);
    }
  }
}
