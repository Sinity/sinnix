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
      # Pair with Sinnix's receive-only media endpoint after selecting the
      # Videoshots folder through Android's folder picker.  Do not pre-grant
      # broad media access: the headset UI scopes the sync root.
      "com.github.catfriend1.syncthingfork".url = "https://github.com/researchxxl/syncthing-android/releases/download/v2.1.5.0/com.github.catfriend1.syncthingfork_release_v2.1.5.0_arm64-v8a.apk";
      # A local shell makes the headset independently useful for diagnostics,
      # SSH and small automation.  Keep it on Termux's GitHub signing track so
      # any future addons can use the same source.
      "com.termux".url = "https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_arm64-v8a.apk";
      # Wolvic publishes several headset-specific APKs in each GitHub release.
      # Pin the Quest artifact directly so a different headset build is never
      # selected solely because it shares the same Android package id.
      "com.igalia.wolvic".url = "https://github.com/Igalia/wolvic/releases/download/v1.9/Wolvic-oculusvr-arm64-gecko-generic-release.apk";
      "org.meumeu.wivrn.github".github = "WiVRn/WiVRn";
      # A conventional Android client is a useful fallback for remote desktop,
      # video and troubleshooting when an XR streaming runtime is not wanted.
      "com.limelight".url = "https://github.com/moonlight-stream/moonlight-android/releases/download/v12.1/app-nonRoot-release.apk";
      # The official universal APK brings the headset onto Sinnix's existing
      # tailnet. It is pinned here because the vendor notes that sideloaded
      # APKs do not update themselves.
      "com.tailscale.ipn".url = "https://pkgs.tailscale.com/stable/tailscale-android-universal-1.102.4.apk";
      # Native, offline-capable creative tool. Use the formal Quest release,
      # never a GitHub prerelease whose sketches may not open in the stable app.
      "com.Icosa.OpenBrush".url = "https://github.com/icosa-foundation/open-brush/releases/download/2.32.0/OpenBrush_Quest_2.32.0.apk";
    };

    fdroid.packages = [
      # Local file transfer, clipboard, and remote-input companion for the
      # KDE Connect endpoint declared in desktop.xr.
      "org.kde.kdeconnect_tp"
      # Plain-text notes and a document reader are useful as native Quest 2D
      # windows and keep their files in explicit, syncable directories.
      "net.gsantner.markor"
      "org.koreader.launcher.fdroid"
    ];

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
    "com.termux".grant = [
      "android.permission.POST_NOTIFICATIONS"
    ];
    "com.github.catfriend1.syncthingfork".grant = [
      "android.permission.POST_NOTIFICATIONS"
    ];
    "com.tailscale.ipn".grant = [ "android.permission.POST_NOTIFICATIONS" ];
    "org.kde.kdeconnect_tp".grant = [
      "android.permission.POST_NOTIFICATIONS"
      # Android gates LAN discovery behind foreground location for this
      # client. It is used only while KDE Connect searches for nearby peers.
      "android.permission.ACCESS_FINE_LOCATION"
      "android.permission.ACCESS_COARSE_LOCATION"
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
