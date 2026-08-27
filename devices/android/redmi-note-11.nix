{
  device = {
    name = "redmi-note-11";
    abi = "arm64-v8a";
    user = 0;
  };

  apps.cleanup = "none";

  android = {
    darkMode = true;

    defaultApps = {
      browser = "com.android.chrome";
      dialer = "com.google.android.dialer";
      home = "com.teslacoilsw.launcher";
      sms = "com.google.android.apps.messaging";
    };

    inputMethod = {
      enabled = [
        "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"
        "com.google.android.tts/com.google.android.apps.speech.tts.googletts.settings.asr.voiceime.VoiceInputMethodService"
      ];
      default = "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME";
    };

    dataSaver.enabled = false;

    appOps."dev.sinnix.phone".RECORD_AUDIO = "allow";

    batteryOptimization.exempt = [
      "com.github.catfriend1.syncthingfork"
      "com.machiav3lli.backup"
      "com.tailscale.ipn"
      "com.termux"
      "com.termux.boot"
      "com.urbandroid.sleep"
      "com.xiaomi.wearable"
      "dev.sinnix.phone"
    ];

    packages.disabled = [
      "com.android.axion.quicklook"
      "com.google.android.glasses.core"
      "com.google.android.gms.supervision"
      "com.google.android.googlequicksearchbox"
      "com.libremobileos.freeform"
      "com.libremobileos.sidebar"
      "io.chaldeaprjkt.gamespace"
      "org.protonaosp.columbus"
    ];

    settings = {
      global = {
        auto_time = 1;
        auto_time_zone = 1;
        stay_on_while_plugged_in = 0;
        transition_animation_scale = "0.6";
        wifi_wakeup_enabled = 0;
        window_animation_scale = "0.6";
      };
      secure = {
        double_tap_to_wake = 1;
        lock_screen_allow_private_notifications = 1;
        lock_screen_show_notifications = 1;
        long_press_timeout = 500;
        navigation_mode = 2;
        show_ime_with_hard_keyboard = 1;
        wake_gesture_enabled = 1;
      };
      system = {
        accelerometer_rotation = 1;
        haptic_feedback_enabled = 1;
        screen_off_timeout = 600000;
        show_password = 0;
        sound_effects_enabled = 0;
        vibrate_when_ringing = 0;
      };
    };
  };
}
