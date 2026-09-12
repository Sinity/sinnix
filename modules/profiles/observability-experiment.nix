# Optional live dashboard. Fixed capture and health telemetry remains active
# independently of this exploratory UI.
{ config, lib, ... }:
let
  cfg = config.sinnix.profiles.observability-experiment;
in
{
  options.sinnix.profiles.observability-experiment.enable =
    lib.mkEnableOption "Netdata observability experiment";

  config.sinnix.services.netdata-monitor.enable = lib.mkDefault cfg.enable;
}
