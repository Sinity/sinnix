# attic/cold: archived 2026-05-24 from sinnix-prime.
# Revive by `git mv` back to modules/features/desktop/vr.nix.
# Reason: VR streaming to standalone headsets — no current use; revival pending
# nixpkgs cached monado-25 (building from source caused multi-minute RAM spikes).
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
