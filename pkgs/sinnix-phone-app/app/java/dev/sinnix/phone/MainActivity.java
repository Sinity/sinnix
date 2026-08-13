package dev.sinnix.phone;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Operator-facing surface: what capture is doing, and the three grants the
 * platform will only hand over through a human tap.
 *
 * <p>The UI is built in code rather than from layout resources so the APK
 * needs no resource compilation beyond the manifest -- the build is plain
 * aapt2/javac/d8 with no Gradle, and keeping the resource surface empty is
 * what makes that tractable.
 */
public class MainActivity extends Activity {

  private TextView statusView;
  private Button toggleButton;
  private final Handler ui = new Handler(Looper.getMainLooper());

  private final Runnable refresh =
      new Runnable() {
        @Override
        public void run() {
          render();
          ui.postDelayed(this, 2000);
        }
      };

  @Override
  protected void onCreate(Bundle savedInstanceState) {
    super.onCreate(savedInstanceState);

    LinearLayout root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    int pad = dp(16);
    root.setPadding(pad, pad, pad, pad);

    TextView title = new TextView(this);
    title.setText("Sinnix Capture");
    title.setTypeface(Typeface.DEFAULT_BOLD);
    title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 22);
    root.addView(title);

    statusView = new TextView(this);
    statusView.setTypeface(Typeface.MONOSPACE);
    statusView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
    statusView.setPadding(0, dp(12), 0, dp(12));
    root.addView(statusView);

    toggleButton = new Button(this);
    toggleButton.setOnClickListener(v -> onToggle());
    root.addView(toggleButton);

    root.addView(button("Grant all-files access", v -> openAllFilesAccess()));
    root.addView(button("Ignore battery optimisation", v -> openBatteryExemption()));
    root.addView(button("App info / autostart", v -> openAppSettings()));

    ScrollView scroll = new ScrollView(this);
    scroll.addView(root);
    setContentView(scroll);

    requestRuntimePermissions();

    if (Prefs.enabled(this) && !AmbientService.running) {
      AmbientService.start(this);
    }
  }

  @Override
  protected void onResume() {
    super.onResume();
    ui.post(refresh);
  }

  @Override
  protected void onPause() {
    ui.removeCallbacks(refresh);
    super.onPause();
  }

  private void onToggle() {
    if (AmbientService.running) {
      Prefs.setEnabled(this, false);
      AmbientService.stop(this);
    } else {
      Prefs.setEnabled(this, true);
      AmbientService.start(this);
    }
    ui.postDelayed(this::render, 400);
  }

  private void render() {
    StringBuilder b = new StringBuilder();
    b.append("version   : ").append(BuildId.VERSION).append('\n');
    b.append("service   : ").append(AmbientService.running ? "RUNNING" : "stopped").append('\n');
    b.append("enabled   : ").append(Prefs.enabled(this)).append('\n');
    b.append("mic perm  : ").append(granted(Manifest.permission.RECORD_AUDIO)).append('\n');
    b.append("all files : ").append(Storage.haveAllFilesAccess()).append('\n');

    File dir = Storage.chunkDir(this);
    b.append("chunk dir : ").append(dir == null ? "NONE" : dir.getAbsolutePath()).append('\n');
    if (dir != null && !Storage.SHARED_DIR.equals(dir.getAbsolutePath())) {
      b.append("            (fallback — the desktop drain cannot read this)\n");
    }
    if (dir != null) {
      File[] chunks = dir.listFiles((d, name) -> name.endsWith(".m4a"));
      b.append("chunks    : ").append(chunks == null ? 0 : chunks.length).append(" closed on disk\n");
      File status = new File(dir, "status.json");
      if (status.isFile()) {
        b.append("status.json ").append(status.length()).append(" bytes, ")
            .append((System.currentTimeMillis() - status.lastModified()) / 1000)
            .append("s old\n");
      }
    }

    statusView.setText(b.toString());
    statusView.setTextColor(AmbientService.running ? Color.parseColor("#1b7f3b") : Color.parseColor("#a02020"));
    toggleButton.setText(AmbientService.running ? "Stop capture" : "Start capture");
  }

  private String granted(String permission) {
    return checkSelfPermission(permission) == PackageManager.PERMISSION_GRANTED ? "granted" : "DENIED";
  }

  private void requestRuntimePermissions() {
    List<String> wanted = new ArrayList<>();
    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
      wanted.add(Manifest.permission.RECORD_AUDIO);
    }
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
        && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
      wanted.add(Manifest.permission.POST_NOTIFICATIONS);
    }
    if (!wanted.isEmpty()) {
      requestPermissions(wanted.toArray(new String[0]), 1);
    }
  }

  @Override
  public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
    if (Prefs.enabled(this)) {
      AmbientService.start(this);
    }
    render();
  }

  private void openAllFilesAccess() {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
      startActivitySafely(
          new Intent(
              Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
              Uri.parse("package:" + getPackageName())));
    }
  }

  private void openBatteryExemption() {
    startActivitySafely(
        new Intent(
            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
            Uri.parse("package:" + getPackageName())));
  }

  private void openAppSettings() {
    startActivitySafely(
        new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName())));
  }

  private void startActivitySafely(Intent intent) {
    try {
      startActivity(intent);
    } catch (Exception e) {
      statusView.setText("could not open settings screen: " + e);
    }
  }

  private Button button(String label, View.OnClickListener onClick) {
    Button b = new Button(this);
    b.setText(label);
    b.setOnClickListener(onClick);
    return b;
  }

  private int dp(int value) {
    return Math.round(value * getResources().getDisplayMetrics().density);
  }
}
