{
  device = {
    name = "redmi-note-11";
    abi = "arm64-v8a";
    user = 0;
  };

  apps = {
    play = [
      "com.github.android"
      "com.google.android.apps.docs"
      "com.google.android.apps.maps"
      "com.google.android.apps.tachyon"
      "com.google.android.apps.walletnfcrel"
      "com.google.android.apps.youtube.music"
      "com.google.android.contactkeys"
      "com.google.android.gm"
      "com.google.android.safetycore"
      "com.google.android.verifier"
      "com.oculus.twilight"
      "com.twitter.android"
      "com.urbandroid.sleep"
      "com.urbandroid.sleep.addon.port"
      "com.urbandroid.sleep.captchapack"
      "com.urbandroid.sleep.full.key"
      "com.xiaomi.wearable"
      "io.elevenlabs.readerapp"
      "pl.gov.cez.mojeikp"
      "pl.mbank"
      "pl.nask.mobywatel"
    ];

    attended = [
      "co.bitfinder.awair"
      "com.anthropic.claude"
      "com.beemdevelopment.aegis"
      "com.facebook.orca"
      "com.github.catfriend1.syncthingfork"
      "com.google.android.apps.docs.editors.docs"
      "com.google.ar.lens"
      "com.machiav3lli.backup"
      "com.nextcloud.client"
      "com.openai.chatgpt"
      "com.sony.songpal.mdr"
      "com.spotify.music"
      "com.tailscale.ipn"
      "com.termux"
      "com.termux.api"
      "com.termux.boot"
      "com.termux.nix"
      "com.teslacoilsw.launcher"
      "com.teslacoilsw.launcher.prime"
      "com.xiaomi.smarthome"
      "dev.sinnix.phone"
      "io.raindrop.raindropio"
      "kups.rrhobtegaj.stw"
      "org.fdroid.fdroid"
      "pl.codever.ecoharmonogram"
      "pl.inpost.inmobile"
      "pl.orlenmobile25"
    ];

    # Surface package drift without deleting newly installed apps before review.
    cleanup = "report";
  };

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

    locales."pl.inpost.inmobile" = [ "pl-PL" ];

    permissions = {
      "com.github.catfriend1.syncthingfork".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.google.android.apps.maps".grant = [
        "android.permission.ACCESS_COARSE_LOCATION"
        "android.permission.ACCESS_FINE_LOCATION"
        "android.permission.POST_NOTIFICATIONS"
        "com.google.android.gms.permission.CAR_SPEED"
      ];
      "com.google.android.apps.walletnfcrel".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.machiav3lli.backup".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.sony.songpal.mdr".grant = [
        "android.permission.BLUETOOTH_CONNECT"
        "android.permission.BLUETOOTH_SCAN"
        "android.permission.POST_NOTIFICATIONS"
      ];
      "com.tailscale.ipn".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.termux".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.termux.api".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.termux.boot".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.termux.nix".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "com.urbandroid.sleep".grant = [
        "android.permission.ACTIVITY_RECOGNITION"
        "android.permission.POST_NOTIFICATIONS"
      ];
      "com.xiaomi.wearable".grant = [
        "android.permission.ACCESS_COARSE_LOCATION"
        "android.permission.ACCESS_FINE_LOCATION"
        "android.permission.ACTIVITY_RECOGNITION"
        "android.permission.ANSWER_PHONE_CALLS"
        "android.permission.BLUETOOTH_CONNECT"
        "android.permission.BLUETOOTH_SCAN"
        "android.permission.POST_NOTIFICATIONS"
        "android.permission.READ_CONTACTS"
        "android.permission.READ_PHONE_STATE"
        "android.permission.health.WRITE_ACTIVE_CALORIES_BURNED"
        "android.permission.health.WRITE_DISTANCE"
        "android.permission.health.WRITE_ELEVATION_GAINED"
        "android.permission.health.WRITE_EXERCISE"
        "android.permission.health.WRITE_EXERCISE_ROUTE"
        "android.permission.health.WRITE_HEART_RATE"
        "android.permission.health.WRITE_OXYGEN_SATURATION"
        "android.permission.health.WRITE_SLEEP"
        "android.permission.health.WRITE_SPEED"
        "android.permission.health.WRITE_STEPS"
      ];
      "dev.sinnix.phone".grant = [
        "android.permission.ACCESS_COARSE_LOCATION"
        "android.permission.BLUETOOTH_CONNECT"
        "android.permission.CAMERA"
        "android.permission.POST_NOTIFICATIONS"
        "android.permission.RECORD_AUDIO"
        "android.permission.health.READ_ACTIVE_CALORIES_BURNED"
        "android.permission.health.READ_BASAL_METABOLIC_RATE"
        "android.permission.health.READ_BLOOD_GLUCOSE"
        "android.permission.health.READ_BLOOD_PRESSURE"
        "android.permission.health.READ_BODY_FAT"
        "android.permission.health.READ_BODY_TEMPERATURE"
        "android.permission.health.READ_DISTANCE"
        "android.permission.health.READ_ELEVATION_GAINED"
        "android.permission.health.READ_EXERCISE"
        "android.permission.health.READ_EXERCISE_ROUTES"
        "android.permission.health.READ_FLOORS_CLIMBED"
        "android.permission.health.READ_HEALTH_DATA_HISTORY"
        "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND"
        "android.permission.health.READ_HEART_RATE"
        "android.permission.health.READ_HEART_RATE_VARIABILITY"
        "android.permission.health.READ_HEIGHT"
        "android.permission.health.READ_HYDRATION"
        "android.permission.health.READ_OXYGEN_SATURATION"
        "android.permission.health.READ_RESPIRATORY_RATE"
        "android.permission.health.READ_RESTING_HEART_RATE"
        "android.permission.health.READ_SKIN_TEMPERATURE"
        "android.permission.health.READ_SLEEP"
        "android.permission.health.READ_SPEED"
        "android.permission.health.READ_STEPS"
        "android.permission.health.READ_TOTAL_CALORIES_BURNED"
        "android.permission.health.READ_VO2_MAX"
        "android.permission.health.READ_WEIGHT"
        "com.termux.permission.RUN_COMMAND"
      ];
      "pl.codever.ecoharmonogram".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "pl.gov.cez.mojeikp".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "pl.inpost.inmobile".grant = [ "android.permission.POST_NOTIFICATIONS" ];
      "pl.mbank".grant = [
        "android.permission.ACCESS_COARSE_LOCATION"
        "android.permission.ACCESS_FINE_LOCATION"
        "android.permission.CALL_PHONE"
        "android.permission.CAMERA"
        "android.permission.GET_ACCOUNTS"
        "android.permission.POST_NOTIFICATIONS"
        "android.permission.READ_CONTACTS"
        "android.permission.READ_PHONE_STATE"
      ];
      "pl.nask.mobywatel".grant = [ "android.permission.POST_NOTIFICATIONS" ];
    };

    appOps = {
      "com.github.catfriend1.syncthingfork" = {
        RUN_ANY_IN_BACKGROUND = "allow";
        RUN_IN_BACKGROUND = "allow";
        START_FOREGROUND = "allow";
      };
      "com.machiav3lli.backup" = {
        GET_USAGE_STATS = "allow";
        START_FOREGROUND = "allow";
        USE_BIOMETRIC = "allow";
      };
      "com.tailscale.ipn" = {
        ACTIVATE_VPN = "allow";
        ESTABLISH_VPN_SERVICE = "allow";
        RUN_ANY_IN_BACKGROUND = "allow";
        RUN_IN_BACKGROUND = "allow";
        START_FOREGROUND = "allow";
      };
      "com.termux" = {
        RUN_ANY_IN_BACKGROUND = "allow";
        START_FOREGROUND = "allow";
      };
      "com.termux.boot".RUN_ANY_IN_BACKGROUND = "allow";
      "com.termux.nix" = {
        RUN_ANY_IN_BACKGROUND = "allow";
        START_FOREGROUND = "allow";
      };
      "com.teslacoilsw.launcher" = {
        BIND_ACCESSIBILITY_SERVICE = "allow";
        REQUEST_DELETE_PACKAGES = "allow";
      };
      "com.urbandroid.sleep" = {
        ACTIVITY_RECOGNITION = "allow";
        BIND_ACCESSIBILITY_SERVICE = "allow";
        RUN_ANY_IN_BACKGROUND = "allow";
      };
      "com.xiaomi.wearable" = {
        AUTO_REVOKE_PERMISSIONS_IF_UNUSED = "ignore";
        BLUETOOTH_CONNECT = "allow";
        BLUETOOTH_SCAN = "allow";
        READ_WRITE_HEALTH_DATA = "allow";
        RUN_ANY_IN_BACKGROUND = "allow";
        RUN_IN_BACKGROUND = "allow";
        START_FOREGROUND = "allow";
      };
      "dev.sinnix.phone" = {
        MANAGE_EXTERNAL_STORAGE = "allow";
        READ_WRITE_HEALTH_DATA = "allow";
        RECORD_AUDIO = "allow";
        START_FOREGROUND = "allow";
      };
      "pl.mbank" = {
        READ_PHONE_STATE = "allow";
        START_FOREGROUND = "allow";
        USE_BIOMETRIC = "allow";
      };
      "pl.nask.mobywatel".USE_BIOMETRIC = "allow";
    };

    batteryOptimization.exempt = [
      "com.github.catfriend1.syncthingfork"
      "com.machiav3lli.backup"
      "com.tailscale.ipn"
      "com.termux"
      "com.termux.boot"
      "com.termux.nix"
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
