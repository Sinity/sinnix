{
  device = {
    name = "quest-3";
    abi = "arm64-v8a";
    user = 0;
  };

  # System software remains Quest-owned.  This profile only preserves the
  # directly observed, USB-development settings; package drift is reported,
  # never removed.
  apps.cleanup = "report";

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
