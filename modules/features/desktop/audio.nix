# System audio configuration
#
# Configures PipeWire audio subsystem with:
# - PipeWire/WirePlumber for audio routing
# - Bluetooth audio (A2DP, SBC-XQ, mSBC)
# - Real-time priority for low latency
# - USB DAC quantum settings
#
# ── sinnix-prime signal path (not obvious from the device names) ────────────
# The Teufel Ultima 40 Aktiv speakers are wired by ANALOG AUX to the FiiO
# DigiHug/E10 USB DAC -- so the sink called "Fiio E10 Analog Stereo" IS the
# speakers, not headphones. The motherboard's own analog output does not work
# on this host, which is why the USB DAC carries everything.
#
# Two failure modes seen live 2026-08-13, both presenting as "audio is broken
# / weirdly quiet" with no obvious cause:
#   1. The FiiO card's profile silently ends up `off`, so its sink disappears
#      entirely and playback lands on some other device. Recover with
#      `wpctl status` then `pw-cli set-param <device-id> Profile
#      '{ index: <output:analog-stereo index>, save: true }'`.
#   2. ALSA refuses to start the FiiO with "Start error: No space left on
#      device" in a ~1Hz loop. Despite the wording this is USB ISOCHRONOUS
#      BANDWIDTH exhaustion, not disk: the DAC is a 12 Mbps full-speed device
#      sharing bus 1 with two hubs, storage, and (when attached for adb) the
#      phone. Freeing bus-1 load stops it; moving the DAC to the bus-2 xHCI
#      controller would isolate it permanently.
# The Ultima 40 is ALSO Bluetooth-pairable (7C:96:D2:C2:A3:E7). Connecting it
# over BT while the aux path is live contends for the same speakers and was
# observed to trigger failure mode 2 -- prefer one path at a time.
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
          };
        };
      };

      systemd.user.services.pipewire.serviceConfig = lib.mkMerge [
        {
          Nice = -11;
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

      # Lane dir for the watchdog's evidence writes (sinnix-capture write
      # does not create missing lane directories itself -- every other
      # lane using it pre-creates its own, e.g. capture-awair.nix).
      systemd.tmpfiles.rules = [
        "d ${config.sinnix.paths.capturesRoot}/audio-watchdog 0755 ${config.sinnix.user.name} users -"
      ];

      # sinnix-nz1c fix (1) + (3): the FiiO's profile has been observed
      # silently flipping to `off` twice, both with unknown root cause (idle
      # policy, suspend/resume, USB re-enumeration are all candidates), so
      # this polls rather than reacting to one specific event. It restores
      # the profile automatically when that happens, and surfaces (but
      # cannot fix -- it's real USB bus contention) the ALSA start-error
      # loop and the default-sink-zero-volume failure shape. Fix (2), moving
      # the DAC to the bus-2 xHCI controller, is a physical change for the
      # operator, not something this can do.
      #
      # DELIBERATELY NOT folded into capture-monitor.nix (2026-08-13,
      # operator config-density concern) despite the surface similarity
      # ("wake up, poll hardware, react"): different hardware domain (PipeWire/
      # wpctl vs DDC/i2c), different cadence need (2min -- a silently-dead
      # speaker matters faster than display-sensor drift -- vs 5min, driven
      # by ddcutil's own ~0.5s-per-transaction cost), and a different action
      # shape (this one actively remediates; capture-monitor only observes).
      # Gluing two unrelated hardware concerns into one unit for a lower
      # file count would be less legible, not more -- the actual bloat this
      # session fixed was the evidence-logging convention (below), not the
      # unit count.
      systemd.user.services.sinnix-audio-watchdog = {
        description = "Detect/restore FiiO DAC profile-off dropout; surface USB bandwidth failures";
        serviceConfig = lib.sinnix.mkRuntimeServiceConfig {
          runtimeInventory = config.sinnix.runtime.inventory;
          unit = "sinnix-audio-watchdog.service";
          overrides = {
            Type = "oneshot";
            ExecStart = lib.concatStringsSep " " [
              "${(helpers.mkSinnixPackagesFor pkgs).sinnix-audio-watchdog}/bin/sinnix-audio-watchdog"
              "${(helpers.mkSinnixPackagesFor pkgs).sinnix-capture}/bin/sinnix-capture"
              config.sinnix.paths.capturesRoot
            ];
          };
        };
      };

      systemd.user.timers.sinnix-audio-watchdog = {
        description = "Periodic FiiO DAC health check";
        wantedBy = [ "timers.target" ];
        timerConfig = {
          OnBootSec = "1min";
          OnUnitActiveSec = "2min";
          AccuracySec = "10s";
        };
      };

      # Nothing was watching the watchdog itself until now -- a real gap
      # (this is a plain service/timer liveness surface, not a captures[]
      # lane: the script only writes evidence on anomaly, so a captures[]
      # staleness check would eventually and wrongly alarm on healthy
      # silence -- see the comment in scripts/sinnix-audio-watchdog).
      sinnix.runtime.surfaces.audio-watchdog = {
        unit = "sinnix-audio-watchdog.service";
        manager = "user";
        resourceClass = "capture-runtime";
        observe = {
          enable = true;
          restartable = true;
        };
      };
    };
} args
