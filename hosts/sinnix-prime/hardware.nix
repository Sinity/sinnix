# Host-specific hardware configuration for sinnix-prime
{
  pkgs,
  lib,
  inputs,
  config,
  ...
}:
let
  interceptTools = pkgs.interception-tools;
  capsPlugin = pkgs.interception-tools-plugins.caps2esc;
  interceptCmd = lib.escapeShellArgs [ "${interceptTools}/bin/intercept" "-g" "$DEVNODE" ];
  bounceCmd = config.services.interceptBounce.commandString;
  scribeCmd = config.services.scribeTap.commandString;
  capsCmd = lib.escapeShellArgs [ "${capsPlugin}/bin/caps2esc" "-m" "1" ];
  uinputCmd = lib.escapeShellArgs [ "${interceptTools}/bin/uinput" "-d" "$DEVNODE" ];
  pipeline = lib.concatStringsSep " | " [ interceptCmd bounceCmd scribeCmd capsCmd uinputCmd ];
in
{
  environment.systemPackages = with pkgs; [
    interception-tools
    interception-tools-plugins.caps2esc
  ];

  services.interceptBounce = {
    enable = true;
    debounceTime = "40ms";
    logInterval = "6h";
    logBounces = true;
    statsJson = true;
    package = inputs.intercept-bounce.packages.${pkgs.system}.intercept-bounce;
  };

  services.scribeTap = {
    enable = true;
    dataDir = "/realm/data/keylog";
    logDir = "/realm/data/keylog/logs";
    snapshotDir = "/realm/data/keylog/snapshots";
    logMode = "both";
    contextMode = "hyprland";
    translateMode = "xkb";
    hyprUser = "sinity";
    xkbLayout = "pl";
    directoryMode = "0700";
    directoryUser = "sinity";
    directoryGroup = "users";
    package = inputs.scribe-tap.packages.${pkgs.system}.default;
  };

  services.interception-tools = {
    enable = true;
    udevmonConfig = ''
      - JOB: "${pipeline}"
        DEVICE:
          LINK: "/dev/input/by-id/.*Logitech.*event-kbd"
          NAME: ".*Logitech.*"
    '';
  };

  # Let the kernel's schedutil governor balance responsiveness with power draw.
  powerManagement.cpuFreqGovernor = "schedutil";
  hardware.enableRedistributableFirmware = true;
}
