# Host-specific hardware configuration for sinnix-prime
{ pkgs, intercept-bounce, scribe-tap, ... }:
{
  environment.systemPackages = with pkgs; [
    intercept-bounce
    interception-tools
    interception-tools-plugins.caps2esc
    scribe-tap
  ];
  services.interception-tools = {
    enable = true;
    udevmonConfig = ''
      - JOB: "${pkgs.interception-tools}/bin/intercept -g $DEVNODE \
            | ${intercept-bounce}/bin/intercept-bounce -t 40ms --log-interval 6h --log-bounces --stats-json \
            | ${scribe-tap}/bin/scribe-tap --log-dir /realm/data/keylog/logs --snapshot-dir /realm/data/keylog/snapshots \
            | ${pkgs.interception-tools-plugins.caps2esc}/bin/caps2esc -m 1 \
            | ${pkgs.interception-tools}/bin/uinput -d $DEVNODE"
        DEVICE:
          LINK: "/dev/input/by-id/.*Logitech.*event-kbd"
          NAME: ".*Logitech.*"
    '';
  };

  systemd.tmpfiles.rules = [
    "d /realm/data/keylog 0700 sinity sinity - -"
    "d /realm/data/keylog/logs 0700 sinity sinity - -"
    "d /realm/data/keylog/snapshots 0700 sinity sinity - -"
    "z /realm/data/keylog 0700 sinity sinity - -"
    "z /realm/data/keylog/logs 0700 sinity sinity - -"
    "z /realm/data/keylog/snapshots 0700 sinity sinity - -"
  ];

  system.activationScripts.scribeTapDirectories.text = ''
    install -d -m 0700 -o sinity -g users /realm/data/keylog
    install -d -m 0700 -o sinity -g users /realm/data/keylog/logs
    install -d -m 0700 -o sinity -g users /realm/data/keylog/snapshots
  '';

  # Let the kernel's schedutil governor balance responsiveness with power draw.
  powerManagement.cpuFreqGovernor = "schedutil";
  hardware.enableRedistributableFirmware = true;
}
