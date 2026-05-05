{
  lib,
  mkServiceTest,
  inputs,
  ...
}:
mkServiceTest {
  name = "services-power-watchdog";
  service = "power-watchdog";
  assertions =
    config:
    let
      service = config.systemd.services.power-watchdog.serviceConfig;
      source = builtins.readFile (inputs.self + "/modules/services/power-watchdog.nix");
    in
    [
      {
        assertion = config.systemd.services ? power-watchdog;
        message = "power-watchdog service must exist";
      }
      {
        assertion = service.IOWeight == 1;
        message = "power-watchdog must not compete with foreground storage I/O";
      }
      {
        assertion = lib.hasInfix "sync -d" source && !(lib.hasInfix "sync -f" source);
        message = "power-watchdog must sync only its CSV data, not the whole filesystem";
      }
      {
        assertion =
          lib.hasInfix ''val=$(cat "$1" 2>/dev/null || true)'' source
          && !(lib.hasInfix ''val=$(cat "$1" 2>/dev/null) || echo "0"'' source);
        message = "power-watchdog temp reads must emit exactly one CSV value when sysfs files are missing";
      }
      {
        assertion = lib.hasInfix "last_rotate=$(date +%s)" source;
        message = "power-watchdog must not rewrite retained CSV data immediately after every restart";
      }
    ];
}
