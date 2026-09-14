# System audio: PipeWire/WirePlumber routing, Bluetooth (A2DP, SBC-XQ, mSBC),
# and real-time priority.
#
# ── sinnix-prime signal path (not obvious from the device names) ────────────
# The Teufel Ultima 40 Aktiv speakers are wired by ANALOG AUX to the FiiO
# DigiHug/E10 USB DAC -- so the sink called "Fiio E10 Analog Stereo" IS the
# speakers, not headphones. The motherboard's own analog output does not work
# on this host, which is why the USB DAC carries everything.
#
# Two failure modes present as "audio is broken / weirdly quiet":
#   1. The FiiO card's profile ends up `off`, so its sink disappears and
#      playback lands on some other device. Recover with `wpctl status` then
#      `pw-cli set-param <device-id> Profile
#      '{ index: <output:analog-stereo index>, save: true }'`.
#   2. ALSA refuses to start the FiiO with "Start error: No space left on
#      device" in a ~1Hz loop, or dmesg repeats `Not enough bandwidth for
#      altsetting 2` / `usb_set_interface failed (-28)`. Despite the wording
#      this is USB ISOCHRONOUS BANDWIDTH exhaustion, not disk: the DAC is a
#      12 Mbps full-speed device whose playback and capture endpoints share
#      one 1023 byte/frame budget, so 24-bit in both directions does not fit.
#      The observed trigger (2026-09-14) was the DAC's own unused line-in
#      winning the default-source election and being opened by Chrome/Steam;
#      the `13-fiio-no-capture` rule below disables that node. Moving the DAC
#      to the bus-2 xHCI controller would raise the ceiling permanently.
# The Ultima 40 is ALSO Bluetooth-pairable (7C:96:D2:C2:A3:E7). Connecting it
# over BT while the aux path is live contends for the same speakers and can
# trigger failure mode 2 -- prefer one path at a time.
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
      helpers,
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
            # The E10's line-in is unused (nothing is plugged into it), but it
            # advertises as an ordinary Audio/Source and can win WirePlumber's
            # default-source election over the Yeti. Whatever then opens the
            # default mic -- Chrome, Steam voice -- pins a 24-bit isochronous
            # IN endpoint on a 12 Mbps full-speed device, and playback's
            # altsetting can no longer fit the 1023 byte/frame budget: the
            # ~1Hz `usb_set_interface failed (-28)` loop of failure mode 2.
            # Disabling the capture node removes the contention at the source;
            # the DAC's playback sink is untouched.
            "13-fiio-no-capture" = {
              "monitor.alsa.rules" = [
                {
                  matches = [
                    { "node.name" = "~alsa_input[.]usb-FiiO_DigiHug_USB_Audio.*"; }
                  ];
                  actions = {
                    update-props = {
                      "node.disabled" = true;
                    };
                  };
                }
              ];
            };
          };
        };
      };

      systemd.user.services.pipewire.serviceConfig = lib.mkMerge [
        {
          Nice = -11;
          # mod.rt raises its own threads to nice -11 with setpriority before
          # asking rtkit; without this rlimit that first attempt logs
          # "Permission denied" on every start even though rtkit then succeeds.
          LimitNICE = -11;
          LimitRTPRIO = 95;
          LimitMEMLOCK = "infinity";
        }
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

      # Same mod.rt behaviour in pipewire-pulse (see pipewire above).
      systemd.user.services.pipewire-pulse.serviceConfig = {
        Nice = -11;
        LimitNICE = -11;
      };

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

      # These reach the user manager (user@.service goes through PAM), which
      # is where the unit-level LimitNICE above gets its hard ceiling.
      security.pam.loginLimits = lib.sinnix.mkPAMLimits {
        domain = "@audio";
        rtprio = 95;
        memlock = "unlimited";
        nice = -11;
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

    };
} args
