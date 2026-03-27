# VR streaming to standalone headsets (Meta Quest 3)
#
# Provides wireless PC VR via ALVR or WiVRn, with ADB tooling for
# sideloading the headset client. The PC encodes frames via NVENC
# and streams over Wi-Fi; the Quest decodes and displays them.
#
# Quest 3 setup (one-time):
#   1. Enable developer mode in Meta Horizon app (phone)
#   2. Connect Quest via USB-C
#   3. adb install <alvr-client.apk>  (download from ALVR GitHub releases)
#   4. Launch ALVR on PC, launch ALVR client on Quest, pair
#
# Network: Quest should be on 5 GHz Wi-Fi, PC wired via Ethernet.
# Ports 9943-9944 (TCP+UDP) are opened for ALVR streaming.
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
    alvr = {
      description = "ALVR wireless VR streaming server";
      default = true;
    };
    wivrn = {
      description = "WiVRn + Monado OpenXR streaming (alternative to ALVR)";
      default = false;
    };
    quest-tools = {
      description = "ADB and udev rules for Meta Quest sideloading";
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

      # ── WiVRn + Monado + OpenComposite ────────────────────────────────────────
      (lib.mkIf cfg.wivrn.enable {
        home-manager.users.${user}.home.packages = with pkgs; [
          wivrn
          monado
          opencomposite
        ];

        # WiVRn uses Avahi for headset discovery + port 9757
        services.avahi = {
          enable = true;
          publish.enable = true;
          publish.userServices = true;
        };

        networking.firewall = {
          allowedTCPPorts = [ 9757 ];
          allowedUDPPorts = [ 9757 ];
        };
      })

      # ── Quest ADB tools ──────────────────────────────────────────────────────
      (lib.mkIf cfg.quest-tools.enable {
        # Meta/Oculus USB vendor ID for udev
        services.udev.extraRules = ''
          # Meta Quest headsets (vendor 2833)
          SUBSYSTEM=="usb", ATTR{idVendor}=="2833", MODE="0666", GROUP="adbusers"
        '';

        users.groups.adbusers = { };
        users.users.${user}.extraGroups = lib.mkAfter [ "adbusers" ];

        # android-tools already in dev shell, but ensure adb is always available
        # for VR sideloading even outside dev environments
        environment.systemPackages = [ pkgs.android-tools ];
      })
    ];
} args
