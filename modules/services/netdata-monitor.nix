# Local, real-time host telemetry for the operator's phone. The dashboard is
# never claimed into Netdata Cloud and is reachable only over the tailnet.
{
  mkServiceModule,
  lib,
  ...
}@args:
mkServiceModule {
  name = "netdata-monitor";
  description = "Tailnet-only real-time resource dashboard";
  surface = {
    unit = "netdata.service";
    resourceClass = "observability";
    observe = {
      enable = true;
      restartable = true;
    };
  };
  configFn =
    { config, ... }:
    let
      stateDir = "/realm/state/netdata";
      tailscaleAddress = "100.114.9.64";
      port = 19999;
    in
    {
      services.netdata = {
        enable = true;
        enableAnalyticsReporting = false;
        config = {
          global = {
            "update every" = 1;
            "cache directory" = "${stateDir}/cache";
            "lib directory" = "${stateDir}/lib";
            "debug log" = "none";
            "access log" = "none";
            "error log" = "syslog";
          };
          db = {
            "mode" = "dbengine";
            "dbengine multihost disk space" = 512;
          };
          ml.enabled = "yes";
          web = {
            "bind to" = "127.0.0.1:${toString port} ${tailscaleAddress}:${toString port}";
            "allow connections from" = "localhost ${tailscaleAddress}";
            "allow dashboard from" = "localhost ${tailscaleAddress}";
          };
          cloud.enabled = "no";
        };
      };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${stateDir} 0750 netdata netdata -"
        "d ${stateDir}/cache 0750 netdata netdata -"
        "d ${stateDir}/lib 0750 netdata netdata -"
      ];

      networking.firewall.interfaces.${config.sinnix.services.tailscale.interfaceName}.allowedTCPPorts = [
        port
      ];
    };
} args
