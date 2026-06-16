# System audio configuration
#
# Configures PipeWire audio subsystem with:
# - PipeWire/WirePlumber for audio routing
# - Bluetooth audio (A2DP, SBC-XQ, mSBC)
# - Real-time priority for low latency
# - USB DAC quantum settings
{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "audio"
  ];
  description = "High-performance audio stack (PipeWire)";
  configFn =
    {
      config,
      lib,
      pkgs,
      ...
    }:
    {
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
                # Keep Bluetooth headphones on classic A2DP. LE Audio/BAP
                # currently exposes Galaxy Buds2 Pro as LC3 sinks that reset
                # their ISO transport, leaving them connected with no audio.
                "bluez5.roles" = [
                  "a2dp_sink"
                  "a2dp_source"
                ];
              };
            };
            "11-bluetooth-policy"."wireplumber.settings" = {
              "bluetooth.autoswitch-to-headset-profile" = false;
              "bluetooth.use-persistent-storage" = true;
            };
            "12-preferred-xm4-output" = {
              "monitor.bluez.rules" = [
                {
                  matches = [
                    {
                      # Prefer the WH-1000XM4 over permanently attached desktop sinks
                      # whenever its A2DP output node appears.
                      "node.name" = "~bluez_output.*AC_80_0A_D4_08_48.*";
                    }
                  ];
                  actions = {
                    update-props = {
                      "priority.driver" = 2100;
                      "priority.session" = 2100;
                    };
                  };
                }
              ];
            };
          };
        };
      };

      systemd.user.services.pipewire.serviceConfig = lib.mkMerge [
        (lib.sinnix.systemd.mkPriorityConfig {
          nice = -11;
          rtprio = 95;
          memlock = "infinity";
        })
        (lib.sinnix.systemd.mkRestartPolicy {
          strategy = "on-failure";
          delaySec = 2;
        })
        {
          # Audio-specific hardening
          ProtectKernelModules = true;
          ProtectKernelTunables = true;
          RestrictNamespaces = true;
          LockPersonality = true;
        }
      ];

      systemd.user.services.wireplumber.serviceConfig = lib.mkMerge [
        (lib.sinnix.systemd.mkRestartPolicy {
          strategy = "always";
          delaySec = 2;
        })
        {
          ProtectKernelModules = true;
          RestrictNamespaces = true;
        }
      ];

      security.pam.loginLimits = lib.sinnix.mkPAMLimits {
        domain = "@audio";
        rtprio = 95;
        memlock = "unlimited";
      };

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
} args
