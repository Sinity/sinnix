package dev.sinnix.phone;

import android.app.NotificationManager;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;

/**
 * What the platform is currently letting this app do.
 *
 * <p>The other screen that carries grades, for a reason this device
 * demonstrates repeatedly: MIUI revokes grants with no event and no error, and
 * the first evidence is a capture that stopped. So each row states what is
 * known, how it was found out, and what breaks if it is lost.
 *
 * <p>Where a probe is possible, the probe wins over the API. An API answering
 * "true" while the platform blocks the path is exactly this vendor's habit,
 * and a green row backed only by a getter is the kind of comfort that lets a
 * silent failure run for a day.
 */
public final class GrantsActivity extends Screen {

  private LinearLayout root;
  private LinearLayout list;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    root = mount();
    root.addView(backRow());
    root.addView(
        text(
            "Each row says how it was checked. Anything the app cannot verify stays"
                + " unverified rather than being called OK.",
            12,
            TEXT_FAINT));
    root.addView(spacer(dp(12)));
    list = column();
    root.addView(list);
  }

  @Override
  protected void onResume() {
    super.onResume();
    refresh();
  }

  private void refresh() {
    list.removeAllViews();

    ProbeResult storage = probeStorage();
    addRow(
        "all-files access",
        storage.grade,
        storage.evidence,
        "chunks stop reaching the shared handoff directory; the drain sees nothing new",
        () -> openSettings(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION, true));

    boolean exempt = isBatteryExempt();
    addRow(
        "battery exemption",
        Grade.of(true, exempt),
        exempt
            ? "PowerManager.isIgnoringBatteryOptimizations = true"
            : "PowerManager.isIgnoringBatteryOptimizations = false",
        "Doze throttles the rotation handler; chunk boundaries drift and stall",
        () -> openSettings(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS, false));

    boolean notifications = notificationsEnabled();
    addRow(
        "notifications",
        Grade.of(true, notifications),
        "NotificationManager.areNotificationsEnabled = " + notifications,
        "the foreground service notification cannot be shown, and the platform may refuse the service",
        () -> openSettings(Settings.ACTION_APP_NOTIFICATION_SETTINGS, false));

    // Structurally unverifiable: MIUI keeps autostart in a private database
    // with no API and no content provider. The honest render is a permanent
    // `unverified` plus the two things that do carry information -- when the
    // operator last attested it, and whether capture actually resumed after
    // the last boot.
    addRow(
        "MIUI autostart",
        Grade.UNVERIFIED,
        attestationLine(),
        "the boot broadcast is never delivered, so capture does not resume until the app is opened",
        this::attestAutostart);

    list.addView(spacer(dp(4)));
    list.addView(mono(bootInferenceLine(), 11, TEXT_FAINT));
  }

  private static final class ProbeResult {
    final Grade grade;
    final String evidence;

    ProbeResult(Grade grade, String evidence) {
      this.grade = grade;
      this.evidence = evidence;
    }
  }

  /**
   * Grade all-files access by writing, not by asking.
   *
   * <p>{@code Environment.isExternalStorageManager()} has answered true on
   * this platform while the path stayed unwritable. Creating and deleting a
   * real file in the handoff directory is the only answer that means what the
   * row claims.
   */
  private ProbeResult probeStorage() {
    boolean api = Storage.haveAllFilesAccess();
    File dir = new File(Storage.SHARED_DIR);
    File probe = new File(dir, ".sinnix-write-probe");
    boolean wrote = false;
    String detail;
    try (FileOutputStream out = new FileOutputStream(probe)) {
      out.write('1');
      wrote = true;
      detail = "wrote and removed " + probe.getName() + " in " + Storage.SHARED_DIR;
    } catch (IOException | SecurityException e) {
      detail = "write probe failed in " + Storage.SHARED_DIR + ": " + e.getClass().getSimpleName();
    }
    if (probe.exists() && !probe.delete()) {
      detail = detail + " (probe file left behind)";
    }
    if (api != wrote) {
      // Worth printing: this is the disagreement the probe exists to catch.
      detail = detail + " · API said " + api;
    }
    return new ProbeResult(Grade.of(true, wrote), detail);
  }

  private boolean isBatteryExempt() {
    PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
    return pm != null && pm.isIgnoringBatteryOptimizations(getPackageName());
  }

  private boolean notificationsEnabled() {
    NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
    return nm != null && nm.areNotificationsEnabled();
  }

  private String attestationLine() {
    JSONObject latest = null;
    for (JSONObject e : Events.recent(this, 60)) {
      if ("attestation".equals(e.optString("kind")) && "miui_autostart".equals(e.optString("grant"))) {
        latest = e;
      }
    }
    if (latest == null) {
      return "never attested — no API exists to read this";
    }
    return "attested " + latest.optString("ts") + " — no API exists to re-check it";
  }

  /**
   * The only real test of autostart is a reboot, so treat each one as a trial.
   *
   * <p>Boot with no capture inside a couple of minutes is evidence autostart
   * is off, and it is recorded as evidence rather than displayed as a guess.
   */
  private String bootInferenceLine() {
    long lastBoot = 0;
    long firstChunkAfterBoot = 0;
    for (JSONObject e : Events.recent(this, 7)) {
      String kind = e.optString("kind");
      long ts = Coverage.parseStamp(e.optString("ts"));
      if ("boot".equals(kind)) {
        lastBoot = ts;
        firstChunkAfterBoot = 0;
      } else if ("chunk_closed".equals(kind) && lastBoot != 0 && firstChunkAfterBoot == 0) {
        firstChunkAfterBoot = ts;
      }
    }
    if (lastBoot == 0) {
      return "boot inference: no reboot observed since the app was installed";
    }
    if (firstChunkAfterBoot == 0) {
      return "boot inference: last reboot produced no chunk — capture did not resume on its own";
    }
    long gapMin = Math.max(0, (firstChunkAfterBoot - lastBoot) / 60000L);
    return "boot inference: capture resumed " + gapMin + " min after the last reboot";
  }

  private void attestAutostart() {
    Events.record(
        this,
        "attestation",
        "grant", "miui_autostart",
        "by", "operator",
        "note", "enabled in MIUI background autostart");
    try {
      startActivity(
          new Intent()
              .setClassName(
                  "com.miui.securitycenter",
                  "com.miui.permcenter.autostart.AutoStartManagementActivity"));
    } catch (ActivityNotFoundException | SecurityException e) {
      // Not a MIUI build, or the activity moved. The attestation still stands.
    }
    refresh();
  }

  private void addRow(String name, Grade grade, String evidence, String blastRadius, Runnable action) {
    LinearLayout c = column();
    c.setBackground(gradeBackground(grade));
    c.setPadding(dp(12), dp(10), dp(12), dp(10));

    LinearLayout head = row();
    TextView label = text(name, 14, TEXT_BRIGHT);
    label.setLayoutParams(
        new LinearLayout.LayoutParams(0, android.view.ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
    head.addView(label);
    head.addView(mono(grade.glyph + " " + grade.word, 11, grade.color));
    c.addView(head);

    c.addView(mono(evidence, 11, TEXT_DIM));
    c.addView(spacer(dp(4)));
    // What breaks if this is lost, in the same row as the state -- so the
    // question "does this matter" never needs a trip to the documentation.
    c.addView(text("if lost: " + blastRadius, 11, TEXT_FAINT));

    if (action != null) {
      c.setOnClickListener(v -> action.run());
    }
    list.addView(c);
    list.addView(spacer(dp(8)));
  }

  private void openSettings(String action, boolean packageUri) {
    try {
      Intent i = new Intent(action);
      if (packageUri) {
        i.setData(Uri.parse("package:" + getPackageName()));
      } else if (Settings.ACTION_APP_NOTIFICATION_SETTINGS.equals(action)) {
        i.putExtra(Settings.EXTRA_APP_PACKAGE, getPackageName());
      }
      startActivity(i);
    } catch (ActivityNotFoundException e) {
      startActivity(
          new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
              .setData(Uri.parse("package:" + getPackageName())));
    }
  }
}
