# System audio configuration
#
# Configures PipeWire audio subsystem with:
# - PipeWire/WirePlumber for audio routing
# - Bluetooth audio (A2DP, SBC-XQ, mSBC)
# - Real-time priority for low latency
# - USB DAC quantum settings
{
  lib,
  pkgs,
  config,
  ...
}:
let
  cfg = config.sinnix.features.desktop.audio;
in
{
  options.sinnix.features.desktop.audio = {
    enable = lib.mkEnableOption "High-performance audio stack (PipeWire)";
  };

  config = lib.mkIf cfg.enable {
    services.pipewire = {
      enable = true;
      audio.enable = true;
      alsa.enable = true;
      pulse.enable = true;
      wireplumber = {
        enable = true;
        extraConfig = {
          "09-bluetooth-features"."wireplumber.profiles".main = {
            "monitor.bluez.seat-monitoring" = "disabled";
            "monitor.bluez-midi.seat-monitoring" = "disabled";
          };
          "10-bluez" = {
            "monitor.bluez.seat-monitoring" = false;
            "monitor.bluez.properties" = {
              "bluez5.enable-sbc-xq" = true;
              "bluez5.enable-msbc" = true;
              "bluez5.enable-hw-volume" = true;
              # Only expose high-fidelity roles; drop HSP/HFP so headsets never fall back to handsfree
              "bluez5.roles" = [
                "a2dp_sink"
                "a2dp_source"
                "bap_sink"
                "bap_source"
              ];
            };
          };
          "11-bluetooth-policy"."wireplumber.settings" = {
            "bluetooth.autoswitch-to-headset-profile" = false;
            "bluetooth.use-persistent-storage" = true;
          };
        };
      };
    };

    systemd.user.services.pipewire.serviceConfig = {
      LimitRTPRIO = 95;
      LimitMEMLOCK = "infinity";
      Nice = -11;
      # Auto-recover from silent audio daemon crashes
      Restart = "on-failure";
      RestartSec = 2;
    };

    security.pam.loginLimits = [
      {
        domain = "@audio";
        type = "soft";
        item = "rtprio";
        value = "95";
      }
      {
        domain = "@audio";
        type = "hard";
        item = "rtprio";
        value = "95";
      }
      {
        domain = "@audio";
        type = "soft";
        item = "memlock";
        value = "unlimited";
      }
      {
        domain = "@audio";
        type = "hard";
        item = "memlock";
        value = "unlimited";
      }
    ];

    environment.systemPackages = with pkgs; [
      alsa-utils
      pamixer
      playerctl
    ];

    users.users."${config.sinnix.user.name}".extraGroups = lib.mkAfter [
      "audio"
      "bluetooth"
    ];

    environment.etc."wireplumber/60-force-quantum.lua".text = ''
      rule = {
        matches = {
          { { "node.name", "matches", "alsa_output.usb-2cc2_*" }, },
        },
        apply_properties = { ["clock.force-quantum"] = 384 },
      }
      table.insert(alsa_monitor.rules, rule)
    '';
  };
}
