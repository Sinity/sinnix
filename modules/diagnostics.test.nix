{
  lib,
  mountTmpfsRoots,
  baseTestConfig,
  inputs,
  ...
}:
{
  name = "core-diagnostics-tools";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "diagnostics-tools-test";
        sinnix.machine.isDesktop = true;
      }
    )
  ];
  assertions =
    config:
    let
      zramResetScript = builtins.readFile (inputs.self + "/scripts/sinnix-zram-reset");
      experimentScript = builtins.readFile (inputs.self + "/scripts/machine-experiment-run");
    in
    [
      {
        assertion = lib.any (pkg: lib.getName pkg == "sinnix-zram-reset") config.environment.systemPackages;
        message = "desktop diagnostics must install the manual zram reset command";
      }
      {
        assertion =
          lib.hasInfix "swapon --noheadings --raw --show=NAME" zramResetScript
          && lib.hasInfix "active swap is not exactly /dev/zram0" zramResetScript
          && lib.hasInfix "run as root" zramResetScript
          && lib.hasInfix "This is intentionally manual. It is not a polling swap-drain service." zramResetScript;
        message = "sinnix-zram-reset must stay manual and refuse unsafe swap topologies";
      }
      {
        assertion =
          lib.hasInfix "systemctl stop dev-zram0.swap" zramResetScript
          && lib.hasInfix "printf 1 > /sys/block/zram0/reset" zramResetScript
          && lib.hasInfix "seq 1 20" zramResetScript
          && lib.hasInfix "restore_zram" zramResetScript
          && lib.hasInfix "exit 75" zramResetScript
          && lib.hasInfix "systemctl start systemd-zram-setup@zram0.service" zramResetScript
          && lib.hasInfix "systemctl start dev-zram0.swap" zramResetScript;
        message = "sinnix-zram-reset must use the validated stop/retry-reset/restore/start sequence";
      }
      {
        assertion =
          lib.hasInfix "--user-unit" experimentScript
          && lib.hasInfix "systemd_user" experimentScript
          && lib.hasInfix "systemctl_show(unit, user=user)" experimentScript
          && lib.hasInfix "unit.startswith(\"user:\")" experimentScript
          && lib.hasInfix "\"stdout_path\"" experimentScript
          && lib.hasInfix "\"stdout.log\"" experimentScript
          && lib.hasInfix "\"stderr_path\"" experimentScript
          && lib.hasInfix "\"stderr.log\"" experimentScript
          && lib.hasInfix "tee_stream" experimentScript;
        message = "machine-experiment-run must capture user-manager units without misclassifying them as system units";
      }
    ];
}
