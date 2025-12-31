{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.machine) isDesktop;
  coreDiagnostics = with pkgs; [
    hwinfo
    inxi
    lshw
    smartmontools
    nvme-cli
    hdparm
  ];
  perfScan = pkgs."perf-scan";
in
{
  config = lib.mkIf isDesktop {
    environment.systemPackages = lib.mkAfter (
      coreDiagnostics ++ [ perfScan ]
    );
  };
}
