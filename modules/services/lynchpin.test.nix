{
  inputs,
  mkServiceTest,
  ...
}:
let
  gitPkg = inputs.nixpkgs.legacyPackages.x86_64-linux.git;
in
mkServiceTest {
  name = "services-lynchpin";
  service = "lynchpin";
  extraModules = [
    {
      sinnix.services.lynchpin = {
        materializationTimer.enable = true;
      };
    }
  ];
  assertions = config: [
    {
      assertion = config.systemd.services ? lynchpin-materialize;
      message = "Lynchpin full materialization service must exist when materializationTimer is enabled";
    }
    {
      assertion = config.systemd.timers ? lynchpin-materialize;
      message = "Lynchpin full materialization timer must exist when materializationTimer is enabled";
    }
    {
      # Regression guard: the repo-rooted CLI writes `.lynchpin/` relative to
      # CWD, so the unit must pin WorkingDirectory or it fails from `/`.
      assertion =
        config.systemd.services.lynchpin-materialize.serviceConfig.WorkingDirectory
        == "/realm/project/sinity-lynchpin";
      message = "Lynchpin materialization service must run from the lynchpin checkout (WorkingDirectory)";
    }
    {
      assertion = builtins.elem "LYNCHPIN_REPO_ROOT=/realm/project/sinity-lynchpin" (
        config.systemd.services.lynchpin-materialize.serviceConfig.Environment or [ ]
      );
      message = "Lynchpin materialization service must export LYNCHPIN_REPO_ROOT";
    }
    {
      assertion = builtins.elem gitPkg (
        config.systemd.services.lynchpin-materialize.path or [ ]
      );
      message = "Lynchpin materialization service must have git on PATH";
    }
    {
      assertion = !(config.systemd.services ? lynchpin-refresh-worker);
      message = "Lynchpin must not install the legacy refresh-worker service";
    }
    {
      assertion = !(config.systemd.timers ? lynchpin-refresh-worker);
      message = "Lynchpin must not install the legacy refresh-worker timer";
    }
  ];
}
