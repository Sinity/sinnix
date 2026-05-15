{
  lib,
  mkServiceTest,
  inputs,
  ...
}:
mkServiceTest {
  name = "services-machine-telemetry";
  service = "machine-telemetry";
  assertions =
    config:
    let
      service = config.systemd.services.machine-telemetry.serviceConfig;
      source = builtins.readFile (inputs.self + "/modules/services/machine-telemetry.nix");
      hasTmpfilesRule =
        pattern:
        builtins.any (rule: builtins.match ".*${pattern}.*" rule != null) config.systemd.tmpfiles.rules;
    in
    [
      {
        assertion = config.systemd.services ? machine-telemetry;
        message = "machine-telemetry service must exist";
      }
      {
        assertion =
          lib.hasInfix "/bin/machine-telemetry" service.ExecStart
          && lib.hasInfix "/realm/data/captures/machine/" service.ExecStart
          && lib.hasInfix "telemetry.sqlite" service.ExecStart;
        message = "machine-telemetry must write the canonical machine telemetry SQLite stream";
      }
      {
        assertion = !(service ? IOWeight) && !(service ? IOSchedulingClass) && !(service ? CPUWeight);
        message = "machine-telemetry must not introduce local cgroup policy";
      }
      {
        assertion =
          lib.hasInfix "CPU RAPL package/core watts" source
          && lib.hasInfix "latency_oversleep_ms" source
          && lib.hasInfix "fan.hwmon_unavailable" source
          && lib.hasInfix "service_state" source
          && lib.hasInfix "--machine=" source;
        message = "machine-telemetry must capture power, latency, missing fan gaps, and service state";
      }
      {
        assertion = hasTmpfilesRule "/realm/data/captures/machine";
        message = "machine-telemetry capture root must be created via tmpfiles";
      }
      {
        assertion =
          builtins.elem "d /realm/data/captures/machine 0755 root users -" config.systemd.tmpfiles.rules
          && builtins.elem "d /realm/data/captures/machine/experiments 0775 root users -" config.systemd.tmpfiles.rules
          && builtins.elem "d /realm/data/captures/machine/legacy 0775 root users -" config.systemd.tmpfiles.rules;
        message = "machine-telemetry tmpfiles ownership must allow system capture plus user experiment manifests";
      }
      {
        assertion =
          lib.hasInfix "network_sample" source
          && lib.hasInfix "--network-interval" service.ExecStart
          && !(config.systemd.services ? network-probe)
          && !(config.systemd.timers ? network-probe);
        message = "machine-telemetry must own network probing without a separate network-probe timer";
      }
    ];
}
