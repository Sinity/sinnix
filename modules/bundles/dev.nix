{ lib, config, ... }:
let
  cfg = config.sinnix.bundles.dev;
in
{
  options.sinnix.bundles.dev = {
    enable = lib.mkEnableOption "Standard Development Environment (CLI)";
  };

  config = lib.mkIf cfg.enable {
    sinnix.features.dev = {
      core.enable = true;
      languages.enable = true;
      utilities.enable = true;
    };
    sinnix.features.cli.core.enable = true;
  };
}
