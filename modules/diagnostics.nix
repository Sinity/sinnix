# System diagnostics tools
#
# Installs hardware introspection utilities (hwinfo, lshw, smartmontools)
# and the perf-scan script for comprehensive system analysis. Desktop only.
#
# Note: perf-scan bundles its own heavier dependencies (flamegraph, etc.)
# to keep this module lightweight.
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
  hogkill = pkgs."hogkill";
  asbl-no-more = pkgs."asbl-no-more";
in
{
  config = lib.mkIf isDesktop {
    environment.systemPackages = lib.mkAfter (
      coreDiagnostics ++ [ perfScan hogkill asbl-no-more ]
    );
  };
}
