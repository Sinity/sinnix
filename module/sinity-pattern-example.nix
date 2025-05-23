# Example: Sinity Alias Pattern
# This demonstrates the recommended pattern for domain modules

{
  config,
  lib,
  pkgs,
  username,
  ...
}:
with lib;
let
  # Pattern: Define sinity alias at the top of the module
  sinity = config.home-manager.users.${username};
in
{
  # Example usage - accessing user config without verbosity
  config = mkIf (sinity ? home) {
    # Can now use sinity.programs.X instead of config.home-manager.users.sinity.programs.X
    environment.systemPackages = if sinity.programs.git.enable or false then [ pkgs.git-lfs ] else [ ];
  };
}
