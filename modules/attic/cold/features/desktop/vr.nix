# attic/cold: archived 2026-05-24 from sinnix-prime.
# Revive by `git mv` back to modules/features/desktop/vr.nix.
# Reason: VR streaming to standalone headsets — no current use; revival pending
# nixpkgs cached monado-25 (building from source caused multi-minute RAM spikes).
#
# TODO: If revived, split the generic host plumbing from higher-level Quest
# management. The generic module should install ADB/scrcpy/SideQuest and VR
# streaming tools; private per-device/app policy belongs outside public sinnix.
#
# TODO: Consider a declarative Quest reconciler instead of only installing
# host tools. Shape: Nix declares desired APKs, package names, versions, hashes,
# pushed files, and device settings; a generated `quest-sync` command compares
# that declaration against `adb shell pm ...`/device state and installs,
# updates, removes, or reports drift. This is reconciliation over ADB, not true
# NixOS-style control of Horizon OS.
# VR streaming to standalone headsets.
{
  mkFeatureModule,
  lib,
  pkgs,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "vr"
  ];
  description = "VR streaming to standalone headsets (Quest 3)";
  subFeatures = {
    wivrn = {
      # Off by default until upstream nixpkgs ships a cached monado-25.1.0;
      # building it from source on a fresh system was a multi-minute RAM spike
      # that contributed to desktop freezes. Re-enable per-host when needed.
      description = "WiVRn + Monado OpenXR streaming stack";
      default = false;
    };
    alvr = {
      description = "ALVR wireless VR streaming server (alternative to WiVRn)";
      default = false;
    };
    quest-tools = {
      description = "ADB, SideQuest, scrcpy, and udev rules for Meta Quest management";
      default = true;
    };
  };
  configFn =
    {
      config,
      lib,
      pkgs,
      cfg,
      user,
      ...
    }:
    lib.mkMerge [

      # ── WiVRn + Monado + OpenComposite ────────────────────────────────────────
      (lib.mkIf cfg.wivrn.enable {
        home-manager.users.${user} = {
          home.packages = with pkgs; [
            wivrn
            monado
            opencomposite
          ];

          # Point the OpenXR loader at Monado, and OpenVR games at OpenComposite
          home.sessionVariables = {
            # Monado as the system OpenXR runtime
            XR_RUNTIME_JSON = "${pkgs.monado}/share/openxr/1/openxr_monado.json";
            # OpenComposite intercepts SteamVR/OpenVR → forwards to Monado
            # Pressure-vessel / Steam looks for vrclient.so at this path
            OXR_LIBPATH = "${pkgs.opencomposite}/lib/opencomposite/bin/linux64/vrclient.so";
          };
        };

        # WiVRn uses Avahi for headset discovery on the local network
        services.avahi = {
          enable = true;
          nssmdns4 = true;
          publish.enable = true;
          publish.userServices = true;
        };

        # WiVRn streaming port
        networking.firewall = {
          allowedTCPPorts = [ 9757 ];
          allowedUDPPorts = [ 9757 ];
        };
      })

      # ── ALVR ──────────────────────────────────────────────────────────────────
      (lib.mkIf cfg.alvr.enable {
        home-manager.users.${user}.home.packages = [ pkgs.alvr ];

        # ALVR streaming ports: 9943 (handshake/control), 9944 (video/audio)
        networking.firewall = {
          allowedTCPPorts = [
            9943
            9944
          ];
          allowedUDPPorts = [
            9943
            9944
          ];
        };
      })

      # ── Quest tools: ADB, SideQuest, scrcpy ─────────────────────────────────
      (lib.mkIf cfg.quest-tools.enable {
        # TODO: Refresh this before revival. Current nixpkgs reports the old
        # android-udev-rules package removed because systemd uaccess handles
        # Android device permissions; the minimum host surface may now be only
        # pkgs.android-tools plus any still-needed local group/udev fallback.
        #
        # TODO: If adding declarative management, keep these as host tools and
        # add a separate reconciler app. Candidate capabilities:
        # - dump installed third-party packages/version codes from a connected
        #   headset as a seed manifest;
        # - install/update pinned APKs with `adb install -r`;
        # - optionally remove explicitly disallowed package names;
        # - push viewer configs/media manifests to /sdcard paths;
        # - apply SideQuest-like device settings via documented ADB commands;
        # - ingest Meta "owned apps/content" exports when available, but treat
        #   account entitlements as advisory because ADB only sees installed
        #   packages.
        # Meta/Oculus USB vendor ID for udev
        services.udev.extraRules = ''
          # Meta Quest headsets (vendor 2833)
          SUBSYSTEM=="usb", ATTR{idVendor}=="2833", MODE="0666", GROUP="adbusers"
        '';

        users.groups.adbusers = { };
        users.users.${user}.extraGroups = lib.mkAfter [ "adbusers" ];

        environment.systemPackages = with pkgs; [
          # Core ADB for sideloading, device config, file transfer
          android-tools

          # SideQuest: GUI sideloader, app store, device tuning dashboard
          # Wraps ADB with one-click resolution/refresh rate/FFR presets
          sidequest

          # scrcpy: mirror Quest display to PC window in real-time
          # Useful for spectating, recording, debugging sideloaded apps
          scrcpy
        ];
      })
    ];
} args
