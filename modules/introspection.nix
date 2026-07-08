# System Introspection: config dump generation
#
# Generates at build time:
# - /etc/sinnix/config.json   — Serialized config.sinnix attrset (for any consumer)
{
  lib,
  config,
  ...
}:
let
  cfg = config.sinnix;
  capturesRoot = cfg.paths.capturesRoot;

  # ── Collect enabled features ────────────────────────────────────────
  collectEnabled =
    domain: features:
    lib.concatLists (
      lib.mapAttrsToList (
        name: value:
        if builtins.isAttrs value && value ? enable && value.enable then [ "${domain}.${name}" ] else [ ]
      ) features
    );

  enabledFeatures = lib.concatLists (lib.mapAttrsToList collectEnabled (cfg.features or { }));

  enabledServices = lib.filter (
    name:
    let
      svc = cfg.services.${name} or { };
    in
    builtins.isAttrs svc && svc ? enable && svc.enable
  ) (builtins.attrNames (cfg.services or { }));

  # ── Config dump (selective serialization for safety) ────────────────
  configDump = {
    sinnix = {
      inherit (cfg)
        user
        machine
        paths
        projects
        ;
      secrets = {
        inherit (cfg.secrets) enable;
        paths = cfg.secrets.paths or { };
      };
    };
    meta = {
      hostname = config.networking.hostName;
      stateVersion = config.system.stateVersion;
      inherit enabledFeatures enabledServices;
      captures.directories = {
        asciinema = "${capturesRoot}/asciinema";
        screenshot = "${capturesRoot}/screenshot";
        audio = "${capturesRoot}/audio";
        keylog = "${capturesRoot}/keylog";
        syslog = "${capturesRoot}/syslog";
        machine = "${capturesRoot}/machine";
        activitywatch = "${capturesRoot}/activitywatch";
        shell = "${capturesRoot}/shell";
        comms = "${capturesRoot}/comms";
        webhistory = "${capturesRoot}/webhistory";
        kitty-scrollback = "${capturesRoot}/kitty-scrollback";
      };
      firewallPorts = {
        tcp = config.networking.firewall.allowedTCPPorts;
        udp = config.networking.firewall.allowedUDPPorts;
      };
    };
  };

in
{
  environment.etc."sinnix/config.json" = {
    text = builtins.toJSON configDump;
    mode = "0444";
  };
}
