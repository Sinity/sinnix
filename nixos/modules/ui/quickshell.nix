{
  lib,
  config,
  username,
  ...
}:
let
  cfg = config.sinnix.interface.quickshell;
in
{
  options.sinnix.interface.quickshell.enable = lib.mkOption {
    type = lib.types.bool;
    default = false;
    description = "Enable the Quickshell status bar.";
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = username != "";
        message = "Quickshell requires a user account to attach to.";
      }
    ];
  };
}
