{
  device = {
    name = "quest-3";
    abi = "arm64-v8a";
    user = 0;
  };

  # System software remains Quest-owned. This is a report baseline for the
  # retained utility set, not an install manifest or a deletion policy.
  apps = {
    # Store and side-loaded utilities retained after the 2026-09 cleanup.
    # `cleanup = "report"` only surfaces drift in `android-rebuild plan`.
    attended = [
      "alvr.client.stable"
      "com.aurora.store"
      "com.apk.editor"
      "com.deovr.gearvr"
      "com.google.android.apps.youtube.vr.oculus"
      "com.meta.curio.ruler"
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
      "org.meumeu.wivrn.github"
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
}
