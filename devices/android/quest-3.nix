{
  device = {
    name = "quest-3";
    abi = "arm64-v8a";
    user = 0;
  };

  # System software remains Quest-owned. This is a report baseline for the
  # retained utility set, not an install manifest or a deletion policy.
  apps = {
    release = {
      # Official upstream releases. The lock records the exact APK hash and
      # signing certificate, so a headset wipe can restore these clients.
      "alvr.client.stable".github = "alvr-org/ALVR";
      # Wolvic publishes several headset-specific APKs in each GitHub release.
      # Pin the Quest artifact directly so a different headset build is never
      # selected solely because it shares the same Android package id.
      "com.igalia.wolvic".url = "https://github.com/Igalia/wolvic/releases/download/v1.9/Wolvic-oculusvr-arm64-gecko-generic-release.apk";
      "org.meumeu.wivrn.github".github = "WiVRn/WiVRn";
    };

    # Store and side-loaded utilities retained after the 2026-09 cleanup.
    # `cleanup = "report"` only surfaces drift in `android-rebuild plan`.
    attended = [
      "com.aurora.store"
      "com.apk.editor"
      "com.deovr.gearvr"
      "com.google.android.apps.youtube.vr.oculus"
      "com.meta.handseducationmodule"
      "com.meta.shell.env.footprint.haven2025"
      "com.meta.shell.env.vista.calming"
      "com.oculus.accountscenter"
      "com.oculus.fitnesstracker"
      "com.oculus.paracosmaavalanche"
      "com.oculus.vrprivacycheckup"
      "com.qcxr.qcxr"
      "com.rarlab.rar"
      "com.streamlabs"
      "com.threethan.launcher"
      "com.threethan.launcher.metastore"
      "com.valvesoftware.steamlinkvr"
      "com.zerotier.one"
      "com.ZeroTransform.VStreamer_Live"
      "github.paroj.dsub2000"
      "org.fdroid.fdroid"
      "pupper.dev.barkvr"
      "quest.side.vr"
    ];
    cleanup = "report";
  };

  android.settings = {
    global = {
      # Keep an attached development headset awake while USB-powered.
      stay_on_while_plugged_in = 2;
      animator_duration_scale = "0.5";
      transition_animation_scale = "0.5";
      window_animation_scale = "0.5";
    };
    system.screen_off_timeout = 86400000;
  };

  android.permissions = {
    "alvr.client.stable".grant = [
      "android.permission.POST_NOTIFICATIONS"
      "android.permission.RECORD_AUDIO"
    ];
    "com.igalia.wolvic".grant = [
      "android.permission.POST_NOTIFICATIONS"
      "android.permission.RECORD_AUDIO"
    ];
    "org.meumeu.wivrn.github".grant = [
      "android.permission.POST_NOTIFICATIONS"
      "android.permission.RECORD_AUDIO"
    ];
  };
}
