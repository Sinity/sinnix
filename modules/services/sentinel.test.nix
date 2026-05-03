{ lib, mkServiceTest, inputs, ... }:
mkServiceTest {
  name = "services-sentinel";
  service = "sentinel";
  assertions =
    config:
    let
      serviceEnv = config.systemd.services.sinnix-sentinel.environment;
      sentinelScript = builtins.readFile (inputs.self + "/scripts/sinnix-sentinel");
      healthPolicy = builtins.fromJSON config.environment.etc."sinnix/health-policy.json".text;
    in
    [
      {
        assertion = config.systemd.services ? sinnix-sentinel;
        message = "sinnix-sentinel oneshot service must exist";
      }
      {
        assertion = config.systemd.timers ? sinnix-sentinel;
        message = "sinnix-sentinel timer must exist";
      }
      {
        assertion = config.environment.etc ? "sinnix/health-policy.json";
        message = "health-policy.json must be generated (from introspection.nix)";
      }
      {
        assertion = config.environment.etc ? "sinnix/config.json";
        message = "config.json must be generated (from introspection.nix)";
      }
      {
        assertion = builtins.any (
          rule: builtins.match ".*sinnix-sentinel.*" rule != null
        ) config.systemd.tmpfiles.rules;
        message = "sentinel event log directory must be created via tmpfiles";
      }
      {
        assertion =
          serviceEnv.SINNIX_CORRECTIVE_ACTIONS == "false"
          && lib.hasInfix ''CORRECTIVE_ACTIONS="''${SINNIX_CORRECTIVE_ACTIONS:-false}"'' sentinelScript
          && lib.hasInfix "--correct) CORRECTIVE_ACTIONS=true" sentinelScript;
        message = "sentinel corrective actions must be opt-in and observable";
      }
      {
        assertion = healthPolicy.backups.backupTargets == [ ];
        message = "sentinel must not run Borg repository probes in the 60s health loop";
      }
    ];
}
